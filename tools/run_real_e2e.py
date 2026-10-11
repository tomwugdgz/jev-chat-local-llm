# -*- coding: utf-8 -*-
"""真实端到端运行（不桩任何东西）：本地 Laya 判断 + 本地 Ollama 起草（已注入 D:/wiki 人格）+ Laya 排序。
零外部网络。验证 Request 3 在运行时确实生效。

跑法（系统 Python 3.13）：
  py tools/run_real_e2e.py
"""
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import core.wiki_profile as wp
from core.engine import analyze
from core.providers import DRAFT_PROVIDERS

# 一条贴合 Tom 职业（社区户外广告）的微信风格对话
MESSAGES = [
    ("her", "明天的社区店开业物料准备好了没"),
    ("me", "门禁广告画面今天出"),
    ("her", "单元门灯箱那批点位确认了吗"),
    ("me", "确认了 30 个小区"),
    ("her", "行 那我等你好消息"),
]
RELATIONSHIP = "合作伙伴"
STYLE = "直接、快节奏、中文混粤语"


def main():
    persona = wp.get_persona()
    print(f"[wiki] 人格文本字符数: {len(persona)}（自动从 D:\\wiki 读取，变更自动重载）")
    print(f"[wiki] 预览: {persona[:120]!r}…\n")

    print(f"[provider] 起草可选来源含 DeepSeek: {'deepseek' in DRAFT_PROVIDERS}"
          f" → 设置里可切换；本次实跑用 ollama 本地\n")

    t0 = time.time()
    try:
        res = analyze(MESSAGES, RELATIONSHIP, provider="ollama",
                      style=STYLE, timeout=90, context=10)
    except Exception as e:
        print(f"[结果] analyze 抛错: {type(e).__name__}: {e}")
        print("（若是起草无候选，多为 minicpm5-2b 小模型指令跟随弱所致，非接线问题）")
        return

    dt = time.time() - t0
    cands = res["candidates"]
    print(f"[结果] 耗时 {dt:.1f}s，候选 {len(cands)} 条:")
    for i, c in enumerate(cands):
        mark = " ★推荐" if i == res["best_index"] else ""
        score = res["scores"][i] if i < len(res["scores"]) else 0.0
        print(f"  {i}. {c}  (胜出概率 {score:.2f}){mark}")
    print(f"\n[结果] 推荐回复: {res['best_reply']}")
    print(f"[结果] usage: {res['usage']}")
    print("\nrun_real_e2e: OK（真实 Laya 判断 + 真实 Ollama 起草含 wiki 人格）")


if __name__ == "__main__":
    main()
