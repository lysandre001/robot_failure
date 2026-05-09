# 注：此模块属于 lexicon 探索阶段产物。
# - 新主题建模流程（phase1/topic_modeling.py）不依赖。
# - 关键词筛选工具（phase1/keyword_filter.py）只复用 ROLE_PATTERNS / 词典 CSV，不调用 apply_lexicons。
# - 如需把 lexicon 当判别器使用，先做 IRR 验证。
"""步骤 B：从评论文本抽取词典命中、玩梗特征、共现与 n-gram。"""
from __future__ import annotations

import re
from collections import Counter

import pandas as pd

from phase1.lexicons import BOUNDARY, EMOJI_RE, PERSONHOOD, ROLE_PATTERNS, XHS_BRACKET

try:
    import jieba  # type: ignore
except ImportError:  # pragma: no cover
    jieba = None


def count_hits(text: str, terms: list[str]) -> int:
    if not text:
        return 0
    return sum(1 for t in terms if t and t in text)


def score_roles(text: str) -> dict[str, int]:
    return {k: count_hits(text, v) for k, v in ROLE_PATTERNS.items()}


def score_personhood(text: str) -> dict[str, int]:
    return {k: count_hits(text, v) for k, v in PERSONHOOD.items()}


def score_boundary(text: str) -> dict[str, int]:
    return {k: count_hits(text, v) for k, v in BOUNDARY.items()}


def meme_score(text: str) -> dict:
    if not text:
        return {"emoji_count": 0, "xhs_tag_count": 0, "template_style": False, "ha_repeat": 0}
    emojis = EMOJI_RE.findall(text)
    tags = XHS_BRACKET.findall(text)
    m = re.search(r"您是.{0,20}，(它|他|她|您们|你们).{0,30}", text)
    ha = len(re.findall(r"哈{2,}", text))
    return {
        "emoji_count": len(emojis),
        "xhs_tag_count": len(tags),
        "template_style": bool(m),
        "ha_repeat": ha,
    }


def top_ngrams_char(texts: list[str], n: int = 4, top: int = 30) -> list[tuple[str, int]]:
    cnt: Counter[str] = Counter()
    for t in texts:
        t = re.sub(r"\s+", "", t)
        if len(t) < n:
            continue
        for i in range(len(t) - n + 1):
            seg = t[i : i + n]
            if seg.isdigit() or seg.isspace():
                continue
            cnt[seg] += 1
    return cnt.most_common(top)


def cooccur_tokens(
    texts: list[str],
    anchors: set[str],
    window: int = 6,
    top: int = 40,
) -> dict[str, list[tuple[str, int]]]:
    out: dict[str, Counter[str]] = {a: Counter() for a in anchors}
    for text in texts:
        if jieba is not None:
            toks = list(jieba.cut(text))
        else:
            # 无 jieba 时的兜底分词（字符级），仅用于保持流程可运行
            toks = [ch for ch in str(text) if not ch.isspace()]
        if not toks:
            continue
        for i, w in enumerate(toks):
            if w not in anchors:
                continue
            lo = max(0, i - window)
            hi = min(len(toks), i + window + 1)
            for j in range(lo, hi):
                if j == i:
                    continue
                tw = toks[j]
                if len(tw) < 2 or tw in anchors:
                    continue
                out[w][tw] += 1
    return {a: c.most_common(top) for a, c in out.items()}


def apply_lexicons(u: pd.DataFrame) -> pd.DataFrame:
    contents = u["content"].fillna("").astype(str).tolist()
    rows = []
    for t in contents:
        rows.append(
            {
                **{f"role_{k}": v for k, v in score_roles(t).items()},
                **{f"ph_{k}": v for k, v in score_personhood(t).items()},
                **{f"bd_{k}": v for k, v in score_boundary(t).items()},
                **meme_score(t),
            }
        )
    ext = pd.DataFrame(rows)
    return pd.concat([u.reset_index(drop=True), ext], axis=1)
