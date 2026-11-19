#!/usr/bin/env python3
"""Validity suite for 三视角 English YouTube BERTopic experiment (N=28096)."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))


def _append_registry() -> None:
    reg = ROOT / "output/experiments/registry.csv"
    out_abs = (
        ROOT
        / "output/experiments/2026-11-16_youtube_en_robot_imagination_self_bertopic/validity"
    )
    row = {
        "run_id": "2026-11-16_youtube_en_robot_imagination_self_bertopic_validity",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "task": "topic_validity_three_perspectives",
        "hypothesis": "",
        "input_data": "analysis_corpus N=28096",
        "method": "stability+overlap+prop_diff+fightin_words+hierarchy+stm",
        "key_params": "primary_mcs=80;bootstrap=999",
        "output_dir": str(out_abs),
        "status": "completed",
        "decision": "supplementary_not_current",
    }
    fieldnames = [
        "run_id",
        "date",
        "task",
        "hypothesis",
        "input_data",
        "method",
        "key_params",
        "output_dir",
        "status",
        "decision",
    ]
    with reg.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=("stability", "overlap", "prop-diff", "fightin", "hierarchy", "stm", "all"),
        default="all",
    )
    parser.add_argument("--skip-umap-seeds", action="store_true", help="Skip UMAP 42-46 refits")
    parser.add_argument("--bootstrap-B", type=int, default=999)
    args = parser.parse_args()

    from tools.topic_validity.paths import assert_corpus

    assert_corpus()

    steps = {
        "stability": lambda: __import__(
            "tools.topic_validity.stability", fromlist=["run_stability"]
        ).run_stability(run_umap_seeds=not args.skip_umap_seeds),
        "overlap": lambda: __import__(
            "tools.topic_validity.overlap", fromlist=["run_overlap"]
        ).run_overlap(),
        "prop-diff": lambda: __import__(
            "tools.topic_validity.prop_diff", fromlist=["run_prop_diff"]
        ).run_prop_diff(bootstrap_B=args.bootstrap_B),
        "fightin": lambda: __import__(
            "tools.topic_validity.fightin_words", fromlist=["run_fightin_words"]
        ).run_fightin_words(),
        "hierarchy": lambda: __import__(
            "tools.topic_validity.hierarchy", fromlist=["run_hierarchy"]
        ).run_hierarchy(),
        "stm": lambda: __import__(
            "tools.topic_validity.stm", fromlist=["run_stm"]
        ).run_stm(),
    }

    todo = list(steps.keys()) if args.only == "all" else [args.only]
    for name in todo:
        print(f"[validity] {name} …")
        steps[name]()
        print(f"[validity] {name} done")

    if args.only == "all":
        _append_registry()
        print("[validity] registry.csv updated")


if __name__ == "__main__":
    main()