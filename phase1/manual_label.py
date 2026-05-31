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
    posts_csv = ROOT / "data" / "rawdata" / "posts.csv"
    if posts_csv.is_file():
        df = pd.read_csv(posts_csv, usecols=["帖子id"])
        return set(df["帖子id"].astype(str).head(16))
    return set(pd.read_csv(POST_CATEGORY_BY_POST_CSV, encoding="utf-8-sig")["帖子id"].astype(str).head(16))


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


def _normalize_content(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)


def sample_l1_increment_per_post(
    df: pd.DataFrame,
    *,
    target_per_post: int = 20,
    exclude_comment_ids: set[str] | None = None,
    exclude_content: set[str] | None = None,
    existing_l1_counts: dict[str, int] | None = None,
    post_ids: list[str] | None = None,
    n_high_like: int | None = None,
    random_seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    在排除已有 comment_id / content 后，每帖再抽一级评论直至达到 target（或池子用尽）。

    返回 (new_samples, report_df)。
    """
    if "comment_level" not in df.columns:
        raise ValueError("输入需含 comment_level 列")
    ex_ids = exclude_comment_ids or set()
    ex_txt = exclude_content or set()
    counts = dict(existing_l1_counts or {})

    l1 = df[df["comment_level"] == 1].copy()
    l1["_content_norm"] = _normalize_content(l1["content"])
    l1 = l1[
        ~l1["comment_id"].astype(str).isin(ex_ids)
        & ~l1["_content_norm"].isin(ex_txt)
    ]
    if post_ids is not None:
        allow = set(post_ids)
        l1 = l1[l1["帖子id"].astype(str).isin(allow)]

    n_high_default = target_per_post // 2
    rng = np.random.default_rng(random_seed)
    parts: list[pd.DataFrame] = []
    report_rows: list[dict] = []

    for pid, grp in l1.groupby("帖子id", sort=False):
        pid = str(pid)
        already = int(counts.get(pid, 0))
        need = max(0, target_per_post - already)
        pool_n = len(grp)
        if need <= 0 or pool_n == 0:
            report_rows.append(
                {
                    "帖子id": pid,
                    "l1_existing": already,
                    "l1_target": target_per_post,
                    "l1_need": need,
                    "l1_pool": pool_n,
                    "l1_sampled": 0,
                    "l1_final": already,
                    "status": "skip_full" if need <= 0 else "no_pool",
                }
            )
            continue

        grp = grp.copy()
        grp["like_count"] = pd.to_numeric(grp["like_count"], errors="coerce").fillna(0)
        k = min(need, pool_n)
        nh = min(n_high_like if n_high_like is not None else n_high_default, k)
        nr = k - nh
        picked: set = set()
        if nh > 0:
            picked.update(grp.nlargest(nh, "like_count").index)
        rest = grp.loc[~grp.index.isin(picked)]
        if nr > 0 and len(rest) > 0:
            take = min(nr, len(rest))
            picked.update(rng.choice(rest.index.to_numpy(), size=take, replace=False))

        sub = grp.loc[list(picked)].drop(columns=["_content_norm"], errors="ignore").copy()
        sub["sample_stratum"] = "l1_increment_mixed"
        sub["sample_rank_in_post"] = range(already + 1, already + len(sub) + 1)
        parts.append(sub)
        report_rows.append(
            {
                "帖子id": pid,
                "l1_existing": already,
                "l1_target": target_per_post,
                "l1_need": need,
                "l1_pool": pool_n,
                "l1_sampled": len(sub),
                "l1_final": already + len(sub),
                "status": "ok" if len(sub) >= need else "shortfall",
            }
        )

    new_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return new_df, pd.DataFrame(report_rows)


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
