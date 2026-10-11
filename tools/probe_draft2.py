# -*- coding: utf-8 -*-
"""抓 draft_candidates 实际发给 Ollama 的 (system, user) 与原始返回，定位空输出环节。本地。"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import core.draft as draft

MESSAGES = [
    ("her", "明天的社区店开业物料准备好了没"),
    ("me", "门禁广告画面今天出"),
    ("her", "单元门灯箱那批点位确认了吗"),
    ("me", "确认了 30 个小区"),
    ("her", "行 那我等你好消息"),
]


def main():
    orig = draft.chat
    captured = {}

    def spy(*a, **k):
        captured["system"] = a[4]
        captured["user"] = a[5][-1] if a[5] else ""
        raw = orig(*a, **k)
        print("=== 实际发出 ===")
        print(f"[system] 长 {len(captured['system'])}")
        print(f"[user]   长 {len(captured['user'])}")
        print(f"[user预览] {captured['user'][:400]!r}")
        print(f"[raw返回] {raw[:400]!r}")
        # 返回可解析假数据，避免 _sanitize 抛错中断观察
        return '["好", "在的", "咋啦"]'

    draft.chat = spy
    try:
        out = draft.draft_candidates(MESSAGES, "合作伙伴", provider="ollama",
                                     style="直接、快节奏、中文混粤语", persona=None)
    finally:
        draft.chat = orig
    print("\ncandidates:", out)


if __name__ == "__main__":
    main()
