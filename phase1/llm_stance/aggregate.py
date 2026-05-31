"""Merge per-model JSONL + the original 3 annotation columns into one wide CSV.

Output columns:
    comment_id, post_id, post_category, content,
    human1, human2, llm_orig,
    <model_key>, <model_key>_reason, <model_key>_error   # per model
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import pandas as pd

from .annotate import load_comments
from .openrouter_client import DEFAULT_MODELS


def load_excel_labels(xlsx_path: str) -> pd.DataFrame:
    """Pull the existing 3 stance columns (H1, LLM-original, H2) from the xlsx."""
    raw = pd.read_excel(xlsx_path, sheet_name=0, header=None)
    data = raw.iloc[2:].reset_index(drop=True)
    return pd.DataFrame({
        "comment_id": data.iloc[:, 6].astype(str),
        "human1":     data.iloc[:, 8],
        "llm_orig":   data.iloc[:, 9],
        "human2":     data.iloc[:, 10],
    })


def load_model_jsonl(path: Path, model_key: str) -> pd.DataFrame:
    rows = []
    if not path.exists():
        return pd.DataFrame(columns=["comment_id", model_key, f"{model_key}_reason", f"{model_key}_error"])
    with path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append({
                "comment_id": str(rec.get("comment_id")),
                model_key:               rec.get("stance"),
                f"{model_key}_reason":   rec.get("reason"),
                f"{model_key}_error":    rec.get("error"),
            })
    df = pd.DataFrame(rows).drop_duplicates(subset=["comment_id"], keep="last")
    return df


def run(input_xlsx: str, jsonl_dir: str, out_csv: str, model_keys: list[str]) -> None:
    base = load_comments(input_xlsx)[["comment_id", "post_id", "post_category", "content"]]
    base["comment_id"] = base["comment_id"].astype(str)

    labels = load_excel_labels(input_xlsx)
    merged = base.merge(labels, on="comment_id", how="left")

    jsonl_root = Path(jsonl_dir)
    for key in model_keys:
        m = load_model_jsonl(jsonl_root / f"{key}.jsonl", key)
        merged = merged.merge(m, on="comment_id", how="left")

    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_csv, index=False)
    print(f"[done] wrote {len(merged)} rows × {len(merged.columns)} cols → {out_csv}")

    # quick sanity summary
    for key in model_keys:
        if key not in merged.columns:
            continue
        nn = merged[key].notna().sum()
        err = (merged[key] == "API_ERROR").sum() + (merged[key] == "PARSE_ERROR").sum()
        print(f"  {key:12s}  labelled={nn}  errors={err}")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--jsonl-dir", default="phase1/llm_stance/output")
    p.add_argument("--out", default="phase1/llm_stance/output/stance_wide.csv")
    p.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS.keys()))
    return p.parse_args()


def main():
    args = parse_args()
    run(args.input, args.jsonl_dir, args.out, args.models)


if __name__ == "__main__":
    main()
