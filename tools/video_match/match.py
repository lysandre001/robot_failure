"""
M4: 跨平台同视频匹配
- 两边各自的签名 = 帖子正文 (+ 标题) + M3 生成的 caption/robots/scene/event
- 用 SiliconFlow BAAI/bge-m3 文本嵌入, cosine sim
- 对每个 tiktok post 找最相似 xhs post, sim >= threshold 即认定同源
- 输出:
    1) match_pairs.csv (全部 tiktok 的 top1 候选, 含分数, 供人工抽检)
    2) 回写 tiktok_post_category_by_post.csv 的 matched_xhs_id 列

xhs 一侧字段由 --xhs-meta 指定 (id, text); tiktok 一侧已在 M1 输出中.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests

EMBED_URL = "https://api.siliconflow.cn/v1/embeddings"
EMBED_MODEL = "BAAI/bge-m3"


def load_captions(jsonl: Path) -> dict[str, str]:
    if not jsonl.exists():
        return {}
    out = {}
    for line in jsonl.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        pid = str(r.get("id", ""))
        parts = [r.get(k, "") for k in ("caption", "robots", "humans", "scene", "event")]
        out[pid] = " | ".join([p for p in parts if p])
    return out


def build_side(meta_csv: Path, captions_jsonl: Path, id_col: str, text_cols: list[str]) -> pd.DataFrame:
    df = pd.read_csv(meta_csv, dtype={id_col: str})
    df = df.drop_duplicates(id_col)
    df["_text"] = df[text_cols].fillna("").astype(str).agg(" ".join, axis=1)
    caps = load_captions(captions_jsonl)
    df["_caption"] = df[id_col].map(caps).fillna("")
    df["_sig"] = (df["_text"] + " || " + df["_caption"]).str.strip()
    return df[[id_col, "_text", "_caption", "_sig"]].rename(columns={id_col: "id"})


def embed(texts: list[str], api_key: str, batch: int = 16) -> np.ndarray:
    vecs = []
    for i in range(0, len(texts), batch):
        chunk = texts[i:i + batch]
        r = requests.post(EMBED_URL, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }, json={"model": EMBED_MODEL, "input": chunk}, timeout=120)
        r.raise_for_status()
        for d in r.json()["data"]:
            vecs.append(d["embedding"])
    a = np.asarray(vecs, dtype=np.float32)
    a /= np.linalg.norm(a, axis=1, keepdims=True) + 1e-9
    return a


def run(
    xhs_meta: Path, xhs_caps: Path,
    tt_meta: Path, tt_caps: Path,
    out_pairs: Path, threshold: float,
) -> None:
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise SystemExit("SILICONFLOW_API_KEY 未设置")

    xhs = build_side(xhs_meta, xhs_caps, id_col="帖子id", text_cols=["帖子正文"])
    tt = build_side(tt_meta, tt_caps, id_col="帖子id", text_cols=["帖子标题", "帖子正文"])
    print(f"[M4] xhs={len(xhs)} tiktok={len(tt)}")

    xv = embed(xhs["_sig"].tolist(), api_key)
    tv = embed(tt["_sig"].tolist(), api_key)
    sim = tv @ xv.T          # [n_tt, n_xhs]
    best = sim.argmax(axis=1)
    score = sim.max(axis=1)

    pairs = pd.DataFrame({
        "tiktok_id": tt["id"].values,
        "tiktok_text": tt["_text"].values.astype(str),
        "tiktok_caption": tt["_caption"].values.astype(str),
        "xhs_id": xhs["id"].values[best],
        "xhs_text": xhs["_text"].values[best].astype(str),
        "xhs_caption": xhs["_caption"].values[best].astype(str),
        "score": score,
        "matched": score >= threshold,
    }).sort_values("score", ascending=False)

    out_pairs.parent.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(out_pairs, index=False)
    print(f"[M4] matched={int(pairs['matched'].sum())}/{len(pairs)} thr={threshold} -> {out_pairs}")

    # 回写 tt_meta 的 matched_xhs_id 列
    tt_df = pd.read_csv(tt_meta, dtype={"帖子id": str})
    id2xhs = dict(zip(pairs["tiktok_id"].astype(str),
                      np.where(pairs["matched"], pairs["xhs_id"].astype(str), "")))
    tt_df["matched_xhs_id"] = tt_df["帖子id"].astype(str).map(id2xhs).fillna("")
    tt_df.to_csv(tt_meta, index=False)
    print(f"[M4] wrote matched_xhs_id back to {tt_meta}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--xhs-meta", required=True, help="csv with 帖子id + 帖子正文")
    p.add_argument("--xhs-caps", required=True, help="jsonl from M3")
    p.add_argument("--tt-meta", required=True, help="M1 output csv")
    p.add_argument("--tt-caps", required=True, help="jsonl from M3")
    p.add_argument("--out-pairs", required=True)
    p.add_argument("--threshold", type=float, default=0.78)
    a = p.parse_args()
    run(Path(a.xhs_meta), Path(a.xhs_caps),
        Path(a.tt_meta), Path(a.tt_caps),
        Path(a.out_pairs), a.threshold)


if __name__ == "__main__":
    main()
