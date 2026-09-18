#!/usr/bin/env python3
"""[辅助] 在已有 clean 表上刷新帖子标签，并同步 data/clean/ 与 output/phase1/。"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from phase1.config import OUT, ROOT
from phase1.preprocess import refresh_post_labels


def _resolve_category_csv(platform: str | None, batch: str | None) -> Path | None:
    if platform and batch:
        p = ROOT / "config" / "post_category" / f"{platform}_{batch}.csv"
        if p.is_file():
            return p
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="刷新 clean_comments_unified 的 post_category / robot_status / human_role")
    ap.add_argument("--platform", type=str, default=None, help="如 youtube / tiktok；与 --batch 一起指定 clean 与分类表")
    ap.add_argument("--batch", type=str, default=None, help="如 2604-marathon")
    ap.add_argument(
        "--post-category-csv",
        type=Path,
        default=None,
        help="分类表路径；默认 xhs 用 config/post_category_by_post.csv，其它用 config/post_category/{platform}_{batch}.csv",
    )
    ap.add_argument(
        "--input-csv",
        type=Path,
        default=None,
    )
    ap.add_argument(
        "--out-csv",
        type=Path,
        default=None,
    )
    ap.add_argument(
        "--before-filter-csv",
        type=Path,
        default=None,
    )
    ap.add_argument("--sync-output-phase1", action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args()

    if args.platform and args.batch:
        clean_dir = ROOT / "data" / "clean" / args.platform.strip().lower() / args.batch
        input_csv = args.input_csv or (clean_dir / "clean_comments_unified.csv")
        out_csv = args.out_csv or input_csv
        before_filter = args.before_filter_csv or (clean_dir / "clean_comments_unified_before_filter.csv")
        cat_csv = args.post_category_csv or _resolve_category_csv(args.platform.strip().lower(), args.batch)
        if cat_csv is None and args.platform.strip().lower() == "xhs":
            cat_csv = ROOT / "config" / "post_category_by_post.csv"
        sync_phase1 = False
    else:
        input_csv = args.input_csv or (ROOT / "data" / "clean" / "clean_comments_unified.csv")
        out_csv = args.out_csv or input_csv
        before_filter = args.before_filter_csv or (ROOT / "data" / "clean" / "clean_comments_unified_before_filter.csv")
        cat_csv = args.post_category_csv
        sync_phase1 = args.sync_output_phase1

    if not input_csv.is_file():
        raise SystemExit(f"input not found: {input_csv}")

    df = pd.read_csv(input_csv)
    refreshed = refresh_post_labels(df, csv_path=cat_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    refreshed.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Wrote {out_csv} ({len(refreshed):,} rows)")
    if cat_csv:
        print(f"  post_category from: {cat_csv}")

    if before_filter.is_file():
        bf = refresh_post_labels(pd.read_csv(before_filter), csv_path=cat_csv)
        bf.to_csv(before_filter, index=False, encoding="utf-8-sig")
        print(f"Wrote {before_filter} ({len(bf):,} rows)")

    sample = refreshed.drop_duplicates("帖子id")[["帖子id", "post_category", "robot_status", "human_role"]].head(5)
    print(sample.to_string(index=False))

    if sync_phase1:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "data").mkdir(parents=True, exist_ok=True)
        for name in ("clean_comments_unified.csv",):
            shutil.copy2(out_csv, OUT / name)
            shutil.copy2(out_csv, OUT / "data" / name)
            print(f"Synced → {OUT / name}")
        if before_filter.is_file():
            for dest in (OUT / "clean_comments_unified_before_filter.csv", OUT / "data" / "clean_comments_unified_before_filter.csv"):
                shutil.copy2(before_filter, dest)


if __name__ == "__main__":
    main()
