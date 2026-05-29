"""
M2: 下载帖子视频前 30 秒切片
- 输入: 一个 csv, 至少含列 [id, url] (id 用作文件名)
- 输出: out_dir/{id}.mp4
- 依赖: yt-dlp (brew install yt-dlp), ffmpeg

xhs 链接通常带 xsec_token, 多数情况下 yt-dlp 也能拉到 (失败的会写入 failed.csv 留待人工/封面回退).
"""
from __future__ import annotations
import argparse
import csv
import random
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd


def download_one(url: str, out_path: Path, seconds: int = 30, timeout: int = 180) -> bool:
    if out_path.exists() and out_path.stat().st_size > 0:
        return True
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--quiet", "--no-warnings",
        "--download-sections", f"*0-{seconds}",
        "--force-keyframes-at-cuts",
        "-f", "mp4/bv*+ba/best",
        "--retries", "3",
        "--fragment-retries", "3",
        "--socket-timeout", "30",
        "-o", str(out_path),
        url,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return out_path.exists() and out_path.stat().st_size > 0
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode(errors="ignore").strip().splitlines()[-1:]
        print(f"[M2-FAIL] {url[:80]} -> {err}")
        return False
    except Exception as e:
        print(f"[M2-FAIL] {url[:80]} -> {e}")
        return False


def run(in_csv: Path, out_dir: Path, id_col: str, url_col: str,
        seconds: int, max_retries: int, sleep: float, jitter: float) -> None:
    df = pd.read_csv(in_csv, dtype={id_col: str})
    df = df.drop_duplicates(id_col).reset_index(drop=True)

    # 待下任务 = 输出目录尚无对应 mp4 的
    pending = [(str(r[id_col]), str(r[url_col])) for _, r in df.iterrows()
               if not (out_dir / f"{r[id_col]}.mp4").exists()]
    print(f"[M2] total={len(df)} already={len(df)-len(pending)} pending={len(pending)}")

    failed = pending[:]
    for attempt in range(1, max_retries + 1):
        if not failed:
            break
        print(f"[M2] === attempt {attempt}/{max_retries} on {len(failed)} items ===")
        still_failed = []
        for i, (pid, url) in enumerate(failed, 1):
            ok = download_one(url, out_dir / f"{pid}.mp4", seconds=seconds)
            if not ok:
                still_failed.append((pid, url))
            # 节流: sleep + 抖动, 避免被 TikTok 限速
            time.sleep(sleep + random.uniform(0, jitter))
        print(f"[M2] attempt {attempt}: ok={len(failed)-len(still_failed)} fail={len(still_failed)}")
        failed = still_failed

    fail_path = out_dir / "failed.csv"
    if failed:
        with fail_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "url"])
            w.writeheader(); w.writerows([{"id": p, "url": u} for p, u in failed])
        print(f"[M2] final failed={len(failed)} -> {fail_path}")
    elif fail_path.exists():
        fail_path.unlink()
    print(f"[M2] done. clips in {out_dir}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True, help="csv with id + url cols")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--id-col", default="帖子id")
    p.add_argument("--url-col", default="帖子链接")
    p.add_argument("--seconds", type=int, default=30)
    p.add_argument("--max-retries", type=int, default=3, help="整轮重试次数")
    p.add_argument("--sleep", type=float, default=1.5, help="每条之间的固定间隔(秒)")
    p.add_argument("--jitter", type=float, default=2.0, help="叠加的随机抖动上限(秒)")
    a = p.parse_args()
    run(Path(a.inp), Path(a.out_dir), a.id_col, a.url_col,
        a.seconds, a.max_retries, a.sleep, a.jitter)


if __name__ == "__main__":
    main()
