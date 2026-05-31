"""Compute cluster-quality metrics for L1 / L2 / Pooled topic discovery layers.

Reads existing experiment artifacts only (no pipeline changes). Outputs
``layer_cluster_metrics.csv`` under the run directory.

Metrics (per visual.md MVP):
- 5D UMAP + base HDBSCAN labels: silhouette, DBCV, outlier_rate, largest_share
- Final reduced model: C_V (from scan table), c_npmi, topic_diversity

Usage (repo root)::

    ./.venv/bin/python -m tools.compute_layer_cluster_metrics \\
        --run-id 2026-05-27_topic_merged_bge_hdbscan_sensitivity
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from phase1.config import ROOT
from phase1.topic_discovery import compute_cv_coherence
from phase1.topic_lda import _setup_tokenizer, tokenize_text
from phase1.topic_modeling import _bertopic_quality_metrics, _topic_diversity_from_terms

DEFAULT_RUN_ID = "2026-05-27_topic_merged_bge_hdbscan_sensitivity"
RANDOM_STATE = 42

LAYERS: tuple[dict[str, str | int | None], ...] = (
    {"layer": "L1", "review_subdir": "topic_discovery_l1", "comment_level": 1},
    {"layer": "L2", "review_subdir": "topic_discovery_l2", "comment_level": 2},
    {"layer": "Pooled", "review_subdir": "topic_discovery_review", "comment_level": None},
)


def _parse_top_terms(row: pd.Series, top_n: int = 10) -> list[str]:
    rep = row.get("Representation", row.get("top_terms", ""))
    if pd.isna(rep):
        return []
    s = str(rep).strip()
    try:
        obj = ast.literal_eval(s)
        if isinstance(obj, (list, tuple)):
            return [str(w).strip() for w in obj if str(w).strip()][:top_n]
    except Exception:
        pass
    return [w.strip() for w in s.split(",") if w.strip()][:top_n]


def _load_stopwords(run_dir: Path) -> set[str]:
    filter_path = run_dir / "comment_content_filter.json"
    if not filter_path.is_file():
        return set()
    with open(filter_path, encoding="utf-8") as f:
        return set(json.load(f).get("stopwords", []))


def _load_shared(run_dir: Path, comment_level: int | None) -> pd.DataFrame:
    shared_path = run_dir / "shared_analyzable_corpus.csv"
    shared = pd.read_csv(shared_path)
    if comment_level is None:
        return shared.reset_index(drop=True)
    sub = shared[shared["comment_level"] == comment_level].reset_index(drop=True)
    if len(sub) == 0:
        raise ValueError(f"no rows for comment_level={comment_level} in {shared_path}")
    return sub


def _fit_or_load_umap_5d(
    run_dir: Path,
    shared: pd.DataFrame,
    comment_level: int | None,
) -> np.ndarray:
    if comment_level is None:
        umap_path = run_dir / "umap_reduced.npy"
        if not umap_path.is_file():
            raise FileNotFoundError(f"missing pooled umap: {umap_path}")
        reduced = np.load(umap_path)
        if reduced.shape[0] != len(shared):
            raise ValueError(f"umap rows {reduced.shape[0]} != corpus {len(shared)}")
        return np.asarray(reduced, dtype=np.float64)

    from umap import UMAP

    emb_path = run_dir / "embeddings.npy"
    if not emb_path.is_file():
        raise FileNotFoundError(f"missing embeddings: {emb_path}")
    embeddings_full = np.load(emb_path)
    shared_full = pd.read_csv(run_dir / "shared_analyzable_corpus.csv")
    if embeddings_full.shape[0] != len(shared_full):
        raise ValueError("embeddings row count != shared corpus row count")
    mask = shared_full["comment_level"].to_numpy() == comment_level
    idx = np.where(mask)[0]
    embeddings = np.asarray(embeddings_full[idx], dtype=np.float64)
    n_doc = len(embeddings)
    n_neighbors = min(15, max(2, n_doc - 1))
    print(f"  UMAP fit n={n_doc} n_neighbors={n_neighbors} …", flush=True)
    umap_runner = UMAP(
        n_neighbors=n_neighbors,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=RANDOM_STATE,
    )
    return np.asarray(umap_runner.fit_transform(embeddings), dtype=np.float64)


def _compute_npmi(topic_word_lists: list[list[str]], tokenized_texts: list[list[str]]) -> float:
    from gensim.corpora import Dictionary
    from gensim.models.coherencemodel import CoherenceModel

    if not topic_word_lists:
        return float("nan")
    dictionary = Dictionary(tokenized_texts)
    filtered: list[list[str]] = []
    for words in topic_word_lists:
        kept = [str(w).strip() for w in words if str(w).strip() in dictionary.token2id]
        if len(kept) >= 2:
            filtered.append(kept)
    if not filtered:
        return float("nan")
    cm = CoherenceModel(
        topics=filtered,
        texts=tokenized_texts,
        dictionary=dictionary,
        coherence="c_npmi",
        processes=1,
    )
    return float(cm.get_coherence())


def _cv_from_curve(review_dir: Path, final_nr: int) -> float:
    curve_path = review_dir / "topic_number_cv_curve.csv"
    if not curve_path.is_file():
        return float("nan")
    curve = pd.read_csv(curve_path)
    row = curve.loc[curve["target_nr_topics"] == final_nr]
    if row.empty:
        return float("nan")
    return float(row.iloc[0]["c_v_coherence"])


def compute_layer_metrics(run_dir: Path, layer_spec: dict[str, str | int | None]) -> dict[str, object]:
    layer = str(layer_spec["layer"])
    review_subdir = str(layer_spec["review_subdir"])
    comment_level = layer_spec["comment_level"]
    comment_level = int(comment_level) if comment_level is not None else None

    review_dir = run_dir / review_subdir
    print(f"[{layer}] {review_dir}", flush=True)

    with open(review_dir / "final_model_selection.json", encoding="utf-8") as f:
        sel = json.load(f)
    base_mcs = int(sel["base_mcs"])
    final_nr = int(sel["selected_target_nr_topics"])

    doc_topics_path = review_dir / f"bert_hdbscan_mcs{base_mcs}" / "doc_topics.csv"
    if not doc_topics_path.is_file():
        # Pooled HDBSCAN candidates live at run root (from topic_modeling), not review subdir.
        doc_topics_path = run_dir / f"bert_hdbscan_mcs{base_mcs}" / "doc_topics.csv"
    if not doc_topics_path.is_file():
        raise FileNotFoundError(doc_topics_path)
    doc_topics = pd.read_csv(doc_topics_path)
    labels = doc_topics["topic_raw"].to_numpy(dtype=int)

    shared = _load_shared(run_dir, comment_level)
    if len(labels) != len(shared):
        raise ValueError(f"{layer}: doc_topics rows {len(labels)} != corpus {len(shared)}")

    reduced = _fit_or_load_umap_5d(run_dir, shared, comment_level)
    qm = _bertopic_quality_metrics(reduced, labels, is_hdbscan=True)

    topics_final_path = review_dir / "final_model" / "topics_final.csv"
    topics_df = pd.read_csv(topics_final_path)
    valid_topics = topics_df[topics_df["Topic"].astype(int) >= 0]
    topic_word_lists = [_parse_top_terms(r, top_n=10) for _, r in valid_topics.iterrows()]
    topic_word_lists = [w for w in topic_word_lists if len(w) >= 2]

    stopwords = _load_stopwords(run_dir)
    _setup_tokenizer("jieba")
    tokenized = [tokenize_text(str(c), tokenizer="jieba", stopwords=stopwords) for c in shared["content"]]

    c_v = _cv_from_curve(review_dir, final_nr)
    c_npmi = _compute_npmi(topic_word_lists, tokenized)
    term_rows = [", ".join(_parse_top_terms(r, top_n=10)) for _, r in valid_topics.iterrows()]
    topic_diversity = _topic_diversity_from_terms(term_rows)

    # Cross-check C_V via gensim (may differ slightly from scan due to OOV filtering).
    c_v_recheck = compute_cv_coherence(topic_word_lists, tokenized)
    notes = ""
    if not np.isnan(c_v) and not np.isnan(c_v_recheck) and abs(c_v - c_v_recheck) > 0.05:
        notes = f"c_v_recheck={c_v_recheck:.4f}"

    n_final = int(valid_topics.shape[0])
    return {
        "layer": layer,
        "n": len(shared),
        "base_mcs": base_mcs,
        "final_nr": final_nr,
        "n_topics": n_final,
        "silhouette_5d": qm.get("silhouette", float("nan")),
        "dbcv_5d": qm.get("dbcv", float("nan")),
        "outlier_rate": qm.get("outlier_rate", float("nan")),
        "largest_share": qm.get("largest_share", float("nan")),
        "c_v": c_v,
        "c_npmi": c_npmi,
        "topic_diversity": topic_diversity,
        "notes": notes,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Layer cluster metrics for topic discovery")
    p.add_argument("--run-id", default=DEFAULT_RUN_ID)
    p.add_argument(
        "--experiments-root",
        type=Path,
        default=ROOT / "output" / "experiments",
    )
    args = p.parse_args()
    run_dir = args.experiments_root / args.run_id
    if not run_dir.is_dir():
        print(f"run dir not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    rows: list[dict[str, object]] = []
    for spec in LAYERS:
        rows.append(compute_layer_metrics(run_dir, spec))

    out_path = run_dir / "layer_cluster_metrics.csv"
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}", flush=True)
    print(df.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
