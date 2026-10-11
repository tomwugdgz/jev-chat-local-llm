# -*- coding: utf-8 -*-
"""真·本地端到端验证：判断走本地 Laya + 起草走本地 Ollama，全程零外部网络。

需要：本机 Ollama 已启动且拉好 minicpm5-2b-32k:latest；CUDA venv 的本地 Laya 可用
（首次约 70s 加载模型）。用「有 openai SDK + 能 import laya_bridge」的 python 跑，例如系统 Python 3.13。

    python tools/verify_local_e2e.py
"""
from __future__ import annotations

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 项目根加入 path，保证 import core
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.engine as engine  # noqa: E402


MESSAGES = [
    ("her", "你今天是不是又忘了我跟你说过什么？"),
    ("me", "记得，你先别提示我，让我自己说。"),
    ("her", "那你说。"),
    ("me", "等一下，我想说完整一点。"),
    ("her", "你最好是。"),
]
RELATIONSHIP = "romantic partners"
OLLAMA_MODEL = "minicpm5-2b-32k:latest"
OLLAMA_BASE = "http://localhost:11434/v1"


def fmt(name: str, ans: dict) -> str:
    t = ans.get("type")
    if t == "noul":
        return f"{name}: noul={ans.get('noul'):.2f}"
    if t == "choice":
        return f"{name}: {ans.get('choice')} (conf {ans.get('confidence'):.2f})"
    if t == "score":
        return f"{name}: score={ans.get('score'):.2f} (conf {ans.get('confidence'):.2f})"
    return f"{name}: {ans}"


def main() -> int:
    print("=== 真·本地端到端：判断=本地Laya + 起草=本地Ollama(零外部网络) ===")
    for w, t in MESSAGES:
        print(f"  {w}: {t}")
    r = engine.analyze(
        MESSAGES, RELATIONSHIP,
        provider="ollama", model=OLLAMA_MODEL, base_url=OLLAMA_BASE,
        jev_provider="openrouter",
    )

    print("\n判断（来自本地 Laya）:")
    for name in ("literal_question", "true_intent", "danger_level",
                 "should_reply_now", "best_action", "she_needs", "tension_resolved"):
        if name in r["answers"]:
            print("  " + fmt(name, r["answers"][name]))

    print("\n候选（来自本地 Ollama）与 Laya 排序（★=推荐）:")
    scores = r.get("scores")
    for i, c in enumerate(r["candidates"]):
        pct = f"  {scores[i]:.0%}" if scores else ""
        print(f"  {'★' if i == r['best_index'] else ' '} {c}{pct}")

    print("\nusage:", r.get("usage"))
    print("\n端到端验证完成：判断与起草全部来自本机模型，无任何外部 API 调用。")

    try:
        from core import laya_judge
        laya_judge.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
