#!/usr/bin/env python3
"""从 clean 表按帖抽取二级子评论数最多的 Top-N 一级评论（demo 浏览用）。"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from phase1.config import ROOT

DEFAULT_OUT_DIR = ROOT / "data" / "demo"
DEFAULT_TOP_N = 10
MAX_L2_SAMPLES = 3

DEFAULT_SOURCES: list[tuple[str, str, Path]] = [
    ("xhs", "merged", ROOT / "data" / "clean" / "xhs" / "merged" / "clean_comments_unified.csv"),
    (
        "tiktok",
        "2604-marathon",
        ROOT / "data" / "clean" / "tiktok" / "2604-marathon" / "clean_comments_unified.csv",
    ),
    (
        "tiktok",
        "2608-olympic",
        ROOT / "data" / "clean" / "tiktok" / "2608-olympic" / "clean_comments_unified.csv",
    ),
    (
        "douyin",
        "2608-olympic",
        ROOT / "data" / "clean" / "douyin" / "2608-olympic" / "clean_comments_unified.csv",
    ),
]

OUTPUT_COLS = [
    "platform",
    "source_batch",
    "帖子id",
    "帖子标题",
    "post_category",
    "rank_in_post",
    "comment_id",
    "n_l2_children",
    "like_count",
    "reply_count",
    "content",
    "comment_time",
    "location",
    "sample_l2_contents",
]


def _source_slug(platform: str, source_batch: str) -> str:
    return f"{platform}_{source_batch}"


def _sample_l2_texts(
    l2: pd.DataFrame,
    parent_id: str,
    *,
    max_samples: int = MAX_L2_SAMPLES,
) -> str:
    sub = l2[l2["parent_comment_id"].astype(str) == str(parent_id)]
    if sub.empty:
        return ""
    sub = sub.sort_values("like_count", ascending=False, na_position="last")
    parts = []
    for text in sub["content"].head(max_samples):
        if pd.isna(text):
            continue
        s = str(text).replace("|", "／").replace("\n", " ").strip()
        if s:
            parts.append(s)
    return " | ".join(parts)


def export_top_l2_by_post(
    input_csv: Path,
    *,
    platform: str,
    source_batch: str,
    top_n: int = DEFAULT_TOP_N,
) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(input_csv)
    if "platform" not in df.columns:
        df["platform"] = platform
    if "source_batch" not in df.columns:
        df["source_batch"] = source_batch
    df["source_batch"] = df["source_batch"].fillna(source_batch)
    df["platform"] = df["platform"].fillna(platform)

    df["comment_level"] = pd.to_numeric(df["comment_level"], errors="coerce")
    df = df[df["comment_level"].isin([1, 2])].copy()
    df["comment_level"] = df["comment_level"].astype(int)

    l1 = df[df["comment_level"] == 1].copy()
    l2 = df[df["comment_level"] == 2].copy()

    l2_counts = l2.groupby("parent_comment_id", dropna=False).size().rename("n_l2_children")
    l1 = l1.merge(l2_counts, left_on="comment_id", right_index=True, how="left")
    l1["n_l2_children"] = l1["n_l2_children"].fillna(0).astype(int)
    l1["like_count"] = pd.to_numeric(l1.get("like_count"), errors="coerce").fillna(0)

    l1 = l1.sort_values(
        ["帖子id", "n_l2_children", "like_count"],
        ascending=[True, False, False],
        kind="mergesort",
    )
    top = l1.groupby("帖子id", sort=False).head(top_n).copy()
    top["rank_in_post"] = top.groupby("帖子id").cumcount() + 1

    top["sample_l2_contents"] = top["comment_id"].map(
        lambda cid: _sample_l2_texts(l2, cid)
    )

    for col in OUTPUT_COLS:
        if col not in top.columns:
            top[col] = ""
    if "post_category" not in top.columns:
        top["post_category"] = "unknown"
    top["post_category"] = top["post_category"].fillna("unknown")

    out = top[OUTPUT_COLS].reset_index(drop=True)

    n_posts = int(df["帖子id"].nunique())
    n_l1 = len(l1)
    n_l1_with_l2 = int((l1["n_l2_children"] > 0).sum())
    summary = {
        "platform": platform,
        "source_batch": source_batch,
        "source_slug": _source_slug(platform, source_batch),
        "input_csv": str(input_csv.resolve()),
        "n_posts": n_posts,
        "n_l1_total": n_l1,
        "n_l1_with_l2": n_l1_with_l2,
        "pct_l1_with_l2": round(100.0 * n_l1_with_l2 / n_l1, 2) if n_l1 else 0.0,
        "n_rows_exported": len(out),
        "top_n": top_n,
    }
    return out, summary


def discover_sources(inventory_csv: Path | None = None) -> list[tuple[str, str, Path]]:
    inv_path = inventory_csv or (ROOT / "data" / "corpus_inventory.csv")
    if inv_path.is_file():
        inv = pd.read_csv(inv_path)
        sources: list[tuple[str, str, Path]] = []
        for _, row in inv.iterrows():
            p = Path(str(row["clean_comments_unified"]))
            if p.is_file():
                sources.append((str(row["platform"]), str(row["source_batch"]), p))
        if sources:
            return sources
    return [(p, b, path) for p, b, path in DEFAULT_SOURCES if path.is_file()]


def run_export(
    *,
    sources: list[tuple[str, str, Path]],
    out_dir: Path,
    top_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_parts: list[pd.DataFrame] = []
    summaries: list[dict] = []

    for platform, source_batch, input_csv in sources:
        part, summary = export_top_l2_by_post(
            input_csv,
            platform=platform,
            source_batch=source_batch,
            top_n=top_n,
        )
        slug = _source_slug(platform, source_batch)
        subdir = out_dir / slug
        subdir.mkdir(parents=True, exist_ok=True)
        part.to_csv(subdir / "top10_l2_by_post.csv", index=False, encoding="utf-8-sig")
        all_parts.append(part)
        summaries.append(summary)

    combined = pd.concat(all_parts, ignore_index=True) if all_parts else pd.DataFrame(columns=OUTPUT_COLS)
    summary_df = pd.DataFrame(summaries)

    combined.to_csv(out_dir / "top10_l2_by_post_all.csv", index=False, encoding="utf-8-sig")
    summary_df.to_csv(out_dir / "summary_by_source.csv", index=False, encoding="utf-8-sig")
    return combined, summary_df


def main() -> None:
    ap = argparse.ArgumentParser(description="每帖抽取 Top-N 高 L2 回复一级评论（demo）")
    ap.add_argument("--input", type=Path, default=None, help="单源 clean CSV；省略则处理全部已知源")
    ap.add_argument("--platform", type=str, default="xhs")
    ap.add_argument("--batch", type=str, default="merged", dest="source_batch")
    ap.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--inventory", type=Path, default=ROOT / "data" / "corpus_inventory.csv")
    args = ap.parse_args()

    if args.input is not None:
        part, summary = export_top_l2_by_post(
            args.input,
            platform=args.platform,
            source_batch=args.source_batch,
            top_n=args.top_n,
        )
        slug = _source_slug(args.platform, args.source_batch)
        subdir = args.out_dir / slug
        subdir.mkdir(parents=True, exist_ok=True)
        out_path = subdir / "top10_l2_by_post.csv"
        part.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"Wrote {out_path} ({len(part)} rows, {summary['n_posts']} posts)")
        return

    sources = discover_sources(args.inventory)
    if not sources:
        raise SystemExit("No clean sources found")
    combined, summary_df = run_export(sources=sources, out_dir=args.out_dir, top_n=args.top_n)
    print(f"Wrote {args.out_dir / 'top10_l2_by_post_all.csv'} ({len(combined)} rows)")
    print(f"Wrote {args.out_dir / 'summary_by_source.csv'}")
    for _, row in summary_df.iterrows():
        print(
            f"  {row['source_slug']}: {row['n_rows_exported']} rows / {row['n_posts']} posts"
        )


if __name__ == "__main__":
    main()
