# -*- coding: utf-8 -*-
"""第三次诊断：根因②——raw wiki markdown 让 minicpm5 空输出。验证「清洗 markdown（去 #/**/>/emoji、
折叠空白）后的 persona」能否被 2.5B 小模型消化。全部本地。"""
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.llm import chat
from core.providers import DRAFT_PROVIDERS
from core.draft import _parse_candidates
import core.wiki_profile as wp

spec = DRAFT_PROVIDERS["ollama"]


def clean(md: str) -> str:
    md = re.sub(r"#+\s*", "", md)
    md = re.sub(r"\*\*([^*]+)\*\*", r"\1", md)
    md = re.sub(r"`([^`]+)`", r"\1", md)
    md = re.sub(r">\s?", "", md)
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)
    md = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF]", "", md)
    md = re.sub(r"[ \t]+", " ", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def call(system, user, extra_body):
    try:
        return chat(spec.protocol, spec.base, "ollama", spec.default, system, [user],
                    temperature=1.2, max_tokens=400, thinking=False,
                    extra_body=extra_body, headers=spec.headers, timeout=90)
    except Exception as e:
        return f"<ERR {type(e).__name__}: {e}>"


def report(label, out):
    if out.startswith("<ERR"):
        print(f"  [{label}] 调用失败: {out}")
        return
    try:
        cands = _parse_candidates(out)
    except Exception:
        cands = []
    print(f"  [{label}] 原文长 {len(out)} → 候选 {len(cands)}: {cands[:3]}")


RAW = wp.get_persona()
CLEAN = clean(RAW)
print(f"[clean] raw 长 {len(RAW)} → cleaned 长 {len(CLEAN)}")
print(f"[clean] 预览: {CLEAN[:160]!r}\n")

SYS = "你是「me」本人，正在聊天里打字。写 3 条 me 接下来可能发的消息，JSON 数组，每条一句。"
USER = ("relationship: 合作伙伴\n\n对话原文:\nher: 明天的社区店开业物料准备好了没\n"
        "me: 门禁广告画面今天出\nher: 单元门灯箱那批点位确认了吗\n"
        "me: 确认了 30 个小区\nher: 行 那我等你好消息")

print("== T4：think:False + 清洗后完整 persona ==")
report("T4 clean全量", call(SYS, USER + "\n\n你是谁（me 真实身份背景，自然贴合）：\n" + CLEAN,
                          {"think": False}))

print("\n== T5：think:False + 清洗后截断 800 字 ==")
report("T5 clean800", call(SYS, USER + "\n\n你是谁（me 真实身份背景，自然贴合）：\n" + CLEAN[:800],
                          {"think": False}))

print("\n== T6：think:False + 仅 tom-profile 清洗（职业/沟通风格核心）==")
# 只抽 preferences/tom-profile.md 那一份，最贴合「声音」
import glob, os as _os
tp = ""
for p in glob.glob(os.path.join(wp.MEMORY_DIR, "preferences", "tom-profile.md")):
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        tp = clean(f.read())
report("T6 tom-profile", call(SYS, USER + "\n\n你是谁（me 真实身份背景，自然贴合）：\n" + tp,
                          {"think": False}))
