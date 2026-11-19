"""Q2a — perspective topic distributions, JS/TV overlap, outlier coverage."""
from __future__ import annotations

import itertools
from typing import Iterable

import numpy as np
import pandas as pd

from .paths import EXP, PERSPECTIVES, PRIMARY_MCS, validity_dir


def _topic_distribution(
    topics: np.ndarray, mask: np.ndarray, *, include_outlier: bool
) -> np.ndarray:
    sub = topics[mask]
    if len(sub) == 0:
        return np.array([])
    if include_outlier:
        cats = sorted({int(t) for t in sub})
    else:
        sub = sub[sub != -1]
        if len(sub) == 0:
            return np.array([])
        cats = sorted({int(t) for t in sub})
    counts = np.array([int(np.sum(sub == c)) for c in cats], dtype=float)
    return counts / counts.sum()


def _align_distributions(p: np.ndarray, q: np.ndarray, p_cats, q_cats) -> tuple[np.ndarray, np.ndarray]:
    all_c = sorted(set(p_cats) | set(q_cats))
    pi = {c: i for i, c in enumerate(p_cats)}
    qi = {c: i for i, c in enumerate(q_cats)}
    pp = np.array([p[pi[c]] if c in pi else 0.0 for c in all_c])
    qq = np.array([q[qi[c]] if c in qi else 0.0 for c in all_c])
    return pp, qq


def js_divergence(p: np.ndarray, q: np.ndarray, *, base: float = 2.0) -> float:
    p = np.clip(p, 1e-12, 1.0)
    q = np.clip(q, 1e-12, 1.0)
    m = 0.5 * (p + q)
    kl_pm = np.sum(p * np.log(p / m)) / np.log(base)
    kl_qm = np.sum(q * np.log(q / m)) / np.log(base)
    return float(0.5 * (kl_pm + kl_qm))


def total_variation(p: np.ndarray, q: np.ndarray) -> float:
    return float(0.5 * np.sum(np.abs(p - q)))


def _cats_from_mask(topics: np.ndarray, mask: np.ndarray, *, excl_outlier: bool) -> list[int]:
    sub = topics[mask]
    if excl_outlier:
        sub = sub[sub != -1]
    return sorted({int(t) for t in sub})


def pairwise_metrics(
    topics: np.ndarray,
    masks: dict[str, np.ndarray],
    *,
    label_suffix: str,
) -> list[dict]:
    rows: list[dict] = []
    names = list(masks.keys())
    for a, b in itertools.combinations(names, 2):
        ma, mb = masks[a], masks[b]
        p_cats = _cats_from_mask(topics, ma, excl_outlier=True)
        q_cats = _cats_from_mask(topics, mb, excl_outlier=True)
        p = _topic_distribution(topics, ma, include_outlier=False)
        q = _topic_distribution(topics, mb, include_outlier=False)
        if len(p) == 0 or len(q) == 0:
            continue
        pa, qa = _align_distributions(p, q, p_cats, q_cats)
        tv = total_variation(pa, qa)
        rows.append(
            {
                "perspective_a": a,
                "perspective_b": b,
                "slice": label_suffix,
                "n_a": int(ma.sum()),
                "n_b": int(mb.sum()),
                "js_base2": round(js_divergence(pa, qa), 6),
                "tv": round(tv, 6),
                "one_minus_tv": round(1.0 - tv, 6),
            }
        )
    return rows


def run_overlap() -> None:
    out = validity_dir()
    df = pd.read_csv(
        EXP / "comment_assignments.csv",
        dtype={"comment_id": str, "帖子id": str},
        low_memory=False,
    )
    topics = df["topic"].fillna(-1).astype(int).to_numpy()

    base_masks: dict[str, np.ndarray] = {
        name: df[col].astype(bool).to_numpy() for name, col in PERSPECTIVES
    }

    inclusive_rows = pairwise_metrics(topics, base_masks, label_suffix="inclusive")

    exclusive_masks: dict[str, np.ndarray] = {}
    for name, col in PERSPECTIVES:
        m = df[col].astype(bool)
        other = pd.Series(False, index=df.index)
        for name2, col2 in PERSPECTIVES:
            if name2 != name:
                other |= df[col2].astype(bool)
        exclusive_masks[f"{name}_exclusive"] = (m & ~other).to_numpy()
    exclusive_rows = pairwise_metrics(topics, exclusive_masks, label_suffix="exclusive")

    pair_exclusive_margin: list[dict] = []
    for a, b in itertools.combinations([n for n, _ in PERSPECTIVES], 2):
        ca, cb = f"has_{a.lower()}" if a != "Imagination" else "has_imagination", None
        ca = {"Robot": "has_robot", "Imagination": "has_imagination", "Self": "has_self"}[a]
        cb = {"Robot": "has_robot", "Imagination": "has_imagination", "Self": "has_self"}[b]
        both = df[ca].astype(bool) & df[cb].astype(bool)
        only_a = df[ca].astype(bool) & ~df[cb].astype(bool)
        only_b = df[cb].astype(bool) & ~df[ca].astype(bool)
        p_cats = _cats_from_mask(topics, only_a.to_numpy(), excl_outlier=True)
        q_cats = _cats_from_mask(topics, only_b.to_numpy(), excl_outlier=True)
        p = _topic_distribution(topics, only_a.to_numpy(), include_outlier=False)
        q = _topic_distribution(topics, only_b.to_numpy(), include_outlier=False)
        if len(p) and len(q):
            pa, qa = _align_distributions(p, q, p_cats, q_cats)
            tv = total_variation(pa, qa)
            pair_exclusive_margin.append(
                {
                    "perspective_a": f"{a}_only",
                    "perspective_b": f"{b}_only",
                    "n_a": int(only_a.sum()),
                    "n_b": int(only_b.sum()),
                    "n_both_dropped": int(both.sum()),
                    "js_base2": round(js_divergence(pa, qa), 6),
                    "tv": round(tv, 6),
                    "one_minus_tv": round(1.0 - tv, 6),
                }
            )

    js_tv = pd.DataFrame(inclusive_rows + exclusive_rows)
    js_tv.to_csv(out / "overlap_js_tv.csv", index=False)
    pd.DataFrame(pair_exclusive_margin).to_csv(out / "overlap_exclusive_margins.csv", index=False)

    outlier_rows = []
    for name, col in PERSPECTIVES:
        m = df[col].astype(bool).to_numpy()
        sub = topics[m]
        outlier_rows.append(
            {
                "perspective": name,
                "n": int(m.sum()),
                "outlier_n": int(np.sum(sub == -1)),
                "outlier_rate": round(float(np.mean(sub == -1)), 6),
            }
        )
    pd.DataFrame(outlier_rows).to_csv(out / "outlier_coverage.csv", index=False)

    sens_rows: list[dict] = []
    for mcs in (50, 100):
        p = EXP / f"bert_hdbscan_mcs{mcs}" / "doc_topics.csv"
        if not p.is_file():
            continue
        alt = pd.read_csv(p)
        if "comment_id" not in alt.columns:
            continue
        merged = df[["comment_id"]].merge(alt[["comment_id", "topic"]], on="comment_id", how="left")
        t_alt = merged["topic"].fillna(-1).astype(int).to_numpy()
        for suffix, masks in [("inclusive", base_masks)]:
            sens_rows.extend(
                {
                    **r,
                    "mcs": mcs,
                }
                for r in pairwise_metrics(t_alt, masks, label_suffix=f"{suffix}_mcs{mcs}")
            )
    pd.DataFrame(sens_rows).to_csv(out / "overlap_sensitivity.csv", index=False)