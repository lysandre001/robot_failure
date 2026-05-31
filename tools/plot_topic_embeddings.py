"""Static 2D embedding visualization for L1 / L2 / Pooled topic discovery.

Methodology (faithful to the BERTopic clustering decision):
- Loads each layer's pre-computed 5D UMAP (the one HDBSCAN actually used).
- Runs a deterministic 5D→2D UMAP (random_state=42, metric=euclidean) for plotting only.
- Top-K largest valid topics get distinct colors; remaining valid topics use a faint
  shared "other" color; outliers (-1) are excluded from topic panels and drawn faint
  in the comment_level panel.
- 4 panels: L1 by topic | L2 by topic | Pooled by topic | Pooled by comment_level.

Output: PNG under <run>/topic_discovery_embedding_panels.png .

Usage::
    ./.venv/bin/python -m tools.plot_topic_embeddings
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# CJK font for Chinese topic terms / titles; fall back gracefully.
for _cjk in ("Hiragino Sans GB", "PingFang SC", "Heiti TC", "Hannotate SC", "Arial Unicode MS"):
    try:
        from matplotlib.font_manager import findfont, FontProperties
        findfont(FontProperties(family=_cjk), fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [_cjk] + plt.rcParams.get("font.sans-serif", [])
        plt.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        continue

RUN_DIR = Path("output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity")
TOP_K_HIGHLIGHT = 12  # number of largest topics to color distinctly
TOP_TERMS_FOR_LABEL = 3
OUT_PATH = RUN_DIR / "topic_discovery_embedding_panels.png"


def _parse_terms(x, n=TOP_TERMS_FOR_LABEL) -> list[str]:
    if pd.isna(x):
        return []
    s = str(x)
    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, (list, tuple)):
            return [str(t).strip() for t in obj if str(t).strip()][:n]
    except Exception:
        pass
    return [t.strip() for t in s.split(",") if t.strip()][:n]


def _reduce_to_2d(reduced_5d: np.ndarray, *, random_state: int = 42) -> np.ndarray:
    from umap import UMAP

    print(f"  UMAP 5D→2D fit on n={len(reduced_5d)} …", flush=True)
    umap2 = UMAP(
        n_neighbors=15,
        n_components=2,
        min_dist=0.1,
        metric="euclidean",
        random_state=random_state,
    )
    return umap2.fit_transform(reduced_5d)


def _load_layer(name: str, sub: str, nr: int) -> dict:
    layer_dir = RUN_DIR / sub
    reduced_path = (
        layer_dir / "umap_reduced.npy" if sub != "topic_discovery_review" else RUN_DIR / "umap_reduced.npy"
    )
    if not reduced_path.is_file():
        raise FileNotFoundError(f"missing {reduced_path}; run fit / topic_modeling first")

    reduced_5d = np.load(reduced_path)
    doc_topics = pd.read_csv(layer_dir / "final_model" / "doc_topics_final.csv")
    review = pd.read_csv(layer_dir / f"topic_review_sheet_final_nr{nr}.csv")
    if "topic_reduced" not in doc_topics.columns:
        raise KeyError(f"{name}: expected 'topic_reduced' in doc_topics_final.csv")
    if len(reduced_5d) != len(doc_topics):
        raise ValueError(
            f"{name}: umap_reduced rows {len(reduced_5d)} != doc_topics rows {len(doc_topics)}"
        )

    print(f"[{name}] embedding 5D→2D …", flush=True)
    coords_2d = _reduce_to_2d(reduced_5d)

    topics_arr = doc_topics["topic_reduced"].astype(int).to_numpy()
    top_terms_map: dict[int, str] = {}
    for _, r in review.iterrows():
        tid = int(r["topic_id"])
        terms = _parse_terms(r.get("top_terms", ""))
        top_terms_map[tid] = " · ".join(terms) if terms else ""

    return {
        "name": name,
        "coords": coords_2d,
        "topics": topics_arr,
        "top_terms": top_terms_map,
        "doc_topics": doc_topics,
        "n_valid": int((topics_arr >= 0).sum()),
        "n_outlier": int((topics_arr == -1).sum()),
        "n_total": len(topics_arr),
    }


def _topic_color_map(topics: np.ndarray, top_k: int) -> tuple[dict[int, tuple], list[int]]:
    valid = topics[topics >= 0]
    sizes = pd.Series(valid).value_counts()
    top_ids = sizes.head(top_k).index.tolist()
    cmap = plt.get_cmap("tab20", max(top_k, 1))
    color_map = {tid: cmap(i) for i, tid in enumerate(top_ids)}
    return color_map, top_ids


def _scatter_by_topic(ax, layer: dict, top_k: int, *, title: str) -> None:
    coords = layer["coords"]
    topics = layer["topics"]
    color_map, top_ids = _topic_color_map(topics, top_k)
    top_set = set(top_ids)

    valid_mask = topics >= 0
    other_mask = valid_mask & ~np.isin(topics, list(top_set))
    # "other" valid topics
    ax.scatter(
        coords[other_mask, 0], coords[other_mask, 1],
        s=3, c="#bbbbbb", alpha=0.25, linewidths=0, label=None,
    )
    # top-K highlighted
    handles = []
    for tid in top_ids:
        m = topics == tid
        if not m.any():
            continue
        c = color_map[tid]
        ax.scatter(coords[m, 0], coords[m, 1], s=4.5, c=[c], alpha=0.75, linewidths=0)
        terms_str = layer["top_terms"].get(tid, "")
        label = f"#{tid} ({int(m.sum())}) {terms_str}"[:48]
        handles.append((c, label))
        # centroid annotation
        cx, cy = coords[m, 0].mean(), coords[m, 1].mean()
        ax.text(cx, cy, str(tid), fontsize=7, ha="center", va="center",
                color="black", weight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=c, lw=0.8, alpha=0.9))

    pct_valid = 100 * layer["n_valid"] / layer["n_total"]
    n_topics_total = int(pd.Series(topics[topics >= 0]).nunique())
    ax.set_title(
        f"{title}\nN={layer['n_total']:,} · {n_topics_total} topics · valid={pct_valid:.1f}% (outlier excluded)",
        fontsize=10,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("UMAP-1 (2D, viz only)")
    ax.set_ylabel("UMAP-2")
    # legend below the axes
    from matplotlib.lines import Line2D
    proxies = [Line2D([0], [0], marker="o", color="w", markerfacecolor=c, markersize=6, label=lbl)
               for c, lbl in handles]
    proxies.append(Line2D([0], [0], marker="o", color="w", markerfacecolor="#bbbbbb", markersize=6,
                          label=f"other valid topics ({n_topics_total - len(top_ids)})"))
    ax.legend(handles=proxies, fontsize=6.5, loc="upper left", bbox_to_anchor=(1.0, 1.0),
              borderaxespad=0.0, frameon=False, handlelength=1.2)


def _scatter_by_level(ax, pooled: dict, *, title: str) -> None:
    coords = pooled["coords"]
    topics = pooled["topics"]
    shared = pd.read_csv(RUN_DIR / "shared_analyzable_corpus.csv")
    if len(shared) != len(coords):
        raise ValueError(f"pooled shared_corpus {len(shared)} != coords {len(coords)}")
    level = shared["comment_level"].to_numpy()
    outlier_mask = topics == -1

    # outliers: faint gray
    ax.scatter(coords[outlier_mask, 0], coords[outlier_mask, 1],
               s=2.5, c="#dddddd", alpha=0.3, linewidths=0)
    # L1
    m1 = (~outlier_mask) & (level == 1)
    ax.scatter(coords[m1, 0], coords[m1, 1], s=3.5, c="#1f77b4", alpha=0.45, linewidths=0,
               label=f"L1 一级 (N={int(m1.sum()):,})")
    # L2
    m2 = (~outlier_mask) & (level == 2)
    ax.scatter(coords[m2, 0], coords[m2, 1], s=3.5, c="#ff7f0e", alpha=0.45, linewidths=0,
               label=f"L2 二级 (N={int(m2.sum()):,})")

    n_pool = len(coords)
    n_out = int(outlier_mask.sum())
    ax.set_title(
        f"{title}\nPooled N={n_pool:,} · outlier shown as light gray ({n_out:,}, {100*n_out/n_pool:.1f}%)",
        fontsize=10,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("UMAP-1 (2D, viz only)")
    ax.set_ylabel("UMAP-2")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=TOP_K_HIGHLIGHT)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args()

    layers = {
        "L1": _load_layer("L1", "topic_discovery_l1", 90),
        "L2": _load_layer("L2", "topic_discovery_l2", 45),
        "Pooled": _load_layer("Pooled", "topic_discovery_review", 85),
    }

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    _scatter_by_topic(axes[0, 0], layers["L1"], args.top_k,
                      title="L1 一级评论 by machine topic (top-K highlighted)")
    _scatter_by_topic(axes[0, 1], layers["L2"], args.top_k,
                      title="L2 二级回复 by machine topic (top-K highlighted)")
    _scatter_by_topic(axes[1, 0], layers["Pooled"], args.top_k,
                      title="Pooled by machine topic (top-K highlighted)")
    _scatter_by_level(axes[1, 1], layers["Pooled"],
                      title="Pooled — colored by comment_level (motivation for stratification)")

    fig.suptitle(
        "Topic discovery — 2D UMAP projections (visualization only; "
        "clustering happened in 5D UMAP that the model used)",
        fontsize=12,
        y=0.995,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    print(f"saved: {args.out}")


if __name__ == "__main__":
    main()
