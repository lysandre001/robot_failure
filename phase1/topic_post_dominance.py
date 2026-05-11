"""按 BERTopic 的 doc_topics 表计算每个主题的帖子集中度 post_dominance。"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def resolve_topic_column(df: pd.DataFrame, topic_col: str | None) -> str:
    if topic_col is not None:
        if topic_col not in df.columns:
            raise ValueError(f"无列: {topic_col}")
        return topic_col
    if "topic" in df.columns:
        return "topic"
    if "topic_assigned" in df.columns:
        return "topic_assigned"
    if "topic_raw" in df.columns:
        return "topic_raw"
    raise ValueError("未找到 topic / topic_assigned / topic_raw 列")


def compute_post_dominance(
    df: pd.DataFrame,
    *,
    topic_col: str | None = None,
    post_col: str = "帖子id",
) -> pd.DataFrame:
    """
    对每个主题 t：post_dominance(t) = 该主题内，评论数最多的单个帖子所占比例。

    Returns
    -------
    DataFrame 列: topic, n_comments, dominant_post_id, n_on_dominant_post, post_dominance
    """
    tcol = resolve_topic_column(df, topic_col)
    if post_col not in df.columns:
        raise ValueError(f"无列: {post_col}")

    rows = []
    for topic, g in df.groupby(tcol, sort=True):
        vc = g[post_col].astype(str).value_counts()
        top_post = vc.index[0]
        n_on_top = int(vc.iloc[0])
        n = int(len(g))
        rows.append(
            {
                "topic": topic,
                "n_comments": n,
                "dominant_post_id": top_post,
                "n_on_dominant_post": n_on_top,
                "post_dominance": n_on_top / n if n else float("nan"),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values("topic").reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser(description="BERTopic 主题级 post_dominance 表")
    p.add_argument("--doc-topics", type=str, required=True, help="doc_topics.csv 路径")
    p.add_argument("--topic-col", type=str, default=None, help="默认自动识别")
    p.add_argument(
        "--out",
        type=str,
        default=None,
        help="输出 CSV（默认与 doc_topics 同目录 post_dominance_by_topic.csv）",
    )
    args = p.parse_args()

    path = Path(args.doc_topics)
    df = pd.read_csv(path)
    tab = compute_post_dominance(df, topic_col=args.topic_col)
    out_path = Path(args.out) if args.out else path.parent / "post_dominance_by_topic.csv"
    tab.to_csv(out_path, index=False)
    print(tab.to_string(index=False))
    print(f"\nwritten: {out_path}", flush=True)


if __name__ == "__main__":
    main()
