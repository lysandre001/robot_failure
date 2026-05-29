"""
M3.7: 双证据融合 (pHash ∧ vembed) -> 最终一一匹配
- 重算两个完整 (tt, xhs) 矩阵:
    * pHash min-hamming  (用 _phash_frames/ 里的帧)
    * vembed max-mean cosine (用 _vembed_cache/ 里缓存的 .npy)
- 双阈值过滤: hamming<=h_thr 且 cos>=v_thr 才算候选
- 对候选用匈牙利做一一匹配, 保留唯一最优配对
- 写出 match_pairs_fused.csv + 回写 matched_xhs_id

无 API 调用 (复用已缓存的 embedding 与已抽帧).
"""
from __future__ import annotations
import argparse
from pathlib import Path

import imagehash
import numpy as np
import pandas as pd
from PIL import Image
from scipy.optimize import linear_sum_assignment


def load_phash(frames_root: Path) -> dict[str, np.ndarray]:
    out = {}
    for d in sorted(frames_root.iterdir()):
        if not d.is_dir(): continue
        hs = []
        for f in sorted(d.glob("f*.jpg")):
            try:
                hs.append(np.array(imagehash.phash(Image.open(f)).hash).flatten())
            except Exception:
                pass
        if hs:
            out[d.name] = np.stack(hs)
    return out


def load_vembed(cache_root: Path) -> dict[str, np.ndarray]:
    out = {}
    for f in sorted(cache_root.glob("*.npy")):
        a = np.load(f)
        if a.size > 0:
            out[f.stem] = a
    return out


def hamming_matrix(A: np.ndarray, B: np.ndarray) -> int:
    """min hamming over all frame pairs."""
    a = A.astype(np.int8)[:, None, :]
    b = B.astype(np.int8)[None, :, :]
    return int(np.min(np.sum(a ^ b, axis=2)))


def vembed_score(A: np.ndarray, B: np.ndarray) -> float:
    """对 a 每帧取它对 b 所有帧的 max cos, 再均值."""
    return float((A @ B.T).max(axis=1).mean())


def run(
    phash_frames_root: Path, vembed_cache_root: Path,
    tt_meta: Path, out_pairs: Path,
    h_thr: int, v_thr: float,
) -> None:
    # pHash
    xhs_h = load_phash(phash_frames_root / "xhs")
    tt_h  = load_phash(phash_frames_root / "tiktok")
    # vembed
    xhs_v = load_vembed(vembed_cache_root / "xhs")
    tt_v  = load_vembed(vembed_cache_root / "tiktok")

    # 双方都有的 id 才纳入
    xhs_ids = sorted(set(xhs_h) & set(xhs_v))
    tt_ids  = sorted(set(tt_h)  & set(tt_v))
    print(f"[M3.7] xhs={len(xhs_ids)} tt={len(tt_ids)}")

    nT, nX = len(tt_ids), len(xhs_ids)
    H = np.full((nT, nX), 99, dtype=np.int16)
    V = np.full((nT, nX), -1.0, dtype=np.float32)
    for i, tid in enumerate(tt_ids):
        for j, xid in enumerate(xhs_ids):
            H[i, j] = hamming_matrix(tt_h[tid], xhs_h[xid])
            V[i, j] = vembed_score(tt_v[tid], xhs_v[xid])

    # 双阈值候选
    cand = (H <= h_thr) & (V >= v_thr)
    n_cand = int(cand.sum())
    print(f"[M3.7] candidates (H<={h_thr} & V>={v_thr}): {n_cand}")

    # 在候选子集上做一一匹配 (匈牙利) -> 最大化 V; 非候选 cost 设 +inf
    cost = np.where(cand, -V, 1e6).astype(np.float64)
    ri, ci = linear_sum_assignment(cost)
    assigned = []
    for i, j in zip(ri, ci):
        if cand[i, j]:
            assigned.append((tt_ids[i], xhs_ids[j], int(H[i, j]), float(V[i, j])))
    print(f"[M3.7] final 1-to-1 matched: {len(assigned)}")

    # 输出: 所有 tt 一行, 含其与各 xhs 的最优 (按 V 倒序) + 是否中签
    rows = []
    chosen = {t: (x, h, v) for (t, x, h, v) in assigned}
    for i, tid in enumerate(tt_ids):
        top_j = int(V[i].argmax())
        rows.append({
            "tiktok_id": tid,
            "matched": tid in chosen,
            "matched_xhs_id": chosen[tid][0] if tid in chosen else "",
            "matched_hamming": chosen[tid][1] if tid in chosen else "",
            "matched_vembed":  round(chosen[tid][2], 4) if tid in chosen else "",
            "top1_xhs_id": xhs_ids[top_j],
            "top1_vembed": round(float(V[i, top_j]), 4),
            "top1_hamming": int(H[i, top_j]),
        })
    df = pd.DataFrame(rows).sort_values(["matched", "matched_vembed"], ascending=[False, False])
    out_pairs.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_pairs, index=False)
    print(f"[M3.7] -> {out_pairs}")

    # 回写 matched_xhs_id (覆盖之前 M3.5/M3.6 的结果)
    tt_df = pd.read_csv(tt_meta, dtype={"帖子id": str})
    id2x = {t: x for (t, x, _, _) in assigned}
    tt_df["matched_xhs_id"] = tt_df["帖子id"].astype(str).map(id2x).fillna("")
    tt_df.to_csv(tt_meta, index=False)
    print(f"[M3.7] wrote matched_xhs_id -> {tt_meta}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--phash-frames-root", default="output/video_match/_phash_frames")
    p.add_argument("--vembed-cache-root", default="output/video_match/_vembed_cache")
    p.add_argument("--tt-meta",   default="output/video_match/tiktok_post_category_by_post.csv")
    p.add_argument("--out-pairs", default="output/video_match/match_pairs_fused.csv")
    p.add_argument("--h-thr", type=int,   default=12, help="pHash min-hamming 上限")
    p.add_argument("--v-thr", type=float, default=0.93, help="vembed cosine 下限")
    a = p.parse_args()
    run(Path(a.phash_frames_root), Path(a.vembed_cache_root),
        Path(a.tt_meta), Path(a.out_pairs), a.h_thr, a.v_thr)


if __name__ == "__main__":
    main()
