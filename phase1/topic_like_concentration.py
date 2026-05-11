"""BERTopic 各主题内：评论点赞是否集中在少数「爆款评论」（高赞评论）。"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from phase1.topic_post_dominance import compute_post_dominance, resolve_topic_column


def _top_k_share(likes: np.ndarray, k: int) -> float:
    if likes.size == 0 or likes.sum() <= 0:
        return float("nan")
    k = min(k, likes.size)
    idx = np.argpartition(-likes, k - 1)[:k]
    return float(likes[idx].sum() / likes.sum())


def _top_frac_share(likes: np.ndarray, frac: float) -> float:
    """点赞最高的 ceil(frac * n) 条评论，其点赞之和占主题总赞的比例。"""
    if likes.size == 0 or likes.sum() <= 0:
        return float("nan")
    k = max(1, int(np.ceil(frac * likes.size)))
    k = min(k, likes.size)
    idx = np.argpartition(-likes, k - 1)[:k]
    return float(likes[idx].sum() / likes.sum())


def _gini_nonneg(x: np.ndarray) -> float:
    """Gini，x 为非负；全 0 返回 0。"""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return float("nan")
    s = x.sum()
    if s <= 0:
        return 0.0
    xs = np.sort(x)
    n = xs.size
    cum = np.cumsum(xs)
    return float((n + 1 - 2 * (cum.sum() / cum[-1])) / n)


def compute_topic_like_concentration(
    doc_topics: pd.DataFrame,
    like_by_comment: pd.DataFrame,
    *,
    topic_col: str | None = None,
    comment_col: str = "comment_id",
    like_col: str = "like_count",
) -> pd.DataFrame:
    """
    每个主题：爆款评论（高赞）是否占主导。

    指标
    ----
    viral_top1_share
        单条最高赞评论的赞数 / 该主题总赞数。
    viral_top5_share
        赞数最高的 5 条评论的赞数之和 / 主题总赞数。
    viral_top1pct_share
        赞数最高的约 1% 条评论（至少 1 条）的赞数之和 / 主题总赞数。
    like_gini
        主题内各评论点赞的基尼系数（0=完全平均，越接近 1 越集中在少数高赞）。
    n_zero_like
        该主题内点赞为 0 或缺失（按 0 计）的评论条数。
    """
    tcol = resolve_topic_column(doc_topics, topic_col)
    m = doc_topics[[comment_col, tcol]].merge(
        like_by_comment[[comment_col, like_col]],
        on=comment_col,
        how="left",
    )
    m[like_col] = pd.to_numeric(m[like_col], errors="coerce").fillna(0.0).clip(lower=0)

    rows = []
    for topic, g in m.groupby(tcol, sort=True):
        likes = g[like_col].to_numpy(dtype=float)
        n = int(len(likes))
        s = float(likes.sum())
        n_zero = int((likes <= 0).sum())
        rows.append(
            {
                "topic": topic,
                "n_comments": n,
                "sum_likes": s,
                "mean_like": s / n if n else float("nan"),
                "max_like": float(likes.max()) if n else float("nan"),
                "viral_top1_share": float(likes.max() / s) if s > 0 else float("nan"),
                "viral_top5_share": _top_k_share(likes, 5),
                "viral_top1pct_share": _top_frac_share(likes, 0.01),
                "like_gini": _gini_nonneg(likes),
                "n_zero_like": n_zero,
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values("topic").reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser(description="主题内评论点赞集中度（爆款评论主导程度）")
    p.add_argument("--doc-topics", type=str, required=True)
    p.add_argument(
        "--shared-corpus",
        type=str,
        default=None,
        help="shared_analyzable_corpus.csv（默认同实验目录）",
    )
    p.add_argument("--topic-col", type=str, default=None)
    p.add_argument("--out", type=str, default=None)
    args = p.parse_args()

    dt_path = Path(args.doc_topics)
    shared_path = (
        Path(args.shared_corpus)
        if args.shared_corpus
        else dt_path.parents[1] / "shared_analyzable_corpus.csv"
    )
    if not shared_path.is_file():
        raise FileNotFoundError(f"找不到 shared corpus: {shared_path}")

    doc_topics = pd.read_csv(dt_path)
    shared = pd.read_csv(shared_path, usecols=["comment_id", "like_count"])

    tab = compute_topic_like_concentration(
        doc_topics, shared, topic_col=args.topic_col
    )
    post_dom = compute_post_dominance(doc_topics, topic_col=args.topic_col)
    tab = tab.merge(
        post_dom[["topic", "post_dominance", "dominant_post_id"]],
        on="topic",
        how="left",
    )

    out_path = Path(args.out) if args.out else dt_path.parent / "topic_viral_concentration.csv"
    tab.to_csv(out_path, index=False)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    print(tab.to_string(index=False))
    print(f"\nwritten: {out_path}", flush=True)


if __name__ == "__main__":
    main()
