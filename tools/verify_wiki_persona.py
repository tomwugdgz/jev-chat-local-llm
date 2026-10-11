# -*- coding: utf-8 -*-
"""验证 Request 3 的 (a) 部分：D:/wiki 人格接入起草提示。

不联网：
  1) core.wiki_profile.get_persona() 能读到 D:\wiki 的真实人格/职业文本（变更自动重载）。
  2) core.draft.draft_candidates 把 persona 注入到喂给草稿模型的 user 提示里
     （monkeypatch chat 抓提示，不真发请求）。

跑法（系统 Python 3.13，已装 openai + laya_bridge）：
  py tools/verify_wiki_persona.py
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import core.wiki_profile as wp
import core.draft as draft


def test_loader():
    text = wp.get_persona()
    files = wp._iter_md()
    print(f"[1] 命中 .md 文件数: {len(files)}")
    for f in files:
        print(f"    - {f}")
    print(f"[1] 人格文本字符数: {len(text)}")
    assert text.strip(), "D:\\wiki 人格文本为空——读不到 vault？"
    # 变更自动重载：改 mtime 后应重读（这里只验证 mtime 比对逻辑不报错）
    assert isinstance(wp._cache, dict) and "mtimes" in wp._cache
    print("[1] wiki_profile 加载 OK\n")
    return text


def test_injection():
    captured = {}

    def fake_chat(*args, **kwargs):
        # chat(protocol, base, key, model, system, turns, ...)
        captured["turns"] = args[5] if len(args) > 5 else kwargs.get("messages")
        return '["好", "在的", "咋啦"]'

    orig = draft.chat
    draft.chat = fake_chat
    try:
        # 不传 persona → 自动从 D:\wiki 读
        out = draft.draft_candidates(
            [("her", "在吗"), ("me", "嗯")], "friends",
            provider="ollama", persona=None)
    finally:
        draft.chat = orig

    assert out, "起草无候选"
    turns = captured.get("turns") or []
    user_prompt = turns[-1] if turns else ""
    assert "你是谁" in user_prompt, "提示里没有人格段"
    # 自动读取到的真实人格文本应出现在提示里
    assert wp.get_persona()[:40] in user_prompt, "自动读取的 wiki 文本未注入"
    print(f"[2] 起草候选数: {len(out)} -> {out}")
    print(f"[2] 提示长度: {len(user_prompt)} 字符；含『你是谁』人格段: 是")
    print("[2] 人格注入 OK")


if __name__ == "__main__":
    test_loader()
    test_injection()
    print("\nverify_wiki_persona: ALL OK")
