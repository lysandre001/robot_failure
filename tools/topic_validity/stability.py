"""Q1 — clustering stability vs primary MCS=80 solution."""
from __future__ import annotations

import ast
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from .md_table import df_to_markdown
from .paths import EXP, MCS_SWEEP, PRIMARY_MCS, UMAP_SEEDS, validity_dir


def _parse_representation(cell: Any) -> list[str]:
    if isinstance(cell, list):
        return [str(x) for x in cell[:10]]
    s = str(cell or "")
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return [str(x) for x in parsed[:10]]
    except (SyntaxError, ValueError):
        pass
    return []


def jaccard_words(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


def rbo(list1: list[str], list2: list[str], *, p: float = 0.9) -> float:
    """Rank-biased overlap (Webber et al.); lists truncated to same length."""
    if not list1 or not list2:
        return 0.0
    depth = min(len(list1), len(list2), 10)
    s1, s2 = list1[:depth], list2[:depth]
    score = 0.0
    weight = 1.0
    for d in range(1, depth + 1):
        overlap = len(set(s1[:d]) & set(s2[:d])) / d
        score += weight * overlap
        weight *= (1 - p)
    return score / (1 - p ** depth) if depth else 0.0


def _load_primary_labels() -> np.ndarray:
    p = EXP / f"bert_hdbscan_mcs{PRIMARY_MCS}" / "doc_topics.csv"
    return pd.read_csv(p)["topic"].to_numpy(dtype=int)


def _topic_top_words(mcs: int) -> dict[int, list[str]]:
    topics = pd.read_csv(EXP / f"bert_hdbscan_mcs{mcs}" / "topics.csv")
    out: dict[int, list[str]] = {}
    for _, row in topics.iterrows():
        tid = int(row["Topic"])
        if tid == -1:
            continue
        out[tid] = _parse_representation(row.get("Representation", row.get("representation")))
    return out


def _aligned_word_stability(
    labels_ref: np.ndarray,
    labels_alt: np.ndarray,
    words_ref: dict[int, list[str]],
    words_alt: dict[int, list[str]],
) -> dict[str, float]:
    """Match non-outlier topics by maximum co-assignment overlap; then top-10 word metrics."""
    jaccs: list[float] = []
    rbos: list[float] = []
    ref_topics = sorted({int(t) for t in labels_ref if t != -1})
    for rt in ref_topics:
        mask_r = labels_ref == rt
        best_t, best_overlap = None, 0
        for at in {int(t) for t in labels_alt if t != -1}:
            overlap = int(np.sum(mask_r & (labels_alt == at)))
            if overlap > best_overlap:
                best_overlap = overlap
                best_t = at
        if best_t is None or best_overlap < 5:
            continue
        w1 = words_ref.get(rt, [])
        w2 = words_alt.get(best_t, [])
        jaccs.append(jaccard_words(w1, w2))
        rbos.append(rbo(w1, w2))
    return {
        "mean_top10_jaccard": float(np.mean(jaccs)) if jaccs else float("nan"),
        "mean_top10_rbo": float(np.mean(rbos)) if rbos else float("nan"),
        "n_matched_topics": float(len(jaccs)),
    }


def _compare_run(
    labels_ref: np.ndarray,
    labels_alt: np.ndarray,
    *,
    run_id: str,
    mcs: int,
    seed: int | None,
    source: str,
    words_ref: dict[int, list[str]],
    words_alt: dict[int, list[str]] | None = None,
) -> dict[str, Any]:
    n_topics_alt = len({int(t) for t in labels_alt if t != -1})
    outlier_alt = float(np.mean(labels_alt == -1))
    row: dict[str, Any] = {
        "run_id": run_id,
        "mcs": mcs,
        "umap_seed": seed,
        "source": source,
        "n_topics": n_topics_alt,
        "outlier_rate": round(outlier_alt, 6),
        "ari": round(float(adjusted_rand_score(labels_ref, labels_alt)), 6),
        "nmi": round(
            float(
                normalized_mutual_info_score(
                    labels_ref, labels_alt, average_method="arithmetic"
                )
            ),
            6,
        ),
    }
    if words_alt is not None:
        row.update(_aligned_word_stability(labels_ref, labels_alt, words_ref, words_alt))
    return row


def _fit_umap_seed(embeddings: np.ndarray, seed: int) -> np.ndarray:
    from umap import UMAP

    n_doc = len(embeddings)
    n_neighbors = min(15, max(2, n_doc - 1))
    return UMAP(
        n_neighbors=n_neighbors,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=seed,
    ).fit_transform(embeddings)


def _cluster_reduced(reduced: np.ndarray, mcs: int) -> np.ndarray:
    from hdbscan import HDBSCAN

    return HDBSCAN(
        min_cluster_size=mcs,
        min_samples=mcs,
        metric="euclidean",
        cluster_selection_method="eom",
    ).fit_predict(reduced)


def run_stability(*, run_umap_seeds: bool = True) -> None:
    out = validity_dir()
    labels_ref = _load_primary_labels()
    words_ref = _topic_top_words(PRIMARY_MCS)
    rows: list[dict[str, Any]] = []

    for mcs in MCS_SWEEP:
        sub = EXP / f"bert_hdbscan_mcs{mcs}" / "doc_topics.csv"
        if not sub.is_file():
            continue
        labels_alt = pd.read_csv(sub)["topic"].to_numpy(dtype=int)
        words_alt = _topic_top_words(mcs)
        rows.append(
            _compare_run(
                labels_ref,
                labels_alt,
                run_id=f"mcs{mcs}",
                mcs=mcs,
                seed=42 if mcs == PRIMARY_MCS else None,
                source="existing_bertopic",
                words_ref=words_ref,
                words_alt=words_alt,
            )
        )

    cache_dir = out / "umap_seed_runs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    embeddings = np.load(EXP / "embeddings.npy")

    if run_umap_seeds:
        for seed in UMAP_SEEDS:
            if seed == 42:
                labels_alt = labels_ref
                source = "primary_ref"
            else:
                cache = cache_dir / f"labels_mcs{PRIMARY_MCS}_umap{seed}.npy"
                if cache.is_file():
                    labels_alt = np.load(cache)
                    source = "cached"
                else:
                    reduced = _fit_umap_seed(embeddings, seed)
                    labels_alt = _cluster_reduced(reduced, PRIMARY_MCS)
                    np.save(cache, labels_alt)
                    source = "fitted"
            rows.append(
                _compare_run(
                    labels_ref,
                    labels_alt,
                    run_id=f"umap_seed{seed}",
                    mcs=PRIMARY_MCS,
                    seed=seed,
                    source=source,
                    words_ref=words_ref,
                    words_alt=None,
                )
            )

    runs = pd.DataFrame(rows)
    runs.to_csv(out / "stability_runs.csv", index=False)

    lines = [
        "# Q1 — clustering stability (reference: `bert_hdbscan_mcs80`)",
        "",
        f"- Documents: N={len(labels_ref)}",
        f"- Primary outlier rate: {np.mean(labels_ref == -1):.4f}",
        "",
        "## MCS sweep (frozen UMAP from main pipeline, seed=42)",
        "",
        df_to_markdown(runs[runs["source"] == "existing_bertopic"]),
        "",
        "## UMAP random seeds (re-fit UMAP + HDBSCAN mcs=80)",
        "",
        "HDBSCAN on a fixed reduction is deterministic; seed variation refits UMAP only.",
        "",
        df_to_markdown(runs[runs["run_id"].str.startswith("umap_seed")]),
    ]
    (out / "stability_summary.md").write_text("\n".join(lines), encoding="utf-8")

    _write_manual_spotcheck(labels_ref, runs, out)


def _write_manual_spotcheck(
    labels_ref: np.ndarray, runs: pd.DataFrame, out: Path
) -> None:
    assign = pd.read_csv(
        EXP / "comment_assignments.csv",
        dtype={"comment_id": str, "帖子id": str},
        low_memory=False,
    )
    assign["topic"] = labels_ref
    rng = random.Random(42)
    rows: list[dict[str, Any]] = []

    alt = EXP / "bert_hdbscan_mcs50" / "doc_topics.csv"
    if alt.is_file():
        lab50 = pd.read_csv(alt)["topic"].to_numpy(dtype=int)
        disagree = np.where(labels_ref != lab50)[0]
        pick = (
            rng.sample(disagree.tolist(), k=min(40, len(disagree)))
            if len(disagree)
            else []
        )
        for i in pick:
            r = assign.iloc[i]
            rows.append(
                {
                    "reason": "mcs50_vs_mcs80_disagree",
                    "comment_id": r["comment_id"],
                    "topic_mcs80": int(labels_ref[i]),
                    "topic_mcs50": int(lab50[i]),
                    "has_robot": r["has_robot"],
                    "has_imagination": r["has_imagination"],
                    "has_self": r["has_self"],
                    "content_excerpt": str(r["content"])[:240],
                    "decision": "",
                    "notes": "",
                }
            )

    for tid in sorted({int(t) for t in labels_ref if t != -1})[:12]:
        idx = np.where(labels_ref == tid)[0]
        if len(idx) < 3:
            continue
        for j in rng.sample(idx.tolist(), k=min(3, len(idx))):
            r = assign.iloc[j]
            rows.append(
                {
                    "reason": f"topic_{tid}_random",
                    "comment_id": r["comment_id"],
                    "topic_mcs80": tid,
                    "topic_mcs50": "",
                    "has_robot": r["has_robot"],
                    "has_imagination": r["has_imagination"],
                    "has_self": r["has_self"],
                    "content_excerpt": str(r["content"])[:240],
                    "decision": "",
                    "notes": "",
                }
            )

    pd.DataFrame(rows).to_csv(out / "manual_spotcheck_sample.csv", index=False)