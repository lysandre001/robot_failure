"""
M3.6: 视觉嵌入 + 一一匹配
- 每段视频沿用 M3.5 抽出的 8 帧 (_phash_frames/{side}/{id}/f*.jpg)
- 每帧调 SiliconFlow Qwen3-VL-Embedding-8B 取视觉向量, 缓存到 .npy
- (tt,xhs) 配对相似度 = 8 个 tt 帧各自对 8 个 xhs 帧的最大 cos -> 求均值
- 用匈牙利算法做一一匹配 (tt 与 xhs 双侧均不重复), 再过阈值
- 输出 match_pairs_vembed.csv + 回写 matched_xhs_id

依赖: requests, numpy, scipy
环境: SILICONFLOW_API_KEY
"""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.optimize import linear_sum_assignment

API_URL = "https://api.siliconflow.cn/v1/embeddings"
MODEL = "Qwen/Qwen3-VL-Embedding-8B"


def img_data_url(p: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


def embed_one(img_url: str, api_key: str, retries: int = 3):
    # type: -> Optional[np.ndarray]; py3.9 兼容
    last_err = ""
    for k in range(retries):
        try:
            r = requests.post(API_URL, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }, json={"model": MODEL, "input": img_url}, timeout=120)
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code} body={r.text[:200]}"
                if r.status_code in (429, 500, 502, 503, 504):
                    import time; time.sleep(2 + k * 2)
                    continue
                return None
            v = np.asarray(r.json()["data"][0]["embedding"], dtype=np.float32)
            n = np.linalg.norm(v)
            return v / (n + 1e-9)
        except Exception as e:
            last_err = repr(e); import time; time.sleep(1 + k)
    print(f"[M3.6-WARN] embed fail after {retries} tries: {last_err}")
    return None


def embed_video(frames_dir: Path, cache_npy: Path, api_key: str) -> np.ndarray:
    """返回 (n_frames, dim). 命中缓存就直接读."""
    if cache_npy.exists():
        return np.load(cache_npy)
    frames = sorted(frames_dir.glob("f*.jpg"))
    if not frames:
        return np.zeros((0, 0), dtype=np.float32)
    vecs = []
    for f in frames:
        v = embed_one(img_data_url(f), api_key)
        if v is not None:
            vecs.append(v)
    if not vecs:
        print(f"[M3.6-WARN] all frames failed for {frames_dir.name}")
        return np.zeros((0, 0), dtype=np.float32)
    arr = np.stack(vecs)
    cache_npy.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_npy, arr)
    return arr


def embed_side(frames_root: Path, cache_root: Path, api_key: str) -> dict[str, np.ndarray]:
    out = {}
    ids = sorted([p.name for p in frames_root.iterdir() if p.is_dir()])
    for i, pid in enumerate(ids, 1):
        arr = embed_video(frames_root / pid, cache_root / f"{pid}.npy", api_key)
        if arr.shape[0] == 0:
            print(f"[M3.6-SKIP] {pid}")
            continue
        out[pid] = arr
        if i % 10 == 0 or i == len(ids):
            print(f"[M3.6] {frames_root.name}: {i}/{len(ids)}")
    return out


def pair_score(a: np.ndarray, b: np.ndarray) -> float:
    """非对称: 对 a 的每帧取它对 b 所有帧的 max cos, 再均值."""
    sim = a @ b.T            # (na, nb)
    return float(sim.max(axis=1).mean())


def run(
    xhs_frames: Path, tt_frames: Path,
    cache_root: Path, out_pairs: Path,
    tt_meta: Path, threshold: float,
) -> None:
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise SystemExit("SILICONFLOW_API_KEY 未设置")

    print("[M3.6] embedding xhs ...")
    xhs = embed_side(xhs_frames, cache_root / "xhs", api_key)
    print("[M3.6] embedding tiktok ...")
    tt = embed_side(tt_frames, cache_root / "tiktok", api_key)
    print(f"[M3.6] xhs={len(xhs)} tt={len(tt)}")

    tt_ids = list(tt.keys()); xhs_ids = list(xhs.keys())
    nT, nX = len(tt_ids), len(xhs_ids)
    score = np.zeros((nT, nX), dtype=np.float32)
    for i, tid in enumerate(tt_ids):
        for j, xid in enumerate(xhs_ids):
            score[i, j] = pair_score(tt[tid], xhs[xid])

    # 匈牙利: 最大化总相似度 -> 最小化 -score
    ri, ci = linear_sum_assignment(-score)
    assigned = {tt_ids[i]: (xhs_ids[j], float(score[i, j])) for i, j in zip(ri, ci)}

    # 也记录每个 tt 的 top1 (未受一一约束) 供对比
    rows = []
    for i, tid in enumerate(tt_ids):
        top_j = int(score[i].argmax())
        top1_xid, top1_s = xhs_ids[top_j], float(score[i, top_j])
        assn_xid, assn_s = assigned.get(tid, ("", -1.0))
        rows.append({
            "tiktok_id": tid,
            "assigned_xhs_id": assn_xid,
            "assigned_score": round(assn_s, 4),
            "top1_xhs_id": top1_xid,
            "top1_score": round(top1_s, 4),
            "matched": assn_s >= threshold,
        })
    df = pd.DataFrame(rows).sort_values("assigned_score", ascending=False)
    out_pairs.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_pairs, index=False)
    n_m = int(df["matched"].sum())
    print(f"[M3.6] matched={n_m}/{len(df)} (thr={threshold}) -> {out_pairs}")

    # 回写 matched_xhs_id
    tt_df = pd.read_csv(tt_meta, dtype={"帖子id": str})
    id2x = {r.tiktok_id: (r.assigned_xhs_id if r.matched else "") for r in df.itertuples()}
    tt_df["matched_xhs_id"] = tt_df["帖子id"].astype(str).map(id2x).fillna("")
    tt_df.to_csv(tt_meta, index=False)
    print(f"[M3.6] wrote matched_xhs_id -> {tt_meta}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--xhs-frames", required=True, help="目录, 子目录是 {id}/f*.jpg")
    p.add_argument("--tt-frames", required=True)
    p.add_argument("--cache-root", required=True)
    p.add_argument("--out-pairs", required=True)
    p.add_argument("--tt-meta", required=True)
    p.add_argument("--threshold", type=float, default=0.55,
                   help="cos 相似度阈值; Qwen3-VL-Embed 一般 >=0.55 视为同源候选")
    a = p.parse_args()
    run(Path(a.xhs_frames), Path(a.tt_frames),
        Path(a.cache_root), Path(a.out_pairs),
        Path(a.tt_meta), a.threshold)


if __name__ == "__main__":
    main()
