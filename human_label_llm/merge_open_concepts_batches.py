#!/usr/bin/env python3
"""Split unique concepts from concepts_long.csv into merge batches (default 50).

Writes under <run_dir>/merge/round<r>/batch_*.json — each file is a JSON list of
strings for a separate LLM merge call (not executed here).

Example:

  .venv/bin/python human_label_llm/merge_open_concepts_batches.py \\
    output/concept_extract/<run_id>/concepts_long.csv \\
    --round 1
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd


def write_batches(
    concepts_long: Path,
    *,
    batch_size: int = 50,
    round_id: int = 1,
    out_dir: Path | None = None,
) -> Path:
    df = pd.read_csv(concepts_long)
    if "concept_raw" not in df.columns:
        raise ValueError(f"Missing concept_raw in {concepts_long}")
    unique = sorted({str(x).strip() for x in df["concept_raw"].dropna() if str(x).strip()})
    run_dir = concepts_long.parent
    merge_dir = (out_dir or run_dir / "merge" / f"round{round_id}")
    merge_dir.mkdir(parents=True, exist_ok=True)
    n_batches = math.ceil(len(unique) / batch_size) if unique else 0
    for i in range(n_batches):
        chunk = unique[i * batch_size : (i + 1) * batch_size]
        path = merge_dir / f"batch_{i:03d}.json"
        path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[merge] unique={len(unique)}  batches={n_batches}  dir={merge_dir}")
    return merge_dir


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("concepts_long_csv", type=Path)
    p.add_argument("--batch-size", type=int, default=50)
    p.add_argument("--round", type=int, default=1)
    p.add_argument("--out-dir", type=Path, default=None)
    args = p.parse_args(argv)
    write_batches(
        args.concepts_long_csv.resolve(),
        batch_size=args.batch_size,
        round_id=args.round,
        out_dir=args.out_dir.resolve() if args.out_dir else None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())