# -*- coding: utf-8 -*-
"""直接测 core.draft.draft_candidates（provider=ollama），绕开 Laya 排序，看真实长 SYSTEM + 清洗 persona
是否稳定出字。本地，不联网。跑 3 次统计成功率。"""
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
    ok = 0
    for i in range(3):
        try:
            out = draft.draft_candidates(MESSAGES, "合作伙伴", provider="ollama",
                                         style="直接、快节奏、中文混粤语", persona=None)
        except Exception as e:
            print(f"  第{i+1}次 抛错: {type(e).__name__}: {e}")
            continue
        print(f"  第{i+1}次 候选 {len(out)}: {out}")
        if out:
            ok += 1
    print(f"\n成功 {ok}/3 次（本地 2.5B 偶发空输出属模型能力，非接线）")


if __name__ == "__main__":
    main()
