"""关键词筛选：探索工具，不参与主题建模；输出至 output/explore/。"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase1.config import ROOT


@dataclass
class KeywordFilterConfig:
    out_name: str
    keywords: list[str] | None = None
    lexicon_csv: Path | None = None
    lexicon_category: str | None = None
    all_categories: bool = False
    match_mode: str = "substring"  # substring | jieba_token | regex
    case_sensitive: bool = False
    input_csv: Path = ROOT / "output" / "phase1" / "data" / "clean_comments_unified.csv"
    out_root: Path = ROOT / "output" / "explore"
    sample_per_keyword: int = 50
    snippet_window: int = 40


def _load_lexicon_terms(path: Path, category: str | None) -> list[tuple[str, str]]:
    """返回 [(keyword, category_or_label), ...]"""
    df = pd.read_csv(path)
    term_col = "term" if "term" in df.columns else None
    if term_col is None:
        raise ValueError("lexicon CSV 需含 term 列")
    cat_col = "category" if "category" in df.columns else ("relation_type" if "relation_type" in df.columns else None)
    if cat_col is None:
        raise ValueError("lexicon CSV 需含 category 或 relation_type 列")
    rows = []
    for _, r in df.iterrows():
        cat = str(r[cat_col]).strip()
        term = str(r[term_col]).strip()
        if not term:
            continue
        if category is not None and cat != category:
            continue
        rows.append((term, cat))
    return rows


_JIEBA_INSTALLED = False


def _ensure_jieba() -> Any:
    """jieba_token 模式按需加载。"""
    global _JIEBA_INSTALLED
    import jieba  # type: ignore

    if not _JIEBA_INSTALLED:
        user_dict = ROOT / "config" / "topic_modeling" / "domain_user_dict.txt"
        if user_dict.is_file():
            jieba.load_userdict(str(user_dict))
        _JIEBA_INSTALLED = True
    return jieba


def _match(text: str, kw: str, mode: str, case_sensitive: bool) -> bool:
    t = text if case_sensitive else text.casefold()
    k = kw if case_sensitive else kw.casefold()
    if mode == "substring":
        return k in t
    if mode == "regex":
        return bool(re.search(kw, text))
    if mode == "jieba_token":
        jb = _ensure_jieba()
        toks = list(jb.cut(t, HMM=True))
        return k in toks
    raise ValueError(mode)


def _snippet(text: str, kw: str, window: int) -> str:
    tl = text
    kl = kw if kw else ""
    pos = tl.find(kl)
    if pos < 0:
        pos = tl.casefold().find(kl.casefold())
    if pos < 0:
        return text[: window * 2]
    a = max(0, pos - window)
    b = min(len(text), pos + len(kw) + window)
    frag = text[a:b]
    return ("…" if a > 0 else "") + frag + ("…" if b < len(text) else "")


def filter_by_keywords(cfg: KeywordFilterConfig) -> Path:
    cfg.out_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M")
    run_dir = cfg.out_root / f"{ts}_{cfg.out_name}"
    run_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(cfg.input_csv)
    n_in = len(df)

    hits_meta: list[tuple[str, str, str]] = []  # kw, source, category_label

    if cfg.keywords:
        for k in cfg.keywords:
            k = str(k).strip()
            if k:
                hits_meta.append((k, "manual_keywords", ""))
    elif cfg.lexicon_csv and cfg.all_categories:
        pairs = _load_lexicon_terms(cfg.lexicon_csv, None)
        for term, cat in pairs:
            hits_meta.append((term, "lexicon_all", cat))
    elif cfg.lexicon_csv and cfg.lexicon_category:
        pairs = _load_lexicon_terms(cfg.lexicon_csv, cfg.lexicon_category)
        for term, cat in pairs:
            hits_meta.append((term, "lexicon_category", cat))
    else:
        raise ValueError("指定 --keywords 或 (--lexicon + --category) 或 (--lexicon --all-categories)")

    hit_records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        content = str(row.get("content", ""))
        matched_kws: list[str] = []
        sources: list[str] = []
        for kw, src, lcat in hits_meta:
            if _match(content, kw, cfg.match_mode, cfg.case_sensitive):
                matched_kws.append(kw)
                sources.append(f"{src}:{lcat}" if lcat else src)
        if matched_kws:
            hit_records.append(
                {
                    "comment_id": row.get("comment_id", ""),
                    "帖子id": row.get("帖子id", ""),
                    "post_category": row.get("post_category", ""),
                    "comment": content,
                    "hit_keywords": "|".join(matched_kws),
                    "match_source": "|".join(sources),
                    "matched_snippet": _snippet(content, matched_kws[0], cfg.snippet_window),
                }
            )

    hits_df = pd.DataFrame(hit_records)
    hits_df.to_csv(run_dir / "hits.csv", index=False)

    # summary.md
    summary_lines = [
        f"# 关键词筛选摘要 `{cfg.out_name}`",
        "",
        f"- 输入行数: {n_in}",
        f"- 命中行数: {len(hits_df)}",
        f"- 命中率: {len(hits_df) / n_in:.4f}" if n_in else "",
        "",
        "## 按 post_category",
    ]
    if len(hits_df):
        vc = hits_df["post_category"].fillna("").value_counts()
        for k, v in vc.head(20).items():
            summary_lines.append(f"- {k}: {v}")
    (run_dir / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    # samples.md
    rng = random.Random(42)
    sample_lines = ["# 抽样预览", ""]
    kw_groups: dict[str, list[pd.Series]] = {}
    for _, r in hits_df.iterrows():
        for kw in str(r["hit_keywords"]).split("|"):
            kw_groups.setdefault(kw, []).append(r)
    for kw, rows in sorted(kw_groups.items()):
        sample_lines.append(f"## {kw}")
        rows_list = rows[: cfg.sample_per_keyword]
        if len(rows) > cfg.sample_per_keyword:
            rows_list = rng.sample(rows, cfg.sample_per_keyword)
        for r in rows_list:
            sample_lines.append(f"- {r['matched_snippet']}")
        sample_lines.append("")

    (run_dir / "samples.md").write_text("\n".join(sample_lines), encoding="utf-8")

    payload = {
        "out_name": cfg.out_name,
        "input_csv": str(cfg.input_csv),
        "match_mode": cfg.match_mode,
        "n_input": n_in,
        "n_hits": len(hits_df),
        "keywords_meta": [{"kw": a[0], "src": a[1], "cat": a[2]} for a in hits_meta[:500]],
    }
    (run_dir / "config.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return run_dir


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, required=True, help="输出子目录名")
    ap.add_argument("--keywords", type=str, default=None, help="逗号分隔关键词")
    ap.add_argument("--lexicon", type=str, default=None)
    ap.add_argument("--category", type=str, default=None)
    ap.add_argument("--all-categories", action="store_true")
    ap.add_argument("--input-csv", type=str, default=str(KeywordFilterConfig.input_csv))
    ap.add_argument(
        "--match-mode",
        type=str,
        default="substring",
        choices=["substring", "jieba_token", "regex"],
    )
    args = ap.parse_args()

    cfg = KeywordFilterConfig(
        out_name=args.out,
        keywords=[k.strip() for k in args.keywords.replace("，", ",").split(",") if k.strip()]
        if args.keywords
        else None,
        lexicon_csv=Path(args.lexicon) if args.lexicon else None,
        lexicon_category=args.category,
        all_categories=args.all_categories,
        input_csv=Path(args.input_csv),
        match_mode=args.match_mode,
    )
    p = filter_by_keywords(cfg)
    print(p)


if __name__ == "__main__":
    main()
