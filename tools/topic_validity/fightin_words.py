"""Q2b — within-topic Fightin' Words (Monroe et al. informative Dirichlet log-odds)."""
from __future__ import annotations

import math
import re
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

from .paths import EXP, PERSPECTIVES, validity_dir

MIN_DOCS = 30
PAIR_NAMES = [
    ("Robot", "Imagination"),
    ("Robot", "Self"),
    ("Imagination", "Self"),
]
COL_MAP = {"Robot": "has_robot", "Imagination": "has_imagination", "Self": "has_self"}


def _tokenize_texts(texts: Iterable[str]) -> list[str]:
    return [str(t).strip() for t in texts if str(t).strip()]


def fightin_word_stats(
    counts_a: dict[str, int],
    counts_b: dict[str, int],
    n_a: int,
    n_b: int,
    *,
    prior: float = 0.01,
) -> list[dict]:
    """Informative Dirichlet log-odds with z-score (Monroe et al. 2008, simplified)."""
    vocab = set(counts_a) | set(counts_b)
    V = max(len(vocab), 1)
    rows: list[dict] = []
    for w in vocab:
        ca = counts_a.get(w, 0)
        cb = counts_b.get(w, 0)
        ya = (ca + prior) / (n_a + prior * V)
        yb = (cb + prior) / (n_b + prior * V)
        delta = math.log(ya) - math.log(yb)
        var = 1.0 / (ca + prior) + 1.0 / (cb + prior)
        z = delta / math.sqrt(var) if var > 0 else 0.0
        rows.append(
            {
                "term": w,
                "count_a": ca,
                "count_b": cb,
                "log_odds": delta,
                "z": z,
                "favors": "a" if delta > 0 else "b",
            }
        )
    return rows


def run_fightin_words() -> None:
    out = validity_dir()
    df = pd.read_csv(
        EXP / "comment_assignments.csv",
        dtype={"comment_id": str, "帖子id": str},
        low_memory=False,
    )
    df = df[df["topic"].notna() & (df["topic"] != -1)].copy()
    df["topic"] = df["topic"].astype(int)

    fw_rows: list[dict] = []
    ex_rows: list[dict] = []

    for topic_id, g in df.groupby("topic"):
        for name_a, name_b in PAIR_NAMES:
            ca, cb = COL_MAP[name_a], COL_MAP[name_b]
            ga = g[g[ca].astype(bool)]
            gb = g[g[cb].astype(bool)]
            if len(ga) < MIN_DOCS or len(gb) < MIN_DOCS:
                continue
            texts_a = _tokenize_texts(ga["content"])
            texts_b = _tokenize_texts(gb["content"])
            vec = CountVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                min_df=2,
                max_df=0.95,
                max_features=5000,
            )
            try:
                X = vec.fit_transform(texts_a + texts_b)
            except ValueError:
                continue
            feats = vec.get_feature_names_out()
            na = len(texts_a)
            nb = len(texts_b)
            ca_counts = np.asarray(X[:na].sum(axis=0)).ravel()
            cb_counts = np.asarray(X[na:].sum(axis=0)).ravel()
            dict_a = {feats[i]: int(ca_counts[i]) for i in range(len(feats)) if ca_counts[i]}
            dict_b = {feats[i]: int(cb_counts[i]) for i in range(len(feats)) if cb_counts[i]}
            stats = fightin_word_stats(dict_a, dict_b, na, nb)
            stats.sort(key=lambda r: abs(r["z"]), reverse=True)
            for rank, st in enumerate(stats[:25], start=1):
                fav = name_a if st["favors"] == "a" else name_b
                fw_rows.append(
                    {
                        "topic_id": int(topic_id),
                        "pair": f"{name_a}-{name_b}",
                        "rank": rank,
                        "term": st["term"],
                        "z": round(st["z"], 4),
                        "log_odds": round(st["log_odds"], 4),
                        "count_a": st["count_a"],
                        "count_b": st["count_b"],
                        "favors": fav,
                        "n_a": na,
                        "n_b": nb,
                    }
                )
            for st in stats[:5]:
                fav = name_a if st["favors"] == "a" else name_b
                pool = ga if fav == name_a else gb
                term = st["term"]
                needle = term.lower()
                picks = []
                for _, r in pool.iterrows():
                    hay = str(r["content"]).lower()
                    if needle in hay or all(p in hay for p in needle.split()):
                        picks.append(r)
                    if len(picks) >= 3:
                        break
                if not picks:
                    picks = pool.head(2).to_dict("records")
                for r in picks[:3]:
                    rec = r if isinstance(r, dict) else r.to_dict()
                    ex_rows.append(
                        {
                            "topic_id": int(topic_id),
                            "pair": f"{name_a}-{name_b}",
                            "term": term,
                            "favors": fav,
                            "comment_id": rec.get("comment_id"),
                            "content_excerpt": str(rec.get("content", ""))[:300],
                        }
                    )

    pd.DataFrame(fw_rows).to_csv(out / "fightin_words_by_topic.csv", index=False)
    pd.DataFrame(ex_rows).to_csv(out / "fightin_words_examples.csv", index=False)