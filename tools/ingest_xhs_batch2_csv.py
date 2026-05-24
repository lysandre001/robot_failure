#!/usr/bin/env python3
"""[一次性] 容错清洗第二批小红书宽表 CSV → sanitized CSV + QC 报告。"""
from __future__ import annotations

import argparse
from pathlib import Path

from phase1.config import ROOT
from phase1.xhs_io import check_overlap_with_batch1, sanitize_xhs_wide_csv


def main() -> None:
    ap = argparse.ArgumentParser(description="容错清洗小红书宽表 CSV（第二批 anchor）")
    ap.add_argument("--input", type=Path, default=ROOT / "2-小红书帖子数据.csv")
    ap.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "rawdata" / "xhs_batch2_wide_sanitized.csv",
    )
    ap.add_argument("--qc-md", type=Path, default=ROOT / "data" / "rawdata" / "xhs_merge_qc.md")
    ap.add_argument("--batch1-xlsx", type=Path, default=ROOT / "1-小红书帖子数据.xlsx")
    ap.add_argument("--expected-posts", type=int, default=17)
    args = ap.parse_args()

    df, qc = sanitize_xhs_wide_csv(args.input, output_csv=args.output, qc_md=args.qc_md)
    overlap = check_overlap_with_batch1(df, args.batch1_xlsx)

    print(f"OK: {qc['n_good_rows']} rows, skipped {qc['n_skipped_rows']}")
    print(f"Unique posts: {qc['n_unique_posts']}")
    print(f"Overlap with batch1: {overlap['overlap_count']}")
    print(f"Wrote: {qc['output_csv']}")
    print(f"QC: {qc['qc_md']}")

    if qc["n_unique_posts"] != args.expected_posts:
        raise SystemExit(
            f"QC FAIL: expected {args.expected_posts} posts, got {qc['n_unique_posts']}"
        )
    if overlap["overlap_count"] != 0:
        raise SystemExit(f"QC FAIL: overlap with batch1: {overlap['overlap_ids']}")


if __name__ == "__main__":
    main()
