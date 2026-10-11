# -*- coding: utf-8 -*-
"""从 D:\\wiki（Tom 的永久记忆中枢 / Obsidian vault）读取人格与职业属性，
注入到起草提示词，让回复带 Tom 的声音与背景。

只依赖标准库；读不到 D:\\wiki 时返回空串（不报错、不影响主流程）。
读取策略（用户选定）：启动时缓存，检测文件 mtime 变化自动重载——低延迟且近实时。

扫描范围（用户选定「全 wiki 扫描」）：Memory/preferences、Memory/plans、Memory/decisions 三个目录下的全部 .md。
为兼容 2.5B 本地小模型，总字符数封顶 _MAX_CHARS，超出按文件顺序截断并标注。
"""
from __future__ import annotations

import glob
import os
import re

WIKI_ROOT = r"D:\wiki"
MEMORY_DIR = os.path.join(WIKI_ROOT, "Memory")

# 全 wiki 扫描：人格 / 职业 / 当前项目 / 历史决策
_SCAN_DIRS = (
    os.path.join(MEMORY_DIR, "preferences"),
    os.path.join(MEMORY_DIR, "plans"),
    os.path.join(MEMORY_DIR, "decisions"),
)

# 提示词里塞多少（字符上限）。全 wiki 可能很长，2.5B 本地小模型也扛得住。
_MAX_CHARS = 4000
# 本地 2.5B 小模型对超长/带 markdown 装饰的文本容易空输出，给它单独更小的窗口 + 清洗。
_OLLAMA_MAX_CHARS = 1500

# 模块级缓存：{"mtimes": {path: float}, "text": str}
_cache: dict | None = None


def clean(md: str) -> str:
    """把 Obsidian markdown 洗成纯文本，避免 # 标题 / **粗体** / > 引用 / 链接 / emoji
    触发小模型 chat 模板异常导致空输出。保留中文语义。"""
    md = re.sub(r"#+\s*", "", md)
    md = re.sub(r"\*\*(.+?)\*\*", r"\1", md)
    md = re.sub(r"`([^`]+)`", r"\1", md)
    md = re.sub(r">\s?", "", md)
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)
    md = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF]", "", md)
    md = re.sub(r"[ \t]+", " ", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def _iter_md() -> list[str]:
    """三个目标目录下全部 .md，按路径排序（稳定顺序，便于 mtime 比对）。"""
    out: list[str] = []
    for d in _SCAN_DIRS:
        if os.path.isdir(d):
            out.extend(sorted(glob.glob(os.path.join(d, "*.md"))))
    return out


def _read_all() -> str:
    """拼接全部 .md 文本，单文件与总量都封顶，避免撑爆小模型上下文。"""
    parts: list[str] = []
    total = 0
    for p in _iter_md():
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read().strip()
        except OSError:
            continue
        if not txt:
            continue
        if total + len(txt) > _MAX_CHARS:
            room = _MAX_CHARS - total
            if room > 200:  # 还塞得下一小段就截一段，否则直接停
                txt = txt[:room] + "\n…（已截断）"
                parts.append(txt)
            break
        total += len(txt)
        parts.append(txt)
    return "\n\n---\n\n".join(parts)


def get_persona(clean_md: bool = False, max_chars: int | None = None) -> str:
    """返回 D:\\wiki 的人格/职业背景文本（已缓存，文件变更自动重载）。读不到返回空串。

    clean_md: True = 先洗掉 markdown 装饰（小模型友好，避免空输出）。
    max_chars: 非空 = 在清洗/截断后再裁到该长度（小模型单独更小的窗口）。
    """
    global _cache
    files = _iter_md()
    mtimes: dict[str, float] = {}
    try:
        for p in files:
            mtimes[p] = os.path.getmtime(p)
    except OSError:
        mtimes = {}
    # 文件集合与各自 mtime 都没变 → 直接返回缓存
    if _cache is not None and _cache["mtimes"] == mtimes:
        text = _cache["text"]
    else:
        text = _read_all()
        _cache = {"mtimes": mtimes, "text": text}
    if clean_md:
        text = clean(text)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + "\n…（已截断）"
    return text


if __name__ == "__main__":
    # 自测：打印扫描到的文件数与人格文本规模（不联网、不写文件）
    files = _iter_md()
    text = get_persona()
    print(f"[wiki_profile] 扫描目录: {_SCAN_DIRS}")
    print(f"[wiki_profile] 命中 .md 文件数: {len(files)}")
    for f in files:
        print(f"  - {f}")
    print(f"[wiki_profile] 人格文本字符数: {len(text)}")
    print("---- 预览（前 600 字）----")
    print(text[:600])
