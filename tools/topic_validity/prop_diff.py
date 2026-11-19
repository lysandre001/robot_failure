"""Q2a — topic proportion differences, cluster bootstrap, FDR, narrative shortlist."""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .md_table import df_to_markdown
from .paths import EXP, PERSPECTIVES, validity_dir


def _bh_fdr(pvals: np.ndarray) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order]
    q = np.empty(n)
    prev = 1.0
    for i in range(n - 1, -1, -1):
        rank = i + 1
        val = ranked[i] * n / rank
        prev = min(prev, val)
        q[i] = prev
    out = np.empty(n)
    out[order] = np.clip(q, 0, 1)
    return out


def _video_bootstrap_props(
    df: pd.DataFrame,
    topics: np.ndarray,
    mask: np.ndarray,
    rng: np.random.Generator,
    *,
    B: int = 999,
) -> np.ndarray:
    """Return B x n_topics matrix of proportions (non-outlier topics only)."""
    sub = df.loc[mask, ["帖子id"]].copy()
    sub["topic"] = topics[mask]
    sub = sub[sub["topic"] != -1]
    if sub.empty:
        return np.zeros((B, 0))
    videos = sub["帖子id"].unique()
    topic_ids = sorted(sub["topic"].unique())
    t2i = {t: i for i, t in enumerate(topic_ids)}
    props = np.zeros((B, len(topic_ids)))
    for b in range(B):
        sampled_vids = rng.choice(videos, size=len(videos), replace=True)
        counts = {i: 0 for i in range(len(topic_ids))}
        total = 0
        for vid in sampled_vids:
            chunk = sub[sub["帖子id"] == vid]
            for t in chunk["topic"]:
                counts[t2i[int(t)]] += 1
                total += 1
        if total:
            props[b, :] = [counts[i] / total for i in range(len(topic_ids))]
    return props, topic_ids


