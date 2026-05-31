#!/usr/bin/env python3
"""[辅助] 在已有 clean 表上刷新帖子标签，并同步 data/clean/ 与 output/phase1/。"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from phase1.config import OUT, ROOT
from phase1.preprocess import refresh_post_labels


def main() -> None:
    ap = argparse.ArgumentParser(description="刷新 clean_comments_unified 的 post_category / robot_status / human_role")
    ap.add_argument(
        "--input-csv",
        type=Path,
        default=ROOT / "data" / "clean" / "clean_comments_unified.csv",
    )
    ap.add_argument(
        "--out-csv",
        type=Path,
        default=ROOT / "data" / "clean" / "clean_comments_unified.csv",
    )
    ap.add_argument(
        "--before-filter-csv",
        type=Path,
        default=ROOT / "data" / "clean" / "clean_comments_unified_before_filter.csv",
    )
    ap.add_argument("--sync-output-phase1", action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args()

    df = pd.read_csv(args.input_csv)
    refreshed = refresh_post_labels(df)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    refreshed.to_csv(args.out_csv, index=False, encoding="utf-8-sig")
    print(f"Wrote {args.out_csv} ({len(refreshed):,} rows)")

    if args.before_filter_csv.is_file():
        bf = refresh_post_labels(pd.read_csv(args.before_filter_csv))
        bf.to_csv(args.before_filter_csv, index=False, encoding="utf-8-sig")
        print(f"Wrote {args.before_filter_csv} ({len(bf):,} rows)")

    sample = refreshed.drop_duplicates("帖子id")[["帖子id", "post_category", "robot_status", "human_role"]].head(5)
    print(sample.to_string(index=False))

    if args.sync_output_phase1:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "data").mkdir(parents=True, exist_ok=True)
        for name in ("clean_comments_unified.csv",):
            shutil.copy2(args.out_csv, OUT / name)
            shutil.copy2(args.out_csv, OUT / "data" / name)
            print(f"Synced → {OUT / name}")
        if args.before_filter_csv.is_file():
            for dest in (OUT / "clean_comments_unified_before_filter.csv", OUT / "data" / "clean_comments_unified_before_filter.csv"):
                shutil.copy2(args.before_filter_csv, dest)


if __name__ == "__main__":
    main()
