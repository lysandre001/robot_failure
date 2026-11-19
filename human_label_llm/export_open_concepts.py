#!/usr/bin/env python3
"""Export open-coding infer log.jsonl → comment_concepts.csv + concepts_long.csv.

Layout (under output/concept_extract/<run_id>/):

  log.jsonl                 # infer source of truth
  comment_concepts.csv      # wide: comment_id, batch, n_concepts, concepts_json, status, ...
  concepts_long.csv         # long: comment_id, concept_raw, rank  (input to merge)
  merge/
    round1/batch_000.json   # ≤50 unique concept_raw per batch (for LLM merge step)
    round1/merged.csv       # canonical, sources (JSON list), n_source_strings

Usage (from repo root):

  .venv/bin/python human_label_llm/export_open_concepts.py \\
    output/concept_extract/20261119_youtube_l1_open_concepts_v3/log.jsonl

Optional --input-csv to attach batch + content_en from the same L1 table used at infer time.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def export_from_log(
    log_path: Path,
    *,
    input_csv: Path | None = None,
    text_column: str = "content_en",
    out_dir: Path | None = None,
) -> tuple[Path, Path]:
    out_dir = out_dir or log_path.parent
    records: list[dict] = []
    with log_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not records:
        raise ValueError(f"No records in {log_path}")

    df = pd.DataFrame(records)
    if input_csv and input_csv.is_file():
        meta_cols = ["comment_id", "batch"]
        meta = pd.read_csv(input_csv)
        if text_column in meta.columns:
            meta_cols.append(text_column)
        meta = meta[meta_cols].drop_duplicates(subset=["comment_id"], keep="first")
        df = df.merge(meta, on="comment_id", how="left")
    elif "batch" not in df.columns:
        df["batch"] = ""
    if text_column not in df.columns:
        df[text_column] = ""

    def concepts_from_row(row: pd.Series) -> list[str]:
        en = str(row.get("label_en", "") or "").strip()
        if en and row.get("status") == "ok":
            return [p.strip() for p in en.split("|") if p.strip()]
        raw = str(row.get("raw", "") or "")
        for cand in (raw.strip(),):
            try:
                obj = json.loads(cand)
                if isinstance(obj, dict) and isinstance(obj.get("concepts"), list):
                    return [str(x).strip() for x in obj["concepts"] if str(x).strip()]
            except json.JSONDecodeError:
                pass
        return []

    concepts_lists = df.apply(concepts_from_row, axis=1)
    wide_cols = [
        "comment_id",
        "batch",
        text_column,
        "status",
        "model_key",
        "scope_id",
        "prompt_id",
    ]
    wide = df[wide_cols].copy()
    wide["n_concepts"] = concepts_lists.map(len)
    wide["concepts_json"] = concepts_lists.map(lambda xs: json.dumps(xs, ensure_ascii=False))

    long_rows: list[dict] = []
    for _, row in df.iterrows():
        cid = row["comment_id"]
        for rank, concept in enumerate(concepts_from_row(row), start=1):
            long_rows.append(
                {"comment_id": cid, "concept_raw": concept, "rank": rank}
            )
    long_df = pd.DataFrame(long_rows)

    wide_path = out_dir / "comment_concepts.csv"
    long_path = out_dir / "concepts_long.csv"
    wide.to_csv(wide_path, index=False)
    long_df.to_csv(long_path, index=False)
    return wide_path, long_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log_jsonl", type=Path, help="Path to infer log.jsonl")
    p.add_argument(
        "--input-csv",
        type=Path,
        default=None,
        help="Optional L1 CSV with comment_id, batch, content_en",
    )
    p.add_argument(
        "--text-column",
        default="content_en",
        help="Comment text column from --input-csv (default: content_en)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: parent of log.jsonl)",
    )
    args = p.parse_args(argv)
    wide, long = export_from_log(
        args.log_jsonl.resolve(),
        input_csv=args.input_csv.resolve() if args.input_csv else None,
        text_column=args.text_column,
        out_dir=args.out_dir.resolve() if args.out_dir else None,
    )
    print(f"Wrote {wide}")
    print(f"Wrote {long}")
    return 0


if __name__ == "__main__":
    sys.exit(main())