# -*- coding: utf-8 -*-
"""诊断 minicpm5-2b-32k 在 Ollama 下的产出能力：分别用「极简提示」和「完整 SYSTEM+wiki 人格」两种负载测，
看空输出是模型本身问题还是提示太长/格式问题。不联网（全本地）。"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.llm import chat
from core.providers import DRAFT_PROVIDERS
from core.draft import SYSTEM

spec = DRAFT_PROVIDERS["ollama"]
KW = dict(protocol=spec.protocol, base=spec.base, key="ollama",
          model=spec.default, extra_body=spec.extra(False), headers=spec.headers,
          timeout=60)


def probe(label, system, user, temperature=1.2, max_tokens=400):
    print(f"\n===== {label} =====")
    try:
        out = chat(spec.protocol, spec.base, "ollama", spec.default, system, [user],
                   temperature=temperature, max_tokens=max_tokens, thinking=False,
                   extra_body=spec.extra(False), headers=spec.headers, timeout=60)
    except Exception as e:
        print(f"  抛错: {type(e).__name__}: {e}")
        return
    print(f"  返回长度: {len(out)}")
    print(f"  内容预览: {out[:300]!r}")


if __name__ == "__main__":
    # 1) 极简：几乎不可能失败
    probe("A 极简提示", "你是中文聊天助手。", "用一句中文回复：你好",
          temperature=0.8, max_tokens=64)
    # 2) 完整 SYSTEM（无 wiki 人格）
    probe("B 完整 SYSTEM", SYSTEM, "对方说「在吗」，写 3 条 me 可能回的消息，JSON 数组。")
    # 3) 完整 SYSTEM + wiki 人格（贴近真实负载）
    import core.wiki_profile as wp
    persona = wp.get_persona()
    user_full = ("对方说「在吗」。写 3 条 me 可能回的消息，JSON 数组，每条一句。\n\n"
                 "你是谁（me 真实身份背景，自然贴合）：\n" + persona)
    probe("C 完整 SYSTEM + wiki 人格", SYSTEM, user_full)