def run_prop_diff(*, bootstrap_B: int = 999) -> None:
    out = validity_dir()
    df = pd.read_csv(
        EXP / "comment_assignments.csv",
        dtype={"comment_id": str, "帖子id": str},
        low_memory=False,
    )
    topics = df["topic"].fillna(-1).astype(int).to_numpy()
    valid = topics != -1
    rng = np.random.default_rng(42)

    persp_names = [n for n, _ in PERSPECTIVES]
    masks = {n: df[c].astype(bool).to_numpy() for n, c in PERSPECTIVES}

    rows_share: list[dict] = []
    topic_ids = sorted({int(t) for t in topics if t != -1})
    for tid in topic_ids:
        row = {"topic_id": tid, "n_total_non_outlier": int(np.sum(topics == tid))}
        for name in persp_names:
            m = masks[name]
            n_in = int(np.sum(m & (topics == tid)))
            n_persp_valid = int(np.sum(m & valid))
            row[f"n_{name}"] = n_in
            row[f"share_{name}"] = n_in / n_persp_valid if n_persp_valid else float("nan")
        rows_share.append(row)
    share_df = pd.DataFrame(rows_share)
    share_df.to_csv(out / "topic_prop_shares_by_perspective.csv", index=False)

    diff_rows: list[dict] = []
    pvals: list[float] = []
    pval_meta: list[tuple[int, str, str]] = []

    for tid in topic_ids:
        for a, b in itertools.combinations(persp_names, 2):
            ma, mb = masks[a], masks[b]
            na = int(np.sum(ma & (topics == tid)))
            nb = int(np.sum(mb & (topics == tid)))
            ta = int(np.sum(ma & valid))
            tb = int(np.sum(mb & valid))
            pa = na / ta if ta else float("nan")
            pb = nb / tb if tb else float("nan")
            p_pool = (na + nb) / (ta + tb) if (ta + tb) else float("nan")
            diff_pp = (pa - pb) * 100 if pa == pa and pb == pb else float("nan")
            if ta > 0 and tb > 0:
                table = [[na, ta - na], [nb, tb - nb]]
                _, p_two = stats.fisher_exact(table, alternative="two-sided")
            else:
                p_two = float("nan")
            diff_rows.append(
                {
                    "topic_id": tid,
                    "perspective_a": a,
                    "perspective_b": b,
                    "n_a_in_topic": na,
                    "n_b_in_topic": nb,
                    "prop_a": pa,
                    "prop_b": pb,
                    "diff_pp_a_minus_b": diff_pp,
                    "lift_a_over_b": (pa / pb) if pb and pb > 0 else float("nan"),
                    "fisher_p": p_two,
                }
            )
            if p_two == p_two:
                pvals.append(p_two)
                pval_meta.append((tid, a, b))

    diff_df = pd.DataFrame(diff_rows)
    if pvals:
        q = _bh_fdr(np.array(pvals))
        fdr_map = {(tid, a, b): qv for (tid, a, b), qv in zip(pval_meta, q)}
        diff_df["bh_fdr"] = diff_df.apply(
            lambda r: fdr_map.get((r["topic_id"], r["perspective_a"], r["perspective_b"]), float("nan")),
            axis=1,
        )
    diff_df.to_csv(out / "topic_prop_pairwise_diffs.csv", index=False)

    boot_rows: list[dict] = []
    for a, b in itertools.combinations(persp_names, 2):
        props_a, topics_a = _video_bootstrap_props(df, topics, masks[a], rng, B=bootstrap_B)
        props_b, topics_b = _video_bootstrap_props(df, topics, masks[b], rng, B=bootstrap_B)
        common = sorted(set(topics_a) & set(topics_b))
        if not common:
            continue
        ia = [topics_a.index(t) for t in common]
        ib = [topics_b.index(t) for t in common]
        deltas = props_a[:, ia] - props_b[:, ib]
        for j, tid in enumerate(common):
            col = deltas[:, j]
            lo, hi = np.percentile(col, [2.5, 97.5])
            boot_rows.append(
                {
                    "topic_id": tid,
                    "perspective_a": a,
                    "perspective_b": b,
                    "diff_pp_mean_bootstrap": float(np.mean(col) * 100),
                    "ci95_low_pp": float(lo * 100),
                    "ci95_high_pp": float(hi * 100),
                    "B": bootstrap_B,
                }
            )
    boot_df = pd.DataFrame(boot_rows)
    boot_df.to_csv(out / "topic_prop_bootstrap_ci.csv", index=False)

    # By event strata
    event_rows: list[dict] = []
    for event, g in df.groupby("source_batch"):
        idx = g.index.to_numpy()
        t_sub = topics[idx]
        v_sub = valid[idx]
        for tid in topic_ids:
            for name in persp_names:
                m = masks[name][idx]
                n_p = int(np.sum(m & v_sub))
                n_t = int(np.sum(m & v_sub & (t_sub == tid)))
                event_rows.append(
                    {
                        "source_batch": event,
                        "topic_id": tid,
                        "perspective": name,
                        "n_perspective_valid": n_p,
                        "n_in_topic": n_t,
                        "share": n_t / n_p if n_p else float("nan"),
                    }
                )
    pd.DataFrame(event_rows).to_csv(out / "topic_prop_by_event.csv", index=False)

    merged = diff_df.merge(
        boot_df,
        on=["topic_id", "perspective_a", "perspective_b"],
        how="left",
    )
    _write_narratives(merged, share_df, out)


def _write_narratives(merged: pd.DataFrame, share_df: pd.DataFrame, out: Path) -> None:
    lines = [
        "# Narratives worth follow-up (auto shortlist)",
        "",
        "Criteria: BH-FDR < 0.05 with |diff_pp| ≥ 3, or lift ≥ 1.35, or high mass on overlap-heavy topics.",
        "",
    ]
    cand = merged[
        (
            (merged["bh_fdr"] < 0.05)
            & (merged["diff_pp_a_minus_b"].abs() >= 3)
        )
        | (merged["lift_a_over_b"].fillna(0) >= 1.35)
        | (merged["lift_a_over_b"].fillna(0) <= 1 / 1.35)
    ].copy()
    cand = cand.sort_values(["bh_fdr", "diff_pp_a_minus_b"], ascending=[True, False])

    if cand.empty:
        lines.append("_No rows met thresholds; review `topic_prop_pairwise_diffs.csv` manually._")
    else:
        lines.append("## Pairwise topic proportion contrasts")
        lines.append("")
        lines.append(df_to_markdown(cand.head(40)))

    high_mass = share_df.nlargest(15, "n_total_non_outlier")[
        ["topic_id", "n_total_non_outlier", "share_Robot", "share_Imagination", "share_Self"]
    ]
    lines.extend(["", "## Largest shared topics (by volume)", "", df_to_markdown(high_mass)])
    (out / "narratives_worth_followup.md").write_text("\n".join(lines), encoding="utf-8")