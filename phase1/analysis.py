"""步骤 C：汇总统计、制图、主题聚类。"""
from __future__ import annotations

import json
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from phase1.config import FIG, OUT
from phase1.features import cooccur_tokens, top_ngrams_char

try:
    import jieba  # type: ignore
except ImportError:  # pragma: no cover
    jieba = None


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)


def interaction_map(l1: pd.DataFrame) -> None:
    g = (
        l1.groupby("post_category")
        .agg(
            posts=("帖子id", "nunique"),
            l1_comments=("comment_id", "count"),
            mean_l1_likes=("like_count", "mean"),
            median_l1_likes=("like_count", "median"),
            mean_replies=("reply_count", "mean"),
            median_replies=("reply_count", "median"),
            mean_len=("content", lambda s: s.astype(str).str.len().mean()),
        )
        .reset_index()
    )
    g.to_csv(OUT / "interaction_by_category.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4))
    cats = g["post_category"].tolist()
    x = np.arange(len(cats))
    ax.bar(x - 0.2, g["l1_comments"], 0.35, label="一级评论数")
    ax2 = ax.twinx()
    ax2.bar(x + 0.2, g["mean_replies"].fillna(0), 0.35, label="均值回复数", color="orange", alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=25, ha="right")
    ax.set_ylabel("一级评论条数")
    ax2.set_ylabel("一级评论平均二级回复数")
    ax.legend(loc="upper left")
    ax2.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG / "interaction_l1_by_category.png", dpi=150)
    plt.close(fig)

    l1.nlargest(30, "reply_count")[
        ["帖子id", "post_category", "comment_id", "reply_count", "like_count", "content"]
    ].to_csv(OUT / "top_high_reply_l1.csv", index=False)


def role_aggregate(enriched: pd.DataFrame) -> None:
    role_cols = [c for c in enriched.columns if c.startswith("role_")]
    g = enriched.groupby(["post_category", "comment_level"])[role_cols].mean().reset_index()
    g.to_csv(OUT / "role_scores_by_category_level.csv", index=False)
    for level in [1, 2]:
        sub = g[g["comment_level"] == level].set_index("post_category")[role_cols]
        if sub.empty:
            continue
        fig, ax = plt.subplots(figsize=(10, 4))
        im = ax.imshow(sub.values, aspect="auto", cmap="YlOrRd")
        ax.set_xticks(range(len(role_cols)))
        ax.set_xticklabels([c.replace("role_", "") for c in role_cols], rotation=35, ha="right")
        ax.set_yticks(range(len(sub.index)))
        ax.set_yticklabels(sub.index)
        plt.colorbar(im, ax=ax)
        ax.set_title(f"角色词典命中密度 (mean hits) — comment_level {level}")
        fig.tight_layout()
        fig.savefig(FIG / f"role_heatmap_L{level}.png", dpi=150)
        plt.close(fig)


def personhood_outputs(enriched: pd.DataFrame) -> None:
    ph_cols = [c for c in enriched.columns if c.startswith("ph_")]
    g = enriched.groupby(["post_category", "comment_level"])[ph_cols].mean().reset_index()
    g.to_csv(OUT / "personhood_by_category_level.csv", index=False)
    co_texts = enriched[enriched["post_category"] != "unknown"]["content"].tolist()
    cap = min(5000, len(co_texts))
    co = cooccur_tokens(co_texts[:cap], {"机器人", "它", "他"})
    (OUT / "cooccurrence_robot_pronouns.json").write_text(
        json.dumps({k: v for k, v in co.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def meme_outputs(enriched: pd.DataFrame) -> None:
    enriched[enriched["template_style"] == True].groupby(["post_category", "comment_level"]).size().reset_index(  # noqa: E712
        name="n"
    ).to_csv(OUT / "meme_template_counts.csv", index=False)
    enriched[(enriched["ha_repeat"] > 0) | (enriched["emoji_count"] > 2)].nlargest(
        200, "like_count"
    )[["帖子id", "post_category", "comment_level", "like_count", "content"]].to_csv(
        OUT / "meme_heavy_highlike_sample.csv", index=False
    )
    rows = []
    for cat, sub in enriched[enriched["comment_level"] == 1].groupby("post_category"):
        for s, c in top_ngrams_char(sub["content"].tolist(), n=4, top=25):
            rows.append({"post_category": cat, "ngram": s, "count": c})
    pd.DataFrame(rows).to_csv(OUT / "char4grams_top_by_category_L1.csv", index=False)


def boundary_outputs(enriched: pd.DataFrame) -> None:
    bd_cols = [c for c in enriched.columns if c.startswith("bd_")]
    g = enriched.groupby(["post_category", "comment_level"])[bd_cols].mean().reset_index()
    g.to_csv(OUT / "boundary_by_category_level.csv", index=False)
    c = enriched["content"].fillna("").astype(str)
    mask = c.str.contains("人") & c.str.contains("机器|钢铁|程序|算法", regex=True)
    sub = enriched.loc[mask, ["post_category", "comment_level", "like_count", "content"]].copy()
    sub["content"] = sub["content"].astype(str).str[:300]
    sub["like_count"] = pd.to_numeric(sub["like_count"], errors="coerce").fillna(0)
    sub.nlargest(150, "like_count").to_csv(OUT / "boundary_contrast_sample.csv", index=False)


def topic_clusters(comments: list[str], categories: list[str], top_n: int = 8000) -> None:
    if len(comments) < 100:
        return
    n_samples = min(len(comments), top_n)
    idx = np.random.RandomState(42).choice(len(comments), size=n_samples, replace=False)
    texts = [comments[i] for i in idx]
    cats = [categories[i] for i in idx]

    vec = TfidfVectorizer(
        max_features=4000,
        min_df=5,
        max_df=0.55,
        analyzer=lambda s: s.split(),
    )
    if jieba is not None:
        cut_texts = [" ".join(jieba.cut(t)) for t in texts]
    else:
        # 无 jieba 时降级为字符级切分，仅保证流程可运行
        cut_texts = [" ".join(ch for ch in str(t) if not ch.isspace()) for t in texts]
    X = vec.fit_transform(cut_texts)
    kmini = min(10, max(3, len(texts) // 200))
    km = MiniBatchKMeans(n_clusters=kmini, random_state=42, batch_size=256)
    labels = km.fit_predict(X)

    feat = np.array(vec.get_feature_names_out())
    rows = []
    for c in range(kmini):
        center = km.cluster_centers_[c]
        top_idx = center.argsort()[-15:][::-1]
        rows.append(
            {
                "cluster": c,
                "top_terms": ", ".join(feat[top_idx]),
                "size": int((labels == c).sum()),
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "topic_clusters_terms.csv", index=False)

    dist = defaultdict(lambda: defaultdict(int))
    for lab, ca in zip(labels, cats):
        dist[int(lab)][ca] += 1
    flat = []
    for lab, d in dist.items():
        tot = sum(d.values())
        for ca, n in d.items():
            flat.append({"cluster": lab, "post_category": ca, "count": n, "share": n / tot})
    pd.DataFrame(flat).to_csv(OUT / "topic_cluster_by_category.csv", index=False)
