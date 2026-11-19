from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "output/experiments/2026-11-16_youtube_en_robot_imagination_self_bertopic"
EXPECTED_N = 28096
PRIMARY_MCS = 80
MCS_SWEEP = (30, 50, 80, 100)
UMAP_SEEDS = (42, 43, 44, 45, 46)

PERSPECTIVES = (
    ("Robot", "has_robot"),
    ("Imagination", "has_imagination"),
    ("Self", "has_self"),
)


def validity_dir() -> Path:
    d = EXP / "validity"
    d.mkdir(parents=True, exist_ok=True)
    return d


def assert_corpus() -> Path:
    p = EXP / "analysis_corpus.csv"
    if not p.is_file():
        raise FileNotFoundError(p)
    import pandas as pd

    n = len(pd.read_csv(p, usecols=["comment_id"]))
    if n != EXPECTED_N:
        raise ValueError(f"analysis_corpus row count {n} != {EXPECTED_N}")
    for rel in ("comment_assignments.csv", "embeddings.npy", "umap_reduced.npy"):
        q = EXP / rel
        if not q.is_file():
            raise FileNotFoundError(q)
    return p