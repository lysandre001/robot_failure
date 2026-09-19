#!/usr/bin/env python3
"""从 shared_analyzable_corpus 增量抽取一级评论，每帖凑满 20 条（排除已有标注样本的 id/正文）。"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from phase1.config import POST_CATEGORY_BY_POST_CSV, ROOT
from phase1.manual_label import sample_l1_increment_per_post

DEFAULT_EXISTING = (
    ROOT
    / "human_label_llm/label_data/filtered_sample10_per_post_humanlabel.csv"
)
DEFAULT_CORPUS = ROOT / "data/clean/shared_analyzable_corpus.csv"
DEFAULT_POSTS = POST_CATEGORY_BY_POST_CSV
DEFAULT_OUT_ADDENDUM = (
    ROOT / "human_label_llm/label_data/filtered_sample20_per_post_addendum.csv"
)
DEFAULT_OUT_MERGED = (
    ROOT / "human_label_llm/label_data/filtered_sample20_per_post_merged.csv"
)
DEFAULT_OUT_REPORT = (
    ROOT / "human_label_llm/label_data/sample20_per_post_report.csv"
)

HUMAN_LABEL_COLS = [
    "帖子id",
    "post_category",
    "human_category",
    "帖子点赞数",
    "帖子评论数",
    "comment_level",
    "comment_id",
    "parent_comment_id",
    "帖子标题",
    "content",
    "评估对象",
    "情感(p/neg/n/m)",
    "combo",
    "comment_time",
    "like_count",
    "reply_count",
    "char_len",
]


def _normalize_content(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)


def load_exclusions(existing: pd.DataFrame) -> tuple[set[str], set[str]]:
    ex_ids = set(existing["comment_id"].astype(str).str.strip())
    ex_ids.discard("")
    ex_ids.discard("nan")
    ex_txt = set(_normalize_content(existing["content"]))
    ex_txt.discard("")
    ex_txt.discard("nan")
    return ex_ids, ex_txt


def existing_l1_counts(existing: pd.DataFrame) -> dict[str, int]:
    l1 = existing[existing["comment_level"] == 1]
    return l1.groupby("帖子id").size().astype(int).to_dict()


def to_human_label_format(
    sampled: pd.DataFrame,
    posts_meta: pd.DataFrame,
) -> pd.DataFrame:
    """对齐 filtered_sample10_per_post_humanlabel.csv 列结构。"""
    meta = posts_meta.copy()
    meta["帖子id"] = meta["帖子id"].astype(str)
    meta = meta.rename(
        columns={"机器人状态": "post_category", "人的形象": "human_category"}
    )[["帖子id", "post_category", "human_category"]]

    out = sampled.copy()
    out["帖子id"] = out["帖子id"].astype(str)
    drop_cols = [c for c in ("post_category", "human_category", "robot_status", "human_role") if c in out.columns]
    out = out.drop(columns=drop_cols, errors="ignore")
    out = out.merge(meta, on="帖子id", how="left")
    out["post_category"] = out["post_category"].fillna("")
    out["human_category"] = out["human_category"].fillna("")
    out["combo"] = out["human_category"].astype(str) + "+" + out["post_category"].astype(str)
    out["combo"] = out["combo"].str.strip("+")

    for c in HUMAN_LABEL_COLS:
        if c not in out.columns:
            out[c] = ""

    return out.reindex(columns=HUMAN_LABEL_COLS)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--existing-csv", type=Path, default=DEFAULT_EXISTING)
    ap.add_argument("--corpus-csv", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--posts-csv", type=Path, default=DEFAULT_POSTS)
    ap.add_argument("--target-per-post", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-addendum", type=Path, default=DEFAULT_OUT_ADDENDUM)
    ap.add_argument("--out-merged", type=Path, default=DEFAULT_OUT_MERGED)
    ap.add_argument("--out-report", type=Path, default=DEFAULT_OUT_REPORT)
    args = ap.parse_args()

    existing = pd.read_csv(args.existing_csv)
    corpus = pd.read_csv(args.corpus_csv)
    posts = pd.read_csv(args.posts_csv, encoding="utf-8-sig")

    ex_ids, ex_txt = load_exclusions(existing)
    l1_counts = existing_l1_counts(existing)
    post_ids = sorted(set(posts["帖子id"].astype(str)) & set(corpus["帖子id"].astype(str)))

    new_raw, report = sample_l1_increment_per_post(
        corpus,
        target_per_post=args.target_per_post,
        exclude_comment_ids=ex_ids,
        exclude_content=ex_txt,
        existing_l1_counts=l1_counts,
        post_ids=post_ids,
        random_seed=args.seed,
    )  # noqa: E501

    addendum = to_human_label_format(new_raw, posts)
    merged = pd.concat(
        [existing.reindex(columns=HUMAN_LABEL_COLS), addendum],
        ignore_index=True,
    )

    args.out_addendum.parent.mkdir(parents=True, exist_ok=True)
    addendum.to_csv(args.out_addendum, index=False, encoding="utf-8-sig")
    merged.to_csv(args.out_merged, index=False, encoding="utf-8-sig")
    report.to_csv(args.out_report, index=False, encoding="utf-8-sig")

    l1_merged = merged[merged["comment_level"] == 1]
    per_post = l1_merged.groupby("帖子id").size()
    print(f"Existing rows: {len(existing)}  (L1={int((existing.comment_level==1).sum())})")
    print(f"New addendum:    {len(addendum)}  (L1 only)")
    print(f"Merged rows:     {len(merged)}  (L1={len(l1_merged)})")
    print(f"L1 per post — min={per_post.min()} max={per_post.max()} mean={per_post.mean():.1f}")
    print(f"Wrote {args.out_addendum}")
    print(f"Wrote {args.out_merged}")
    print(f"Wrote {args.out_report}")
    short = report[report["status"] == "shortfall"]
    if not short.empty:
        print("\nShortfall posts (池子不足，未凑满 20):")
        print(short.to_string(index=False))


if __name__ == "__main__":
    main()
