# -*- coding: utf-8 -*-
"""本地 Laya 判断客户端：对 engine 来说是 Jev.ask 的 drop-in 替代品。

engine 仍然调用 ask(state, questions, provider=..., model=...) —— 这里忽略
provider/model，全部走本地 Laya（通过子进程桥接 CUDA venv，真正离线、不碰网络）。

通信：长驻子进程 tools/laya_bridge_server.py（用 laya_cuda_venv 的 python 跑），
stdin/stdout 走 JSON 行协议。首行 "READY" 表示模型已加载，之后每行一个请求/响应。

路径与 laya_bridge.py 里的常量保持一致；可用环境变量 LAYA_VENV_PY 覆盖 venv 解释器。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

# 与 laya_bridge.py 里的常量保持一致（CUDA venv 里的本地 GPU Laya）
_DEFAULT_VENV_PY = (
    r"D:\xwechat_files\RAW\.workbuddy"
    r"\2026-09-21-01-35-33\laya_cuda_venv\Scripts\python.exe"
)


def _bridge_path() -> str:
    """定位 tools/laya_bridge_server.py，兼容「源码运行」与「PyInstaller 打包」两种布局。

    打包后 core 模块被收进 PYZ 归档，__file__ 指向 _internal/core/...（虚拟路径），
    其 ../tools/ 即 _internal/tools/；另外兜底按可执行文件所在目录的 _internal/tools/ 找，
    以及 sys._MEIPASS（onedir 的 contents 目录）下的 tools/。第一个真实存在的路径即采用。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "tools", "laya_bridge_server.py"),
        os.path.join(os.path.dirname(sys.executable), "_internal", "tools",
                     "laya_bridge_server.py"),
    ]
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", ""):
        candidates.append(os.path.join(sys._MEIPASS, "tools", "laya_bridge_server.py"))
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0])


_BRIDGE = _bridge_path()


class JevError(Exception):
    """与 core/jev_client.JevError 同款，engine 直接复用，调用方无需感知后端切换。"""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


_lock = threading.Lock()
_proc = None
_ready = threading.Event()


def _spawn() -> None:
    global _proc
    venv_py = os.environ.get("LAYA_VENV_PY") or _DEFAULT_VENV_PY
    if not os.path.exists(venv_py):
        raise JevError(f"本地 Laya 的 CUDA venv 不存在: {venv_py}")
    bridge = os.path.abspath(_BRIDGE)
    if not os.path.exists(bridge):
        raise JevError(f"桥接脚本缺失: {bridge}")
    # 项目根作为 cwd，保证桥接里 import core 能找到
    cwd = os.path.dirname(os.path.dirname(bridge))
    _proc = subprocess.Popen(
        [venv_py, bridge],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    # 等首行：READY（模型已加载）或 ERROR（启动失败）
    first = _proc.stdout.readline().strip()
    if first.startswith("ERROR"):
        raise JevError("Laya 桥接启动失败: " + first[6:].strip())
    if first != "READY":
        err = _proc.stderr.read(800) if _proc.stderr else ""
        raise JevError(f"Laya 桥接未就绪（收到 {first!r}）：{err}")
    _ready.set()


def _ensure() -> None:
    global _proc
    with _lock:
        if _proc is None or _proc.poll() is not None:
            _ready.clear()
            _spawn()


def ask(state: dict, questions: dict, timeout: float = 30,
        provider: str | None = None, model: str | None = None) -> dict:
    """Jev.ask 的 drop-in：把判断交给本地 Laya。

    返回 {"answers": {name: {...}}, "usage": {...}}（Laya 不报 token 用量，usage 留空）。
    provider / model 形参保留以兼容 engine 调用，但本地 Laya 不用，直接忽略。
    """
    _ensure()
    req = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)
    try:
        _proc.stdin.write(req + "\n")  # type: ignore[union-attr]
        _proc.stdin.flush()
    except (BrokenPipeError, ValueError) as e:
        raise JevError(f"Laya 桥接已断开: {e}")

    # 用子线程读一行，便于实现超时（Windows 下 select 对管道不可靠）
    got: dict = {}

    def _read() -> None:
        line = _proc.stdout.readline()  # type: ignore[union-attr]
        if line:
            got["line"] = line

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise JevError(f"Laya 判断超时（{timeout}s）")
    line = got.get("line")
    if not line:
        err = _proc.stderr.read(800) if _proc.stderr else ""  # type: ignore[union-attr]
        raise JevError(f"Laya 桥接无响应: {err}")
    resp = json.loads(line.strip())
    if "error" in resp:
        raise JevError(f"Laya 判断出错: {resp['error']}")
    return {"answers": resp.get("answers", {}), "usage": resp.get("usage", {})}


def close() -> None:
    """关掉桥接子进程，释放 GPU 显存。程序退出时建议调用一次。"""
    global _proc
    if _proc is not None:
        try:
            if _proc.stdin:
                _proc.stdin.close()
        except Exception:
            pass
        try:
            _proc.terminate()
        except Exception:
            pass
        _proc = None
        _ready.clear()
