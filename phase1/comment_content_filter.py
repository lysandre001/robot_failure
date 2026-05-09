"""可配置评论内容噪音过滤：纯 emoji、仅 @、重复短片段等。规则见 config/topic_modeling/comment_content_filter.json。"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from phase1.preprocess import normalize_text

COMMENT_CONTENT_FILTER_JSON = (
    Path(__file__).resolve().parents[1] / "config" / "topic_modeling" / "comment_content_filter.json"
)


def load_comment_filter_rules(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else COMMENT_CONTENT_FILTER_JSON
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _is_emoji_or_joiner_codepoint(ch: str) -> bool:
    o = ord(ch)
    if ch in "\u200d\uFE0F\uFE0E\u20E3":
        return True
    if 0x1F3FB <= o <= 0x1F3FF:
        return True
    return (
        0x1F300 <= o <= 0x1FAFF
        or 0x2600 <= o <= 0x27BF
        or 0x1F600 <= o <= 0x1F64F
        or 0x1F900 <= o <= 0x1F9FF
        or 0x1FA70 <= o <= 0x1FAFF
        or 0x1F1E6 <= o <= 0x1F1FF
        or 0x20D0 <= o <= 0x20FF
    )


def is_pure_emoji_text(text: str) -> bool:
    """是否可视为「纯 emoji」（允许空白）。"""
    t = "".join(str(text).split())
    if not t:
        return False
    for ch in t:
        if _is_emoji_or_joiner_codepoint(ch):
            continue
        if "\u4e00" <= ch <= "\u9fff":
            return False
        if ch.isascii() and (ch.isalnum() or ch in "_"):
            return False
        return False
    return True


def _compile_mention_pattern(rules: dict[str, Any]) -> re.Pattern[str]:
    pat = rules.get("mention_regex") or r"[@＠][^\s@＠]+"
    return re.compile(pat)


def substantive_after_stripping_mentions(text: str, rules: dict[str, Any]) -> str:
    om = rules
    mention_re = _compile_mention_pattern(om)
    t = mention_re.sub("", str(text))
    t = t.strip()
    strip_set = set(om.get("strip_chars_not_substance") or "")
    if strip_set:
        t = "".join(c for c in t if c not in strip_set)
    return t.strip()


def is_only_mentions(text: str, rules: dict[str, Any]) -> bool:
    if not str(text).strip():
        return False
    return len(substantive_after_stripping_mentions(text, rules)) == 0


def _minimal_repeating_unit(text: str, max_period: int) -> tuple[int, int] | None:
    """若整串由长度为 p 的子串重复组成，返回 (p, 重复次数)；否则 None。取最小满足条件的 p。"""
    s = str(text)
    n = len(s)
    if n < 2:
        return None
    upper = min(max_period, n)
    for p in range(1, upper + 1):
        if n % p != 0:
            continue
        k = n // p
        if k < 2:
            continue
        if s[:p] * k == s:
            return p, k
    return None


def is_repeated_fragment_noise(text: str, rules: dict[str, Any]) -> bool:
    rf = rules
    if not rf.get("enabled", True):
        return False
    max_p = int(rf.get("max_period_chars", 6))
    min_rep = int(rf.get("min_repeat_count", 3))
    min_total = int(rf.get("min_total_chars", 4))
    s = "".join(str(text).split())
    if len(s) < min_total:
        return False
    info = _minimal_repeating_unit(s, max_p)
    if info is None:
        return False
    _p, k = info
    return k >= min_rep


def classify_comment_noise(text: str, rules: dict[str, Any]) -> str | None:
    """
    若应排除则返回原因键，否则 None。
    优先级：pure_emoji -> only_mentions -> repeated_fragment（先判语义更单纯的类）。
    """
    t = normalize_text(text)
    if not t:
        return None

    pe = rules.get("pure_emoji") or {}
    if pe.get("enabled", True) and is_pure_emoji_text(t):
        return "pure_emoji"

    om = rules.get("only_mentions") or {}
    if om.get("enabled", True) and is_only_mentions(t, om):
        return "only_at_mentions"

    rf = rules.get("repeated_fragment") or {}
    if rf.get("enabled", True) and is_repeated_fragment_noise(t, rf):
        return "repeated_fragment"

    return None


def apply_content_noise_rules(
    df: pd.DataFrame,
    rules: dict[str, Any],
    *,
    content_col: str = "content",
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """
    返回 (保留行, 排除行带 reason 列, 汇总统计 dict)。
    """
    work = df.copy()
    work[content_col] = work[content_col].map(normalize_text)
    reasons = [classify_comment_noise(t, rules) for t in work[content_col]]
    work["_noise_rule"] = reasons
    dropped = work[work["_noise_rule"].notna()].copy()
    kept = work[work["_noise_rule"].isna()].copy()
    for x in (kept, dropped):
        x.drop(columns=["_noise_rule"], errors="ignore", inplace=True)
    dropped_reason = work[work["_noise_rule"].notna()].copy()
    dropped_reason.rename(columns={"_noise_rule": "exclude_reason"}, inplace=True)

    n = len(df)
    summary = {
        "n_input": int(n),
        "n_kept": int(len(kept)),
        "n_dropped": int(len(dropped_reason)),
        "by_reason": {k: int(v) for k, v in Counter(dropped_reason["exclude_reason"]).most_common()},
    }
    return kept, dropped_reason, summary


def run_filter_report(
    input_csv: Path,
    rules_path: Path | None = None,
    out_summary: Path | None = None,
    out_dropped: Path | None = None,
    *,
    sample_per_reason: int | None = None,
) -> dict[str, Any]:
    """读 CSV，应用规则，写汇总 JSON 与排除行 CSV（默认导出全部被排除的行）。"""
    rules = load_comment_filter_rules(rules_path)
    df = pd.read_csv(input_csv)
    if "content" not in df.columns:
        raise ValueError("CSV 需含 content 列")
    _, dropped, summary = apply_content_noise_rules(df, rules)

    root = Path(__file__).resolve().parents[1]
    if out_summary is None:
        out_summary = root / "output" / "phase1" / "comment_content_filter_report.json"
    if out_dropped is None:
        out_dropped = root / "output" / "phase1" / "comment_content_filter_dropped.csv"

    out_summary.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rules_file": str(rules_path or COMMENT_CONTENT_FILTER_JSON),
        "input_csv": str(input_csv),
        "dropped_csv": str(out_dropped),
        **summary,
    }
    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    out_export = dropped
    if sample_per_reason is not None and sample_per_reason > 0:
        parts = [
            g.head(sample_per_reason) for _, g in out_export.groupby("exclude_reason", sort=False)
        ]
        out_export = pd.concat(parts, ignore_index=True) if parts else dropped.head(0)

    sort_cols = [c for c in ("exclude_reason", "comment_id") if c in out_export.columns]
    if sort_cols:
        out_export = out_export.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
    out_export.to_csv(out_dropped, index=False)

    return payload


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="评论噪音规则：统计 + 排除行全量 CSV")
    ap.add_argument(
        "--input-csv",
        type=str,
        default=str(
            Path(__file__).resolve().parents[1]
            / "output"
            / "phase1"
            / "data"
            / "clean_comments_unified_before_filter.csv"
        ),
    )
    ap.add_argument("--rules", type=str, default=str(COMMENT_CONTENT_FILTER_JSON))
    ap.add_argument(
        "--out-dropped",
        type=str,
        default=None,
        help="排除行输出路径（默认 output/phase1/comment_content_filter_dropped.csv）",
    )
    ap.add_argument(
        "--sample-per-reason",
        type=int,
        default=None,
        metavar="N",
        help="若指定则每种原因最多保留 N 条（调试用；默认全量）",
    )
    args = ap.parse_args()
    rep = run_filter_report(
        Path(args.input_csv),
        rules_path=Path(args.rules),
        out_dropped=Path(args.out_dropped) if args.out_dropped else None,
        sample_per_reason=args.sample_per_reason,
    )
    print(json.dumps(rep, ensure_ascii=False, indent=2))
