"""
M3.5: 基于感知哈希(pHash)的同源视频匹配  —— 判同视频的主力
- 每段视频 ffmpeg 抽 N 帧 (默认 8), 每帧算 64-bit pHash
- 对每对 (tt, xhs), 计算所有帧对的最小汉明距离 -> 越小越同源
- 阈值 T (默认 8/64) 内即判同源; 同一个 xhs 可对应多个 tt (转发/二次剪辑)
- 写出 match_pairs_phash.csv, 并回写 tt 表的 matched_xhs_id

不依赖任何 API. 本地 几秒级跑完 100 段.
"""
from __future__ import annotations
import argparse
import subprocess
from pathlib import Path

import imagehash
import numpy as np
import pandas as pd
from PIL import Image


HASH_BITS = 64  # imagehash.phash 默认 8x8 -> 64 bit


def extract_frames(video: Path, out_dir: Path, n: int = 8) -> list[Path]:
    """均匀抽 n 帧 (避开首尾极端). 已存在则跳过."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if len(list(out_dir.glob("f*.jpg"))) >= n:
        return sorted(out_dir.glob("f*.jpg"))[:n]
    try:
        dur = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(video),
        ]).decode().strip())
    except Exception:
        dur = 30.0
    # 均匀采样, 留两端 5% 边界
    ts = [dur * (0.05 + 0.9 * i / max(n - 1, 1)) for i in range(n)]
    paths = []
    for i, t in enumerate(ts):
        out = out_dir / f"f{i}.jpg"
        if not out.exists():
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-ss", f"{t:.2f}", "-i", str(video),
                "-frames:v", "1", "-q:v", "4",
                "-vf", "scale=256:-2",
                str(out),
            ], check=False)
        if out.exists():
            paths.append(out)
    return paths


def hash_video(video: Path, frame_dir: Path, n: int) -> np.ndarray:
    """返回 (n, 64) bool array; 若帧不足返回实际帧数."""
    frames = extract_frames(video, frame_dir, n=n)
    hashes = []
    for f in frames:
        try:
            h = imagehash.phash(Image.open(f))
            hashes.append(np.array(h.hash).flatten())  # 8x8 bool -> 64
        except Exception:
            continue
    if not hashes:
        return np.zeros((0, HASH_BITS), dtype=bool)
    return np.stack(hashes)


def hash_dir(clip_dir: Path, frames_root: Path, n_frames: int) -> dict[str, np.ndarray]:
    out = {}
    for v in sorted(clip_dir.glob("*.mp4")):
        pid = v.stem
        hv = hash_video(v, frames_root / pid, n=n_frames)
        if hv.shape[0] == 0:
            print(f"[M3.5-SKIP] {pid} (no frames)")
            continue
        out[pid] = hv
        print(f"[M3.5] {pid}  frames={hv.shape[0]}")
    return out


def pair_min_hamming(a: np.ndarray, b: np.ndarray) -> tuple[int, int, int]:
    """返回 (min_hamming, ai, bi). a:(n,64) b:(m,64) -> n*m 帧对."""
    # xor 后 sum
    # 用 int8 累加避免 bool 加法歧义
    aa = a.astype(np.int8)[:, None, :]
    bb = b.astype(np.int8)[None, :, :]
    diff = np.sum(aa ^ bb, axis=2)  # (n, m)
    idx = np.unravel_index(int(np.argmin(diff)), diff.shape)
    return int(diff[idx]), int(idx[0]), int(idx[1])


def run(
    xhs_dir: Path, tt_dir: Path,
    frames_root: Path, out_pairs: Path,
    tt_meta: Path, n_frames: int, threshold: int,
) -> None:
    print("[M3.5] hashing xhs ...")
    xhs = hash_dir(xhs_dir, frames_root / "xhs", n_frames)
    print(f"[M3.5] xhs done: {len(xhs)} videos")
    print("[M3.5] hashing tiktok ...")
    tt = hash_dir(tt_dir, frames_root / "tiktok", n_frames)
    print(f"[M3.5] tiktok done: {len(tt)} videos")

    rows = []
    xhs_ids = list(xhs.keys())
    for tid, th in tt.items():
        best = (HASH_BITS + 1, "", 0, 0)
        for xid in xhs_ids:
            d, ai, bi = pair_min_hamming(th, xhs[xid])
            if d < best[0]:
                best = (d, xid, ai, bi)
        d, xid, ai, bi = best
        rows.append({
            "tiktok_id": tid,
            "xhs_id": xid,
            "min_hamming": d,
            "tt_frame": ai,
            "xhs_frame": bi,
            "matched": d <= threshold,
        })

    df = pd.DataFrame(rows).sort_values("min_hamming")
    out_pairs.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_pairs, index=False)
    n_m = int(df["matched"].sum())
    print(f"[M3.5] matched={n_m}/{len(df)} (T<={threshold}) -> {out_pairs}")

    # 回写 tt_meta 的 matched_xhs_id
    tt_df = pd.read_csv(tt_meta, dtype={"帖子id": str})
    id2xhs = {str(r.tiktok_id): (str(r.xhs_id) if r.matched else "")
              for r in df.itertuples()}
    tt_df["matched_xhs_id"] = tt_df["帖子id"].astype(str).map(id2xhs).fillna("")
    tt_df.to_csv(tt_meta, index=False)
    print(f"[M3.5] wrote matched_xhs_id -> {tt_meta}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--xhs-dir", required=True)
    p.add_argument("--tt-dir", required=True)
    p.add_argument("--frames-root", required=True, help="缓存帧目录")
    p.add_argument("--out-pairs", required=True)
    p.add_argument("--tt-meta", required=True, help="M1 输出的 tt csv, 用于回写 matched_xhs_id")
    p.add_argument("--n-frames", type=int, default=8)
    p.add_argument("--threshold", type=int, default=8,
                   help="最小汉明距离阈值 (0=完全相同, 64=完全不同); 8 是常见同源视频经验值")
    a = p.parse_args()
    run(Path(a.xhs_dir), Path(a.tt_dir),
        Path(a.frames_root), Path(a.out_pairs),
        Path(a.tt_meta), a.n_frames, a.threshold)


if __name__ == "__main__":
    main()
