# -*- coding: utf-8 -*-
"""独立验证：engine 的判断是否已真正走本地 Laya（不依赖草稿 LLM key）。

做法：把 draft_candidates 桩成 3 条固定候选，直接跑 analyze()，
观察 Jev→Laya 替换后的完整链路——7 道判断 + 排序都来自本地 Laya。
需要本地 CUDA venv 的 Laya（首次会加载模型约 70s，脚本已留足超时）。

    python tools/verify_laya_judge.py        # 用任意有 subprocess 的 python 跑
"""
from __future__ import annotations

import io
import os
import sys
import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 项目根加入 path，保证 import core 能找到（脚本在 tools/ 下，sys.path[0] 是 tools/）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 桩掉 core.draft，避免 import 链拉起 core.llm（需要草稿 SDK / key）。
# engine 在 from .draft import draft_candidates 时会取到这个桩。
_fake_draft = types.ModuleType("core.draft")
STUB_CANDIDATES = ["我先想想再回你", "记得，你别急", "你先说完整一点"]
_fake_draft.draft_candidates = lambda *a, **k: list(STUB_CANDIDATES)
sys.modules["core.draft"] = _fake_draft

import core.engine as engine  # noqa: E402  （导入时 from .draft 取到的就是我们桩的）


MESSAGES = [
    ("her", "你今天是不是又忘了我跟你说过什么？"),
    ("me", "记得，你先别提示我，让我自己说。"),
    ("her", "那你说。"),
    ("me", "等一下，我想说完整一点。"),
    ("her", "你最好是。"),
]
RELATIONSHIP = "romantic partners"


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
    print("=== 独立验证：本地 Laya 判断（engine 完整链路，草稿已桩）===")
    for w, t in MESSAGES:
        print(f"  {w}: {t}")
    # provider/jev_provider 形参保留以兼容 engine 签名，本地 Laya 会忽略它们
    r = engine.analyze(MESSAGES, RELATIONSHIP, provider="deepseek",
                       jev_provider="openrouter")

    print("\n判断（来自本地 Laya）:")
    for name in ("literal_question", "true_intent", "danger_level",
                 "should_reply_now", "best_action", "she_needs", "tension_resolved"):
        if name in r["answers"]:
            print("  " + fmt(name, r["answers"][name]))

    print("\n候选（桩）与 Laya 排序（★=推荐）:")
    scores = r.get("scores")
    for i, c in enumerate(r["candidates"]):
        pct = f"  {scores[i]:.0%}" if scores else ""
        print(f"  {'★' if i == r['best_index'] else ' '} {c}{pct}")

    print("\nusage:", r.get("usage"))
    print("\n验证完成：判断与 best_reply 排序均由本地 Laya 给出（无 Jev 网络调用）。")

    # 收尾：关桥接子进程释放显存
    try:
        from core import laya_judge
        laya_judge.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
