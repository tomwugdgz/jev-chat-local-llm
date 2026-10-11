# -*- coding: utf-8 -*-
"""第二次诊断：针对 minicpm5-2b 在 Ollama 下空输出的两种可能根因逐一验证。
  (1) 思考字段吞掉内容 → 加 extra_body={'think': False} 看 content 是否回来。
  (2) 长提示/高温度不稳定 → 精简 few-shot 提示 + 关思考 + 低温度，看能否稳定出 3 条 JSON。
全部本地，不联网。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.llm import chat
from core.providers import DRAFT_PROVIDERS
from core.draft import _parse_candidates

spec = DRAFT_PROVIDERS["ollama"]


def call(system, user, temperature, max_tokens, extra_body):
    try:
        out = chat(spec.protocol, spec.base, "ollama", spec.default, system,
                   [user] if not isinstance(user, list) else user,
                   temperature=temperature, max_tokens=max_tokens, thinking=False,
                   extra_body=extra_body, headers=spec.headers, timeout=90)
    except Exception as e:
        return f"<ERR {type(e).__name__}: {e}>"
    return out


def report(label, out):
    if out.startswith("<ERR"):
        print(f"  [{label}] 调用失败: {out}")
        return
    try:
        cands = _parse_candidates(out)
    except Exception:
        cands = []
    print(f"  [{label}] 原文长 {len(out)} → 可解析候选 {len(cands)}: {cands}")


# 精简 few-shot system（小模型友好）
SMALL_SYS = ("你是 Tom，正在微信里回消息，不是助手。对方刚说了话。\n"
             "只输出一个 JSON 数组，恰好 3 个字符串，每条一句中文，句尾别加句号。\n"
             '示例: ["好", "在的", "咋啦"]')

USER_FULL = ("relationship: 合作伙伴\n\n对话原文:\nher: 明天的社区店开业物料准备好了没\n"
             "me: 门禁广告画面今天出\nher: 单元门灯箱那批点位确认了吗\n"
             "me: 确认了 30 个小区\nher: 行 那我等你好消息\n\n输出 3 条候选，JSON 数组。")

import core.wiki_profile as wp
PERSONA = wp.get_persona()
USER_PERSONA = USER_FULL + ("\n\n你是谁（me 真实身份背景，自然贴合）：\n" + PERSONA)


def main():
    print("== T1：完整 SYSTEM + think:False + 完整 persona（4000字）==")
    report("T1 完整persona", call(
        "你是「me」本人，正在聊天里打字。写 3 条 me 接下来可能发的消息，JSON 数组，每条一句。",
        USER_PERSONA, 1.2, 400, {"think": False}))

    print("\n== T2：完整 SYSTEM + think:False + 截断 persona（前 600 字）==")
    report("T2 截断persona", call(
        "你是「me」本人，正在聊天里打字。写 3 条 me 接下来可能发的消息，JSON 数组，每条一句。",
        USER_FULL + "\n\n你是谁（me 真实身份背景，自然贴合）：\n" + PERSONA[:600],
        1.2, 400, {"think": False}))

    print("\n== T3：完整 SYSTEM + think:False + 无 persona（对照）==")
    report("T3 无persona", call(
        "你是「me」本人，正在聊天里打字。写 3 条 me 接下来可能发的消息，JSON 数组，每条一句。",
        USER_FULL, 1.2, 400, {"think": False}))


if __name__ == "__main__":
    main()
