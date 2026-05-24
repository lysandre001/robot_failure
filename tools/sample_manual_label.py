#!/usr/bin/env python3
"""[辅助] 按帖抽取一级评论，供人工开放编码。"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from phase1.config import ROOT
from phase1.manual_label import enrich_for_labeling, sample_l1_per_post
from phase1.post_links import DEFAULT_POSTS_CSV, attach_post_links


def main() -> None:
    ap = argparse.ArgumentParser(description="每帖抽取 N 条一级评论供人工标注")
    ap.add_argument("--input-csv", type=Path, default=ROOT / "data" / "clean" / "clean_comments_unified.csv")
    ap.add_argument("--out-csv", type=Path, default=ROOT / "data" / "clean" / "manual_label_l1_30perpost.csv")
    ap.add_argument("--n-per-post", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--doc-topics",
        type=Path,
        default=ROOT
        / "output/experiments/2026-05-19_topic_full_corpus_merged_bge_base/bert_kmeans_k7/doc_topics.csv",
    )
    ap.add_argument("--posts-csv", type=Path, default=DEFAULT_POSTS_CSV)
    args = ap.parse_args()

    df = pd.read_csv(args.input_csv)
    sample = sample_l1_per_post(df, n_per_post=args.n_per_post, random_seed=args.seed)
    sample = enrich_for_labeling(sample, doc_topics_path=args.doc_topics)
    sample = attach_post_links(sample, posts_csv=args.posts_csv)

    front = [
        "corpus", "帖子id", "帖子链接", "post_category", "帖子标题", "comment_id",
        "comment_level", "sample_stratum", "sample_rank_in_post", "bert_topic_k7",
        "like_count", "reply_count", "char_len", "content",
        "open_code", "axial_code", "memo", "exclude_from_coding", "coder",
    ]
    rest = [c for c in sample.columns if c not in front]
    sample = sample[[c for c in front if c in sample.columns] + rest]

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(args.out_csv, index=False, encoding="utf-8-sig")

    per_post = sample.groupby("帖子id").size()
    print(f"Wrote {args.out_csv}")
    print(f"  posts: {sample['帖子id'].nunique()}, rows: {len(sample)}")
    print(f"  L1 per post: min={per_post.min()}, median={per_post.median():.0f}, max={per_post.max()}")


if __name__ == "__main__":
    main()
