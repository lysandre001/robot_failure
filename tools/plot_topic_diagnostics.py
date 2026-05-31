"""Diagnostic figures 1–7 for L1/L2/Pooled topic discovery (visual.md helpers).

Outputs under ``<run>/topic_diagnostics/``:

1. outlier_rate_by_token.png — outlier rate vs effective token bin
2. token_ecdf_in_vs_out.png — ECDF of token length (in-cluster vs outlier)
3. umap_outlier_overlay.png — 2D UMAP colored by outlier status
4. topic_size_distribution.png — topic Count histogram (log y)
5. pooled_level_x_outlier.png — L1/L2 outlier rate (pooled labels)
6. top15_topics.png — top-15 topic share + label terms
7. mcs_sensitivity_panels.png — mcs → n_topics / outlier / largest_share

Usage::

    ./.venv/bin/python -m tools.plot_topic_diagnostics \\
        --run-id 2026-05-27_topic_merged_bge_hdbscan_sensitivity
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from phase1.config import ROOT
from phase1.topic_lda import _setup_tokenizer, load_topic_stopwords, tokenize_text

DEFAULT_RUN_ID = "2026-05-27_topic_merged_bge_hdbscan_sensitivity"
RANDOM_STATE = 42

LAYERS: tuple[tuple[str, str, int | None, int], ...] = (
    ("L1", "topic_discovery_l1", 1, 90),
    ("L2", "topic_discovery_l2", 2, 45),
    ("Pooled", "topic_discovery_review", None, 85),
)

TOKEN_BINS = [-0.5, 0.5, 1.5, 2.5, 3.5, 5.5, 8.5, 12.5, 20.5, 999]
TOKEN_LABELS = ["0", "1", "2", "3", "4-5", "6-8", "9-12", "13-20", "21+"]


def _setup_cjk_font() -> None:
    for family in ("Hiragino Sans GB", "PingFang SC", "Heiti TC", "Arial Unicode MS"):
        try:
            from matplotlib.font_manager import FontProperties, findfont

            findfont(FontProperties(family=family), fallback_to_default=False)
            plt.rcParams["font.sans-serif"] = [family] + plt.rcParams.get("font.sans-serif", [])
            plt.rcParams["axes.unicode_minus"] = False
            return
        except Exception:
            continue


def _parse_terms(x, n: int = 3) -> str:
    if pd.isna(x):
        return ""
    s = str(x)
    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, (list, tuple)):
            return " · ".join(str(t).strip() for t in obj if str(t).strip())[:n]
    except Exception:
        pass
    parts = [t.strip() for t in s.split(",") if t.strip()][:n]
    return " · ".join(parts)


def _load_doc_topics(run_dir: Path, review_subdir: str) -> pd.DataFrame:
    return pd.read_csv(run_dir / review_subdir / "final_model" / "doc_topics_final.csv")


def _token_len_series(content: pd.Series, stopwords: set[str]) -> pd.Series:
    _setup_tokenizer("jieba")
    return content.map(lambda s: len(tokenize_text(str(s), tokenizer="jieba", stopwords=stopwords)))


def _prepare_docs(run_dir: Path, stopwords: set[str]) -> dict[str, pd.DataFrame]:
    shared = pd.read_csv(run_dir / "shared_analyzable_corpus.csv")
    out: dict[str, pd.DataFrame] = {}
    for name, sub, level, _nr in LAYERS:
        doc = _load_doc_topics(run_dir, sub)
        doc["is_outlier"] = doc["topic_raw"].astype(int) == -1
        doc["char_len"] = doc["content"].astype(str).str.len()
        doc["token_len"] = _token_len_series(doc["content"], stopwords)
        if level is not None:
            doc["comment_level"] = level
        else:
            doc = doc.merge(shared[["comment_id", "comment_level"]], on="comment_id", how="left")
        out[name] = doc
    return out


def _fit_umap_5d(run_dir: Path, level: int | None, n_rows: int) -> np.ndarray:
    if level is None:
        reduced = np.load(run_dir / "umap_reduced.npy")
        if len(reduced) != n_rows:
            raise ValueError("pooled umap row mismatch")
        return reduced

    from umap import UMAP

    emb = np.load(run_dir / "embeddings.npy")
    shared = pd.read_csv(run_dir / "shared_analyzable_corpus.csv")
    idx = np.where(shared["comment_level"].to_numpy() == level)[0]
    sub_emb = emb[idx]
    n_neighbors = min(15, max(2, len(sub_emb) - 1))
    print(f"  UMAP 5D fit level={level} n={len(sub_emb)} …", flush=True)
    return UMAP(
        n_neighbors=n_neighbors,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=RANDOM_STATE,
    ).fit_transform(sub_emb)


def _reduce_5d_to_2d(reduced_5d: np.ndarray) -> np.ndarray:
    from umap import UMAP

    print(f"  UMAP 5D→2D n={len(reduced_5d)} …", flush=True)
    return UMAP(
        n_neighbors=15,
        n_components=2,
        min_dist=0.1,
        metric="euclidean",
        random_state=RANDOM_STATE,
    ).fit_transform(reduced_5d)


def plot_1_outlier_by_token(docs: dict[str, pd.DataFrame], out_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    for ax, (name, df) in zip(axes, docs.items()):
        df = df.copy()
        df["tok_bin"] = pd.cut(df["token_len"], bins=TOKEN_BINS, labels=TOKEN_LABELS)
        agg = df.groupby("tok_bin", observed=True).agg(rate=("is_outlier", "mean"), n=("is_outlier", "count"))
        ax.bar(range(len(agg)), agg["rate"], color="#c44e52", alpha=0.85)
        ax.set_xticks(range(len(agg)))
        ax.set_xticklabels(agg.index, rotation=45, ha="right")
        ax.set_ylim(0, 1)
        ax.axhline(df["is_outlier"].mean(), color="gray", ls="--", lw=1, label=f"overall {df['is_outlier'].mean():.1%}")
        ax.set_title(f"{name} (N={len(df):,})")
        ax.set_xlabel("effective tokens (jieba)")
        ax.legend(fontsize=8)
        for i, (rate, n) in enumerate(zip(agg["rate"], agg["n"])):
            ax.text(i, rate + 0.02, str(int(n)), ha="center", fontsize=7)
    axes[0].set_ylabel("outlier rate (topic_raw=-1)")
    fig.suptitle("1. Outlier rate by token length (not driven by ultra-short comments only)", fontsize=11)
    fig.tight_layout()
    path = out_dir / "01_outlier_rate_by_token.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_2_token_ecdf(docs: dict[str, pd.DataFrame], out_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, (name, df) in zip(axes, docs.items()):
        for label, mask, color in [
            ("in_cluster", ~df["is_outlier"], "#4c72b0"),
            ("outlier", df["is_outlier"], "#c44e52"),
        ]:
            vals = np.sort(df.loc[mask, "token_len"].to_numpy())
            if len(vals) == 0:
                continue
            y = np.arange(1, len(vals) + 1) / len(vals)
            ax.step(vals, y, where="post", label=f"{label} (med={np.median(vals):.0f})", color=color, lw=1.8)
        ax.set_xlim(left=-0.5)
        ax.set_ylim(0, 1)
        ax.set_title(name)
        ax.set_xlabel("effective tokens")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("ECDF")
    fig.suptitle("2. Token length ECDF: in-cluster vs outlier (distributions largely overlap)", fontsize=11)
    fig.tight_layout()
    path = out_dir / "02_token_ecdf_in_vs_out.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_3_umap_outlier(run_dir: Path, docs: dict[str, pd.DataFrame], out_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    level_map = {"L1": 1, "L2": 2, "Pooled": None}
    for ax, name in zip(axes, docs):
        df = docs[name]
        reduced_5d = _fit_umap_5d(run_dir, level_map[name], len(df))
        coords = _reduce_5d_to_2d(reduced_5d)
        out_m = df["is_outlier"].to_numpy()
        ax.scatter(coords[out_m, 0], coords[out_m, 1], s=2, c="#cccccc", alpha=0.35, linewidths=0, label="outlier")
        ax.scatter(coords[~out_m, 0], coords[~out_m, 1], s=3, c="#4c72b0", alpha=0.5, linewidths=0, label="in_cluster")
        ax.set_title(f"{name} · outlier {out_m.mean():.1%}")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.legend(fontsize=8, markerscale=2)
    fig.suptitle("3. 2D UMAP (viz only): outliers vs in-cluster — check if scattered vs clumped", fontsize=11)
    fig.tight_layout()
    path = out_dir / "03_umap_outlier_overlay.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_4_topic_size(run_dir: Path, out_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, (name, sub, _lvl, _nr) in zip(axes, LAYERS):
        topics = pd.read_csv(run_dir / sub / "final_model" / "topics_final.csv")
        counts = topics.loc[topics["Topic"].astype(int) >= 0, "Count"].astype(int)
        ax.hist(counts, bins=30, color="#55a868", alpha=0.85, edgecolor="white")
        ax.set_yscale("log")
        ax.set_title(f"{name}: {len(counts)} topics")
        ax.set_xlabel("comments per topic")
        ax.axvline(counts.median(), color="gray", ls="--", label=f"median={counts.median():.0f}")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("topic count (log scale)")
    fig.suptitle("4. Topic size distribution (final reduced model)", fontsize=11)
    fig.tight_layout()
    path = out_dir / "04_topic_size_distribution.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_5_level_x_outlier(docs: dict[str, pd.DataFrame], out_dir: Path) -> Path:
    pooled = docs["Pooled"]
    rows = []
    for lvl, lab in [(1, "L1"), (2, "L2")]:
        g = pooled[pooled["comment_level"] == lvl]
        rows.append({"level": lab, "in_cluster": (~g["is_outlier"]).mean(), "outlier": g["is_outlier"].mean(), "n": len(g)})
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.arange(len(df))
    ax.bar(x, df["in_cluster"], label="in_cluster", color="#4c72b0")
    ax.bar(x, df["outlier"], bottom=df["in_cluster"], label="outlier", color="#c44e52")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r.level}\n(n={int(r.n):,})" for r in df.itertuples()])
    ax.set_ylabel("share of comments")
    ax.set_ylim(0, 1)
    for i, r in enumerate(df.itertuples()):
        ax.text(i, 0.02, f"outlier {r.outlier:.1%}", ha="center", color="white", fontsize=9, weight="bold")
    ax.legend()
    fig.suptitle("5. Pooled HDBSCAN: outlier rate by comment_level", fontsize=11)
    fig.tight_layout()
    path = out_dir / "05_pooled_level_x_outlier.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_6_top_topics(run_dir: Path, out_dir: Path, top_n: int = 15) -> Path:
    fig, axes = plt.subplots(3, 1, figsize=(11, 12))
    for ax, (name, sub, _lvl, _nr) in zip(axes, LAYERS):
        topics = pd.read_csv(run_dir / sub / "final_model" / "topics_final.csv")
        valid = topics[topics["Topic"].astype(int) >= 0].copy()
        valid = valid.sort_values("Count", ascending=True).tail(top_n)
        total_valid = valid["Count"].sum()
        labels = []
        for r in valid.itertuples():
            rep = getattr(r, "Representation", None) or getattr(r, "Name", "")
            labels.append(
                f"#{int(r.Topic)} ({100 * r.Count / total_valid:.1f}%) {_parse_terms(rep)}"[:55]
            )
        ax.barh(range(len(valid)), valid["Count"], color="#8172b3", alpha=0.9)
        ax.set_yticks(range(len(valid)))
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("comment count")
        ax.set_title(f"{name} — top {top_n} topics (among valid-assigned in topics table)")
    fig.suptitle("6. Largest topics + top terms (sanity check for coders)", fontsize=11, y=1.01)
    fig.tight_layout()
    path = out_dir / "06_top15_topics.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_7_mcs_sensitivity(run_dir: Path, out_dir: Path) -> Path:
    fig, axes = plt.subplots(len(LAYERS), 3, figsize=(12, 9), sharex="col")
    metrics = [
        ("n_topics", "n_topics", "#4c72b0"),
        ("raw_outlier_rate", "outlier rate", "#c44e52"),
        ("largest_share_valid", "largest_share (valid)", "#55a868"),
    ]
    for row, (name, sub, _lvl, _nr) in enumerate(LAYERS):
        summary = pd.read_csv(run_dir / sub / "hdbscan_candidate_summary.csv")
        sel = json.loads((run_dir / sub / "final_model_selection.json").read_text(encoding="utf-8"))
        chosen_mcs = int(sel["base_mcs"])
        for col, (col_name, ylabel, color) in enumerate(metrics):
            ax = axes[row, col]
            ax.plot(summary["mcs"], summary[col_name], "o-", color=color, lw=1.5, markersize=6)
            ax.axvline(chosen_mcs, color="black", ls="--", lw=1, alpha=0.7)
            if row == 0:
                ax.set_title(ylabel)
            if col == 0:
                ax.set_ylabel(name)
            ax.set_xlabel("min_cluster_size")
            ax.grid(True, alpha=0.3)
    fig.suptitle("7. HDBSCAN mcs sensitivity (★ dashed = selected base_mcs)", fontsize=11)
    fig.tight_layout()
    path = out_dir / "07_mcs_sensitivity_panels.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="Topic discovery diagnostic figures 1–7")
    ap.add_argument("--run-id", default=DEFAULT_RUN_ID)
    ap.add_argument("--experiments-root", type=Path, default=ROOT / "output" / "experiments")
    args = ap.parse_args()

    run_dir = args.experiments_root / args.run_id
    out_dir = run_dir / "topic_diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)

    _setup_cjk_font()
    stopwords = load_topic_stopwords()
    print("Loading docs …", flush=True)
    docs = _prepare_docs(run_dir, stopwords)

    paths = [
        plot_1_outlier_by_token(docs, out_dir),
        plot_2_token_ecdf(docs, out_dir),
        plot_3_umap_outlier(run_dir, docs, out_dir),
        plot_4_topic_size(run_dir, out_dir),
        plot_5_level_x_outlier(docs, out_dir),
        plot_6_top_topics(run_dir, out_dir),
        plot_7_mcs_sensitivity(run_dir, out_dir),
    ]
    print("\nSaved:")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
