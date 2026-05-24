"""人工标注抽样逻辑（库函数；CLI 见 tools/sample_manual_label.py）。"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from phase1.config import POST_CATEGORY_BY_POST_CSV, ROOT


def _batch1_post_ids() -> set[str]:
    xlsx = ROOT / "1-小红书帖子数据.xlsx"
    if xlsx.is_file():
        df = pd.read_excel(xlsx, sheet_name="小红书帖子数据", usecols=["帖子id"])
        return set(df["帖子id"].astype(str))
    return set(pd.read_csv(POST_CATEGORY_BY_POST_CSV, encoding="utf-8-sig")["帖子id"].astype(str))


def sample_l1_per_post(
    df: pd.DataFrame,
    *,
    n_per_post: int = 30,
    n_high_like: int | None = None,
    random_seed: int = 42,
) -> pd.DataFrame:
    """每帖最多 ``n_per_post`` 条一级评论；默认一半按 ``like_count`` 高、一半随机。"""
    if "comment_level" not in df.columns:
        raise ValueError("输入需含 comment_level 列")
    l1 = df[df["comment_level"] == 1].copy()
    if l1.empty:
        raise ValueError("无一级评论")

    n_high = n_high_like if n_high_like is not None else n_per_post // 2
    n_rand = n_per_post - n_high
    rng = np.random.default_rng(random_seed)

    parts: list[pd.DataFrame] = []
    for _pid, grp in l1.groupby("帖子id", sort=False):
        grp = grp.copy()
        grp["like_count"] = pd.to_numeric(grp["like_count"], errors="coerce").fillna(0)
        k = min(n_per_post, len(grp))
        if k == 0:
            continue
        nh = min(n_high, k)
        nr = k - nh

        picked_idx: set = set()
        if nh > 0:
            top = grp.nlargest(nh, "like_count")
            picked_idx.update(top.index)
        rest = grp.loc[~grp.index.isin(picked_idx)]
        if nr > 0 and len(rest) > 0:
            take = min(nr, len(rest))
            ri = rng.choice(rest.index.to_numpy(), size=take, replace=False)
            picked_idx.update(ri)

        sub = grp.loc[list(picked_idx)].copy()
        sub["sample_stratum"] = "l1_per_post_mixed"
        sub["sample_rank_in_post"] = range(1, len(sub) + 1)
        parts.append(sub)

    return pd.concat(parts, ignore_index=True)


def enrich_for_labeling(sample: pd.DataFrame, *, doc_topics_path: Path | None) -> pd.DataFrame:
    b1 = _batch1_post_ids()
    out = sample.copy()
    out["corpus"] = out["帖子id"].astype(str).map(lambda x: "batch1" if x in b1 else "batch2_anchor")
    out["bert_topic_k7"] = pd.NA
    if doc_topics_path and doc_topics_path.is_file():
        dt = pd.read_csv(doc_topics_path, usecols=["comment_id", "topic"])
        dt = dt.rename(columns={"topic": "bert_topic_k7"})
        out = out.drop(columns=["bert_topic_k7"], errors="ignore")
        out = out.merge(dt, on="comment_id", how="left")

    for col in ("open_code", "axial_code", "memo", "exclude_from_coding", "coder"):
        if col not in out.columns:
            out[col] = ""
    return out
