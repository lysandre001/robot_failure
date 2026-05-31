"""CLI for rigorous topic discovery workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from phase1.topic_discovery import TopicDiscoveryConfig, run_pipeline


def main() -> None:
    p = argparse.ArgumentParser(description="Rigorous topic discovery pipeline")
    p.add_argument("--run-id", default="2026-05-27_topic_merged_bge_hdbscan_sensitivity")
    p.add_argument("--experiments-root", type=Path, default=Path("output/experiments"))
    p.add_argument("--base-mcs", type=int, default=50)
    p.add_argument(
        "--step",
        choices=[
            "all",
            "freeze",
            "select",
            "review",
            "codebook",
            "sensitivity",
            "validate",
            "agreement",
            "backfill",
            "document",
        ],
        default="all",
        help="Pipeline step (use 'all' for full run excluding post-coding steps)",
    )
    args = p.parse_args()

    cfg = TopicDiscoveryConfig(
        run_id=args.run_id,
        experiments_root=args.experiments_root,
        base_mcs=args.base_mcs,
    )

    if args.step == "all":
        steps = {"freeze", "select", "review", "codebook", "sensitivity", "validate", "document"}
    else:
        steps = {args.step}

    results = run_pipeline(cfg, steps=steps)
    for k, v in results.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
