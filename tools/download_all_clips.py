#!/usr/bin/env python3
"""从 raw 宽表抽帖子链接，写入 data/rawdata/{platform}/{batch}/clips/（复用 M2 yt-dlp）。"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from phase1.config import ROOT
from phase1.preprocess import normalize_post_id
from tools.video_match.post_media_jobs import JOBS

_DOWNLOAD_CLIP = Path(__file__).resolve().parent / "video_match" / "download_clip.py"


def _load_download_run():
    import importlib.util

    spec = importlib.util.spec_from_file_location("download_clip", _DOWNLOAD_CLIP)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.run

def reuse_existing_clips(job: dict) -> int:
    """Hardlink previously downloaded 30s clips (video_match M2) into rawdata clips/."""
    src = job.get("reuse")
    if not src:
        return 0
    src = Path(src)
    dst = Path(job["clips"])
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for mp4 in src.glob("*.mp4"):
        if mp4.stat().st_size <= 0:
            continue
        target = dst / mp4.name
        if target.exists() and target.stat().st_size > 0:
            continue
        if target.exists():
            target.unlink()
        try:
            os.link(mp4, target)
        except OSError:
            import shutil
            shutil.copy2(mp4, target)
        n += 1
    return n


def write_manifest(job: dict) -> Path:
    raw = Path(job["raw"])
    df = pd.read_csv(raw, low_memory=False, dtype={job["id_col"]: str, job["url_col"]: str})
    out = df[[job["id_col"], job["url_col"]]].copy()
    out.columns = ["帖子id", "帖子链接"]
    out["帖子id"] = out["帖子id"].map(normalize_post_id)
    out = out.dropna(subset=["帖子id", "帖子链接"])
    out = out[out["帖子链接"].astype(str).str.startswith("http")]
    out = out.drop_duplicates("帖子id")
    clips = Path(job["clips"])
    clips.mkdir(parents=True, exist_ok=True)
    path = clips / "urls.csv"
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def aggregate_reports(jobs: list[dict], out_csv: Path) -> pd.DataFrame:
    parts = []
    for job in jobs:
        rep = Path(job["clips"]) / "download_report.csv"
        if not rep.is_file():
            continue
        df = pd.read_csv(rep)
        df["platform"] = job["platform"]
        df["source_batch"] = job["batch"]
        parts.append(df)
    all_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if not all_df.empty:
        all_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    summary_rows = []
    for job in jobs:
        sub = all_df[
            (all_df["platform"] == job["platform"]) & (all_df["source_batch"] == job["batch"])
        ] if not all_df.empty else pd.DataFrame()
        n = len(sub)
        n_ok = int((sub["status"] == "ok").sum()) if n else 0
        summary_rows.append({
            "platform": job["platform"],
            "source_batch": job["batch"],
            "clips_dir": str(job["clips"]),
            "n_posts": n,
            "n_ok": n_ok,
            "n_fail": n - n_ok,
            "ok_pct": round(100.0 * n_ok / n, 1) if n else None,
        })
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(out_csv.with_name("clips_download_summary.csv"), index=False, encoding="utf-8-sig")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="按平台下载 raw 帖子视频切片到 clips/")
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--max-retries", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--jitter", type=float, default=0.8)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--skip-download", action="store_true", help="只写 urls.csv / 汇总已有 report")
    args = ap.parse_args()

    for job in JOBS:
        man = write_manifest(job)
        n_reuse = reuse_existing_clips(job)
        n_url = sum(1 for _ in open(man)) - 1
        print(f"[manifest] {job['platform']}/{job['batch']} -> {man} ({n_url} urls, reused={n_reuse})")
        if args.skip_download:
            continue
        download_run = _load_download_run()
        download_run(
            man,
            Path(job["clips"]),
            "帖子id",
            "帖子链接",
            args.seconds,
            args.max_retries,
            args.sleep,
            args.jitter,
            args.workers,
        )

    summary = aggregate_reports(JOBS, ROOT / "data" / "rawdata" / "clips_download_report.csv")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
