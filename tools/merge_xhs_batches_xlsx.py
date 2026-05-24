#!/usr/bin/env python3
"""[一次性] 合并第一批 Excel 与第二批 sanitized CSV → merged xlsx + posts.csv。"""
from __future__ import annotations

import argparse
from pathlib import Path

from phase1.config import ROOT
from phase1.xhs_io import build_merged_xlsx


def main() -> None:
    ap = argparse.ArgumentParser(description="合并两批小红书数据为 merged xlsx")
    ap.add_argument("--batch1", type=Path, default=ROOT / "1-小红书帖子数据.xlsx")
    ap.add_argument(
        "--batch2",
        type=Path,
        default=ROOT / "data" / "rawdata" / "xhs_batch2_wide_sanitized.csv",
    )
    ap.add_argument(
        "--out-xlsx",
        type=Path,
        default=ROOT / "data" / "rawdata" / "小红书帖子数据_merged.xlsx",
    )
    ap.add_argument("--posts-csv", type=Path, default=ROOT / "data" / "rawdata" / "posts.csv")
    ap.add_argument("--expected-posts", type=int, default=33)
    args = ap.parse_args()

    stats = build_merged_xlsx(
        args.batch1,
        args.batch2,
        merged_xlsx=args.out_xlsx,
        posts_csv=args.posts_csv,
    )
    print("Merged:", stats)
    if stats["n_unique_posts"] != args.expected_posts:
        raise SystemExit(
            f"QC FAIL: expected {args.expected_posts} posts, got {stats['n_unique_posts']}"
        )
    if stats["n_posts_csv"] != args.expected_posts:
        raise SystemExit(
            f"QC FAIL: posts.csv rows {stats['n_posts_csv']} != {args.expected_posts}"
        )


if __name__ == "__main__":
    main()
