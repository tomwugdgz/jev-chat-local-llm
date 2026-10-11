# -*- coding: utf-8 -*-
"""Laya 判断桥接服务（运行在 CUDA venv 里，真正本地离线）。

父进程（jev-chat 主程序，PySide6 python）通过 stdin/stdout 的 JSON 行协议调用本服务：
  请求: {"state": {...}, "questions": {name: {type, instructions, criteria}}}
  响应: {"answers": {name: {type, ...}}, "usage": {}}
  启动后打一行 "READY" 再进入请求循环；致命报错打 "ERROR: ..." 并退出。

本服务把 Jev 的 question 格式适配成 Laya 本地格式（保留原 instructions，
criteria 字典→列表），再把 Laya 的答案映射回 Jev 的形状——engine 完全不用关心
底下跑的是 Laya 还是 Jev。

注意：本文件只在 CUDA venv 的 python 下跑（才有本地 GPU Laya）。jev-chat 主程序
通过 core/laya_judge.py 用子进程拉起它，不要在别处直接 import。
"""
from __future__ import annotations

import json
import os
import sys

# 项目根（tools/ 的上一级）加入 path，便于 import core。
# 打包后脚本位于 _internal/tools/，ROOT 会是 _internal —— 里面含 PyInstaller 塞入的
# python312.dll 与 3.12 标准库 .pyd；一旦加进 sys.path，外部 CUDA venv（Python 3.13）
# 会优先加载到 3.12 的 .pyd，引用到 python312.dll 报「conflicts with this version of Python」。
# 故仅当 ROOT 确为项目根（含 core/）时才加入；打包态跳过，避免污染外部解释器路径。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.isdir(os.path.join(ROOT, "core")) and ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 本机代理会让 HuggingFace 下载返回 502，权重已落地本地目录，必须离线
os.environ.setdefault("HF_HUB_OFFLINE", "1")


def adapt(questions: dict):
    """Jev question 格式 → Laya 本地格式（保留 instructions，criteria 字典→列表）。

    返回 (laya_questions, meta)。meta[name] = (jev_type, [keys], [opts])，
    用于把 Laya 返回的「选中文本」映射回 Jev 的「key」。
    """
    out, meta = {}, {}
    for name, q in questions.items():
        t = q["type"]
        crit = q.get("criteria", {})
        instr = q.get("instructions", "")
        if t == "noul":
            # noul(是否)在 Laya 本地没有原生类型，用 2 选 1 的 choice 顶替
            opts = list(crit.values())
            out[name] = {"type": "choice", "instructions": instr, "criteria": opts}
            meta[name] = ("noul", list(crit.keys()), opts)
        elif t == "choice":
            opts = list(crit.values())
            out[name] = {"type": "choice", "instructions": instr, "criteria": opts}
            meta[name] = ("choice", list(crit.keys()), opts)
        elif t == "score":
            out[name] = {"type": "score", "instructions": instr, "criteria": crit}
            meta[name] = ("score",)
        else:
            opts = crit if isinstance(crit, list) else list(crit.values())
            out[name] = {"type": t, "instructions": instr, "criteria": opts}
            meta[name] = (t,)
    return out, meta


def map_back(raw: dict, meta: dict) -> dict:
    """Laya 答案 → Jev 形状。choice 返回的是选中的 criteria 文本，要映射回 key。"""
    answers = {}
    for name, ans in raw.items():
        jt = (meta.get(name) or (None,))[0]
        if jt == "noul":
            opts = meta[name][2]
            chosen = ans.get("choice")
            idx = opts.index(chosen) if chosen in opts else 0
            key = meta[name][1][idx]
            conf = float(ans.get("confidence", 0.5) or 0.5)
            noul = conf if key == "true" else 1.0 - conf
            answers[name] = {"type": "noul", "noul": noul}
        elif jt == "choice":
            opts = meta[name][2]
            chosen = ans.get("choice")
            idx = opts.index(chosen) if chosen in opts else 0
            key = meta[name][1][idx]
            conf = float(ans.get("confidence", 0.0) or 0.0)
            n = len(meta[name][1])
            raw_probs = ans.get("probabilities") or {}
            # 优先用 Laya 给的逐选项概率（键是 criteria 文本）；没有就用 confidence 构造，
            # 保证「被选中 = 概率最高」，跟界面星标一致
            mapped = {k: float(raw_probs.get(o, 0.0) or 0.0)
                      for k, o in zip(meta[name][1], opts)}
            if sum(mapped.values()) <= 0:
                mapped = {k: (conf if k == key else (1.0 - conf) / max(n - 1, 1))
                          for k in meta[name][1]}
            total = sum(mapped.values()) or 1.0
            probabilities = {k: v / total for k, v in mapped.items()}
            answers[name] = {"type": "choice", "choice": key,
                             "confidence": conf, "probabilities": probabilities}
        elif jt == "score":
            probs = ans.get("probabilities") or {}
            answers[name] = {"type": "score",
                             "score": float(ans.get("score", 0.0) or 0.0),
                             "confidence": float(ans.get("confidence", 0.0) or 0.0),
                             "probabilities": {str(k): float(v) for k, v in probs.items()}}
        else:
            answers[name] = ans
    return answers


def main() -> None:
    from laya_bridge import _get_router  # 复用本机门的路径常量与离线设置

    router = _get_router("multilingual")  # 加载一次，之后复用（约 2.6GB 显存）

    sys.stdout.write("READY\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            laya_q, meta = adapt(req["questions"])
            res = router.predict({"state": req["state"]}, laya_q, model="multilingual")
            answers = map_back(res.get("answers", {}), meta)
            sys.stdout.write(json.dumps({"answers": answers, "usage": {}},
                                        ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as e:  # 单条失败不影响后续；把错误回传父进程
            sys.stdout.write(json.dumps({"error": str(e)}, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stdout.write("ERROR: " + str(e) + "\n")
        sys.stdout.flush()
        sys.exit(1)
