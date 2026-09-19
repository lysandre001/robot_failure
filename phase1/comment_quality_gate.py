"""评论级纳入门控：有无可分析语义。不含 sklearn 英文功能词表。"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from phase1.comment_content_filter import COMMENT_CONTENT_FILTER_JSON, load_comment_filter_rules
from phase1.topic_lda import clean_text, tokenize_text, _setup_tokenizer

GATE_JSON = (
    Path(__file__).resolve().parents[1] / "config" / "topic_modeling" / "comment_quality_gate.json"
)
_HAN_RE = re.compile(r"[\u4e00-\u9fff]")
_LETTER_RE = re.compile(r"[a-z]{2,}")


def load_quality_gate_rules(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else GATE_JSON
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _boilerplate_token_set(content_filter: dict[str, Any] | None = None) -> set[str]:
    rules = content_filter if content_filter is not None else load_comment_filter_rules(
        COMMENT_CONTENT_FILTER_JSON
    )
    eb = rules.get("english_boilerplate") or {}
    out: set[str] = set()
    for phrase in eb.get("exact_match_lower") or []:
        for tok in re.findall(r"[a-z]{2,}", str(phrase).casefold()):
            out.add(tok)
    return out


def comment_quality_metrics(
    text: str,
    gate_stopwords: set[str],
    *,
    boilerplate: set[str] | None = None,
) -> dict[str, Any]:
    nt = unicodedata.normalize("NFC", str(text or "")).strip()
    cleaned = clean_text(nt)
    letter_tokens = _LETTER_RE.findall(cleaned)
    bp = boilerplate if boilerplate is not None else _boilerplate_token_set()
    en_content = [w for w in letter_tokens if w not in bp]
    _setup_tokenizer("jieba")
    zh_tokens = tokenize_text(nt, tokenizer="jieba", stopwords=gate_stopwords)
    n_han = len(_HAN_RE.findall(nt))
    return {
        "char_len": len(nt),
        "n_han": n_han,
        "n_zh_content": len(zh_tokens),
        "n_letter": len(letter_tokens),
        "n_en_content": len(en_content),
        "effective_token_count": max(len(zh_tokens), len(letter_tokens)),
    }


def passes_comment_quality_gate(
    text: str,
    gate_stopwords: set[str],
    *,
    rules: dict[str, Any] | None = None,
    boilerplate: set[str] | None = None,
) -> tuple[bool, dict[str, Any]]:
    """
    中文：内容词 ≥2 或（含汉字且 char_len ≥8）。
    英文：字母词 ≥4 或 去套话后内容词 ≥2。
    中英混合：任一路径通过即可。
    """
    cfg = rules if rules is not None else load_quality_gate_rules()
    m = comment_quality_metrics(text, gate_stopwords, boilerplate=boilerplate)
    zh_cfg = cfg.get("zh") or {}
    en_cfg = cfg.get("en") or {}
    zh_ok = m["n_zh_content"] >= int(zh_cfg.get("min_content_tokens", 2)) or (
        m["n_han"] > 0 and m["char_len"] >= int(zh_cfg.get("min_chars_alternative", 8))
    )
    en_ok = m["n_letter"] >= int(en_cfg.get("min_letter_tokens", 4)) or m["n_en_content"] >= int(
        en_cfg.get("min_content_tokens", 2)
    )
    if m["n_han"] > 0 and m["n_letter"] > 0:
        ok = zh_ok or en_ok
    elif m["n_han"] > 0:
        ok = zh_ok
    else:
        ok = en_ok
    return ok, m
