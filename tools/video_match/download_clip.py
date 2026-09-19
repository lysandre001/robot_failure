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
import os
import random
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


def _yt_dlp_cmd() -> list[str]:
    env = os.environ.get("YT_DLP")
    if env:
        return [env]
    local = Path.home() / ".local" / "bin" / "yt-dlp"
    if local.is_file():
        return [str(local)]
    found = shutil.which("yt-dlp")
    if found:
        return [found]
    return [sys.executable, "-m", "yt_dlp"]


def download_one(url: str, out_path: Path, seconds: int = 30, timeout: int = 180) -> tuple[bool, str]:
    if out_path.exists() and out_path.stat().st_size > 0:
        return True, "already"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        *_yt_dlp_cmd(),
        "--no-warnings",
        "--download-sections", f"*0-{seconds}",
        "-f", "b[height<=720]/mp4/b",
        "--retries", "3",
        "--fragment-retries", "3",
        "--socket-timeout", "30",
        "-o", str(out_path),
        url,
    ]
    browser = os.environ.get("YT_DLP_COOKIES_FROM_BROWSER", "").strip()
    if browser:
        cmd[1:1] = ["--cookies-from-browser", browser]
    try:
        proc = subprocess.run(cmd, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return True, "ok"
        err = (proc.stderr or b"").decode(errors="ignore").strip().splitlines()
        msg = err[-1] if err else f"exit_{proc.returncode}"
        print(f"[M2-FAIL] {url[:80]} -> {msg}")
        return False, msg[:500]
    except subprocess.TimeoutExpired:
        print(f"[M2-FAIL] {url[:80]} -> timeout")
        return False, "timeout"
    except Exception as e:
        print(f"[M2-FAIL] {url[:80]} -> {e}")
        return False, str(e)[:500]


def write_report(out_dir: Path, rows: list[dict]) -> Path:
    path = out_dir / "download_report.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "url", "status", "bytes", "error"])
        w.writeheader()
        w.writerows(rows)
    return path


def run(in_csv: Path, out_dir: Path, id_col: str, url_col: str,
        seconds: int, max_retries: int, sleep: float, jitter: float,
        workers: int = 3) -> dict:
    df = pd.read_csv(in_csv, dtype={id_col: str})
    df = df.drop_duplicates(id_col).reset_index(drop=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    pending = [(str(r[id_col]), str(r[url_col])) for _, r in df.iterrows()
               if not (out_dir / f"{r[id_col]}.mp4").exists()]
    already = len(df) - len(pending)
    print(f"[M2] total={len(df)} already={already} pending={len(pending)} workers={workers}")

    errors: dict[str, str] = {}
    failed = pending[:]
    n_workers = max(1, int(workers))

    def _one(item: tuple[str, str]) -> tuple[str, str, bool, str]:
        pid, url = item
        ok, msg = download_one(url, out_dir / f"{pid}.mp4", seconds=seconds)
        time.sleep(sleep + random.uniform(0, jitter))
        return pid, url, ok, msg

    for attempt in range(1, max_retries + 1):
        if not failed:
            break
        print(f"[M2] === attempt {attempt}/{max_retries} on {len(failed)} items ===")
        still_failed = []
        ok_n = 0
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            futs = [pool.submit(_one, item) for item in failed]
            for fut in as_completed(futs):
                pid, url, ok, msg = fut.result()
                if ok:
                    ok_n += 1
                    errors.pop(pid, None)
                else:
                    still_failed.append((pid, url))
                    errors[pid] = msg
        print(f"[M2] attempt {attempt}: ok={ok_n} fail={len(still_failed)}")
        failed = still_failed

    report_rows = []
    for _, r in df.iterrows():
        pid = str(r[id_col])
        url = str(r[url_col])
        mp4 = out_dir / f"{pid}.mp4"
        if mp4.exists() and mp4.stat().st_size > 0:
            report_rows.append({
                "id": pid, "url": url, "status": "ok",
                "bytes": mp4.stat().st_size, "error": "",
            })
        else:
            report_rows.append({
                "id": pid, "url": url, "status": "fail",
                "bytes": 0, "error": errors.get(pid, "missing"),
            })
    write_report(out_dir, report_rows)

    fail_path = out_dir / "failed.csv"
    if failed:
        with fail_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "url", "error"])
            w.writeheader()
            w.writerows([{"id": p, "url": u, "error": errors.get(p, "")} for p, u in failed])
        print(f"[M2] final failed={len(failed)} -> {fail_path}")
    elif fail_path.exists():
        fail_path.unlink()
    n_ok = sum(1 for x in report_rows if x["status"] == "ok")
    print(f"[M2] done. ok={n_ok} fail={len(report_rows)-n_ok} clips in {out_dir}")
    return {"n_total": len(report_rows), "n_ok": n_ok, "n_fail": len(report_rows) - n_ok, "out_dir": str(out_dir)}


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
    p.add_argument("--workers", type=int, default=3, help="并行下载线程数")
    a = p.parse_args()
    run(Path(a.inp), Path(a.out_dir), a.id_col, a.url_col,
        a.seconds, a.max_retries, a.sleep, a.jitter, a.workers)


if __name__ == "__main__":
    main()
