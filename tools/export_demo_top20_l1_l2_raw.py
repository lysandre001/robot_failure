#!/usr/bin/env python3
"""从 raw 宽表按帖抽取 Top-N 高 L2 子评论数的一级评论，每条 L1 附 1 条最高赞 L2（demo / Drive）。"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from phase1.config import ROOT
from phase1.douyin_io import douyin_rows_to_canonical
from phase1.preprocess import normalize_post_id, normalize_text
from tools.comment_lang.io_utils import read_raw_csv

DEFAULT_OUT_DIR = ROOT / "data" / "demo"
DEFAULT_TOP_N = 20
SAMPLING_METHOD = "top20L1_1L2_by_l2count"

EVENT_NAMES = {
    ("tiktok", "2604-marathon"): "beijing_robot_marathon",
    ("tiktok", "2608-olympic"): "world_humanoid_robot_games",
    ("douyin", "2608-olympic"): "world_humanoid_robot_games",
    ("youtube", "2604-marathon"): "beijing_robot_marathon",
    ("youtube", "2608-olympic"): "world_humanoid_robot_games",
}

JOBS: list[dict[str, Any]] = [
    {
        "platform": "tiktok",
        "batch": "2604-marathon",
        "path": ROOT / "data/rawdata/tiktok/2604-marathon/beijing_robot_marathon_帖子数据(1).csv",
        "kind": "csv",
        "source": "raw",
        "include_lang": True,
    },
    {
        "platform": "tiktok",
        "batch": "2608-olympic",
        "path": ROOT / "data/clean/tiktok/2608-olympic/clean_comments_unified.csv",
        "kind": "clean",
        "source": "clean",
        "include_lang": False,
    },
    {
        "platform": "douyin",
        "batch": "2608-olympic",
        "path": ROOT / "data/clean/douyin/2608-olympic/clean_comments_unified.csv",
        "kind": "clean",
        "source": "clean",
        "include_lang": False,
    },
    {
        "platform": "youtube",
        "batch": "2604-marathon",
        "path": ROOT / "data/clean/youtube/2604-marathon/clean_comments_unified.csv",
        "kind": "clean",
        "source": "clean",
        "include_lang": True,
    },
    {
        "platform": "youtube",
        "batch": "2608-olympic",
        "path": ROOT / "data/clean/youtube/2608-olympic/clean_comments_unified.csv",
        "kind": "clean",
        "source": "clean",
        "include_lang": True,
    },
]

BASE_COLS = [
    "event",
    "platform",
    "source_batch",
    "sampling_method",
    "帖子id",
    "帖子标题",
    "post_category",
    "rank_in_post",
    "comment_level",
    "comment_id",
    "parent_comment_id",
    "content",
    "like_count",
    "reply_count",
    "comment_time",
    "location",
    "n_l2_children",
    "char_len",
]

LANG_COLS = ["language", "is_mixed", "content_en"]


def _load_raw(job: dict[str, Any]) -> pd.DataFrame:
    path = Path(job["path"])
    if job.get("source") == "clean" or job["kind"] == "clean":
        return pd.read_csv(path)
    if job["kind"] == "douyin":
        raw = pd.read_csv(path, dtype=str, low_memory=False)
        for col in (
            "一级评论语言", "一级评论混合", "一级评论英文",
            "二级评论语言", "二级评论混合", "二级评论英文",
        ):
            if col not in raw.columns:
                raw[col] = pd.NA
        return douyin_rows_to_canonical(raw)
    return read_raw_csv(path)


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _clean_text(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).replace("\n", " ").strip()


def _pick_best_l2(l2: pd.DataFrame, parent_id: str) -> pd.Series | None:
    sub = l2[l2["一级评论id"].astype(str) == str(parent_id)]
    if sub.empty:
        return None
    sub = sub.sort_values("二级评论点赞数", ascending=False, kind="mergesort")
    return sub.iloc[0]


def _export_from_raw_wide(
    df: pd.DataFrame,
    *,
    platform: str,
    batch: str,
    event: str,
    include_lang: bool,
    top_n: int,
) -> tuple[list[dict[str, Any]], int]:
    df["帖子id"] = df["帖子id"].map(normalize_post_id)
    df = df[df["帖子id"].notna()].copy()
    df["一级评论id"] = df["一级评论id"].astype(str).str.strip()
    df.loc[df["一级评论id"].isin(["", "nan", "None", "<NA>"]), "一级评论id"] = pd.NA
    df = df[df["一级评论id"].notna()].copy()

    df["一级评论点赞数"] = _num(df.get("一级评论点赞数"))
    df["一级评论回复数"] = _num(df.get("一级评论回复数"))
    df["二级评论点赞数"] = _num(df.get("二级评论点赞数"))

    has_l2 = df["二级评论id"].notna() & (df["二级评论id"].astype(str).str.strip() != "")
    l2 = df[has_l2].copy()
    l2["二级评论id"] = l2["二级评论id"].astype(str).str.strip()

    l2_counts = l2.groupby("一级评论id", sort=False).size().rename("n_l2_children")

    l1 = (
        df.sort_values(["一级评论id", "一级评论点赞数"], ascending=[True, False], kind="mergesort")
        .drop_duplicates(subset=["一级评论id"], keep="first")
        .copy()
    )
    l1 = l1.merge(l2_counts, left_on="一级评论id", right_index=True, how="left")
    l1["n_l2_children"] = l1["n_l2_children"].fillna(0).astype(int)

    l1 = l1.sort_values(
        ["帖子id", "n_l2_children", "一级评论点赞数"],
        ascending=[True, False, False],
        kind="mergesort",
    )
    top_l1 = l1.groupby("帖子id", sort=False).head(top_n).copy()
    top_l1["rank_in_post"] = top_l1.groupby("帖子id").cumcount() + 1

    rows: list[dict[str, Any]] = []
    for _, l1_row in top_l1.iterrows():
        l1_id = str(l1_row["一级评论id"])
        l1_content = _clean_text(l1_row.get("一级评论内容"))
        base = {
            "event": event,
            "platform": platform,
            "source_batch": batch,
            "sampling_method": SAMPLING_METHOD,
            "帖子id": l1_row["帖子id"],
            "帖子标题": _clean_text(l1_row.get("帖子标题")),
            "post_category": "unknown",
            "rank_in_post": int(l1_row["rank_in_post"]),
            "comment_level": 1,
            "comment_id": l1_id,
            "parent_comment_id": "",
            "content": l1_content,
            "like_count": int(l1_row["一级评论点赞数"]),
            "reply_count": int(l1_row["一级评论回复数"]),
            "comment_time": _clean_text(l1_row.get("一级评论时间")),
            "location": _clean_text(l1_row.get("一级评论地址")),
            "n_l2_children": int(l1_row["n_l2_children"]),
            "char_len": len(normalize_text(l1_content) or l1_content),
        }
        if include_lang:
            base["language"] = _clean_text(l1_row.get("一级评论语言"))
            base["is_mixed"] = _clean_text(l1_row.get("一级评论混合"))
            base["content_en"] = _clean_text(l1_row.get("一级评论英文"))
        rows.append(base)

        l2_row = _pick_best_l2(l2, l1_id)
        if l2_row is not None:
            l2_content = _clean_text(l2_row.get("二级评论内容"))
            l2_rec = {
                "event": event,
                "platform": platform,
                "source_batch": batch,
                "sampling_method": SAMPLING_METHOD,
                "帖子id": l1_row["帖子id"],
                "帖子标题": _clean_text(l1_row.get("帖子标题")),
                "post_category": "unknown",
                "rank_in_post": int(l1_row["rank_in_post"]),
                "comment_level": 2,
                "comment_id": str(l2_row["二级评论id"]),
                "parent_comment_id": l1_id,
                "content": l2_content,
                "like_count": int(l2_row["二级评论点赞数"]),
                "reply_count": 0,
                "comment_time": _clean_text(l2_row.get("二级评论时间")),
                "location": _clean_text(l2_row.get("二级评论地址")),
                "n_l2_children": "",
                "char_len": len(normalize_text(l2_content) or l2_content),
            }
            if include_lang:
                l2_rec["language"] = _clean_text(l2_row.get("二级评论语言"))
                l2_rec["is_mixed"] = _clean_text(l2_row.get("二级评论混合"))
                l2_rec["content_en"] = _clean_text(l2_row.get("二级评论英文"))
            rows.append(l2_rec)
    return rows, int(top_l1["帖子id"].nunique())


def _export_from_clean_long(
    df: pd.DataFrame,
    *,
    platform: str,
    batch: str,
    event: str,
    top_n: int,
    include_lang: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    df["comment_level"] = pd.to_numeric(df["comment_level"], errors="coerce")
    df = df[df["comment_level"].isin([1, 2])].copy()
    l1 = df[df["comment_level"] == 1].copy()
    l2 = df[df["comment_level"] == 2].copy()
    l2["like_count"] = _num(l2.get("like_count"))
    l1["like_count"] = _num(l1.get("like_count"))
    l1["reply_count"] = _num(l1.get("reply_count"))

    l2_counts = l2.groupby("parent_comment_id", dropna=False).size().rename("n_l2_children")
    l1 = l1.merge(l2_counts, left_on="comment_id", right_index=True, how="left")
    l1["n_l2_children"] = l1["n_l2_children"].fillna(0).astype(int)

    l1 = l1.sort_values(
        ["帖子id", "n_l2_children", "like_count"],
        ascending=[True, False, False],
        kind="mergesort",
    )
    top_l1 = l1.groupby("帖子id", sort=False).head(top_n).copy()
    top_l1["rank_in_post"] = top_l1.groupby("帖子id").cumcount() + 1

    rows: list[dict[str, Any]] = []
    for _, l1_row in top_l1.iterrows():
        l1_id = str(l1_row["comment_id"])
        l1_content = _clean_text(l1_row.get("content"))
        post_cat = _clean_text(l1_row.get("post_category")) or "unknown"
        l1_rec = {
            "event": event,
            "platform": platform,
            "source_batch": batch,
            "sampling_method": SAMPLING_METHOD,
            "帖子id": l1_row["帖子id"],
            "帖子标题": _clean_text(l1_row.get("帖子标题")),
            "post_category": post_cat,
            "rank_in_post": int(l1_row["rank_in_post"]),
            "comment_level": 1,
            "comment_id": l1_id,
            "parent_comment_id": "",
            "content": l1_content,
            "like_count": int(l1_row["like_count"]),
            "reply_count": int(l1_row["reply_count"]),
            "comment_time": _clean_text(l1_row.get("comment_time")),
            "location": _clean_text(l1_row.get("location")),
            "n_l2_children": int(l1_row["n_l2_children"]),
            "char_len": len(normalize_text(l1_content) or l1_content),
        }
        if include_lang:
            l1_rec["language"] = _clean_text(l1_row.get("language"))
            l1_rec["is_mixed"] = _clean_text(l1_row.get("is_mixed"))
            l1_rec["content_en"] = _clean_text(l1_row.get("content_en"))
        rows.append(l1_rec)

        sub = l2[l2["parent_comment_id"].astype(str) == l1_id]
        if not sub.empty:
            l2_row = sub.sort_values("like_count", ascending=False, kind="mergesort").iloc[0]
            l2_content = _clean_text(l2_row.get("content"))
            l2_rec = {
                "event": event,
                "platform": platform,
                "source_batch": batch,
                "sampling_method": SAMPLING_METHOD,
                "帖子id": l1_row["帖子id"],
                "帖子标题": _clean_text(l1_row.get("帖子标题")),
                "post_category": post_cat,
                "rank_in_post": int(l1_row["rank_in_post"]),
                "comment_level": 2,
                "comment_id": str(l2_row["comment_id"]),
                "parent_comment_id": l1_id,
                "content": l2_content,
                "like_count": int(l2_row["like_count"]),
                "reply_count": 0,
                "comment_time": _clean_text(l2_row.get("comment_time")),
                "location": _clean_text(l2_row.get("location")),
                "n_l2_children": "",
                "char_len": len(normalize_text(l2_content) or l2_content),
            }
            if include_lang:
                l2_rec["language"] = _clean_text(l2_row.get("language"))
                l2_rec["is_mixed"] = _clean_text(l2_row.get("is_mixed"))
                l2_rec["content_en"] = _clean_text(l2_row.get("content_en"))
            rows.append(l2_rec)
    return rows, int(top_l1["帖子id"].nunique())


def export_top20_l1_l2(
    job: dict[str, Any],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = _load_raw(job)
    platform, batch = job["platform"], job["batch"]
    event = EVENT_NAMES.get((platform, batch), batch)
    include_lang = bool(job.get("include_lang"))

    if job.get("source") == "clean" or job["kind"] == "clean":
        rows, n_posts = _export_from_clean_long(
            df,
            platform=platform,
            batch=batch,
            event=event,
            top_n=top_n,
            include_lang=include_lang,
        )
    else:
        rows, n_posts = _export_from_raw_wide(
            df,
            platform=platform,
            batch=batch,
            event=event,
            include_lang=include_lang,
            top_n=top_n,
        )

    out_cols = BASE_COLS + (LANG_COLS if include_lang else [])
    out = pd.DataFrame(rows)
    for col in out_cols:
        if col not in out.columns:
            out[col] = ""
    out = out[out_cols]

    summary = {
        "event": event,
        "platform": platform,
        "source_batch": batch,
        "sampling_method": SAMPLING_METHOD,
        "include_lang": include_lang,
        "n_posts": n_posts,
        "n_l1_rows": int((out["comment_level"] == 1).sum()),
        "n_l2_rows": int((out["comment_level"] == 2).sum()),
        "n_rows": len(out),
        "top_n": top_n,
    }
    return out, summary


def drive_filename(job: dict[str, Any], *, ext: str = "xlsx") -> str:
    event = EVENT_NAMES.get((job["platform"], job["batch"]), job["batch"])
    suffix = "_with_lang_en" if job.get("include_lang") else ""
    return f"{event}__{job['batch']}__{job['platform']}__{SAMPLING_METHOD}{suffix}.{ext}"


def run_export(
    jobs: list[dict[str, Any]],
    *,
    out_dir: Path,
    top_n: int,
) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []

    for job in jobs:
        part, summary = export_top20_l1_l2(job, top_n=top_n)
        slug = f"{job['platform']}_{job['batch']}"
        subdir = out_dir / slug
        subdir.mkdir(parents=True, exist_ok=True)

        csv_name = drive_filename(job, ext="csv")
        xlsx_name = drive_filename(job, ext="xlsx")
        part.to_csv(subdir / csv_name, index=False, encoding="utf-8-sig")
        part.to_excel(subdir / xlsx_name, index=False, sheet_name="sample")

        summary["csv_path"] = str((subdir / csv_name).resolve())
        summary["xlsx_path"] = str((subdir / xlsx_name).resolve())
        summary["drive_filename"] = xlsx_name
        summaries.append(summary)
        print(
            f"  {slug}: {summary['n_l1_rows']} L1 + {summary['n_l2_rows']} L2 "
            f"({summary['n_posts']} posts) -> {xlsx_name}"
        )

    summary_df = pd.DataFrame(summaries)
    summary_path = out_dir / "top20_l1_l2_raw_summary.csv"
    if summary_path.is_file() and len(jobs) < len(JOBS):
        prev = pd.read_csv(summary_path)
        key = ["platform", "source_batch"]
        prev = prev[
            ~prev.set_index(key).index.isin(summary_df.set_index(key).index)
        ]
        summary_df = pd.concat([prev, summary_df], ignore_index=True)
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    return summary_df


def main() -> None:
    ap = argparse.ArgumentParser(description="Raw 宽表：每帖 Top20 L1 + 1 L2（demo / Drive）")
    ap.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--platform", choices=["tiktok", "douyin", "youtube"])
    ap.add_argument("--batch")
    args = ap.parse_args()

    jobs = JOBS
    if args.platform and args.batch:
        jobs = [j for j in JOBS if j["platform"] == args.platform and j["batch"] == args.batch]
        if not jobs:
            raise SystemExit(f"unknown job: {args.platform}/{args.batch}")

    print(f"Export top-{args.top_n} L1 + 1 L2 from raw -> {args.out_dir}")
    run_export(jobs, out_dir=args.out_dir, top_n=args.top_n)


if __name__ == "__main__":
    main()
