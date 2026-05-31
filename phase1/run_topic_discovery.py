"""CLI for rigorous topic discovery workflow.

Supports three tracks:
- Pooled (default):     ``--review-dir topic_discovery_review`` (no ``--comment-level``).
- Level 1 (一级评论):    ``--comment-level 1 --review-dir topic_discovery_l1``.
- Level 2 (二级回复):    ``--comment-level 2 --review-dir topic_discovery_l2``.

For level runs ``--step all`` includes ``fit`` (UMAP+HDBSCAN per mcs on the
sub-corpus). Pass ``--run-both-levels`` to run L1 then L2 in sequence with the
canonical review directory names.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from phase1.topic_discovery import TopicDiscoveryConfig, run_pipeline

STEP_CHOICES = [
    "all",
    "freeze",
    "fit",
    "select",
    "review",
    "codebook",
    "sensitivity",
    "validate",
    "agreement",
    "backfill",
    "document",
]


def _resolve_review_dir(args: argparse.Namespace) -> str:
    if args.review_dir:
        return args.review_dir
    if args.comment_level == 1:
        return "topic_discovery_l1"
    if args.comment_level == 2:
        return "topic_discovery_l2"
    return "topic_discovery_review"


def _run_one(args: argparse.Namespace, *, comment_level: int | None, review_dir: str) -> None:
    cfg = TopicDiscoveryConfig(
        run_id=args.run_id,
        experiments_root=args.experiments_root,
        base_mcs=args.base_mcs,
        comment_level=comment_level,
        review_subdir=review_dir,
        device=args.device,
    )
    if args.step == "all":
        steps = {"freeze", "select", "review", "codebook", "sensitivity", "validate", "document"}
        if cfg.is_level_run:
            steps.add("fit")
    else:
        steps = {args.step}

    banner = f"[topic_discovery] run_id={cfg.run_id} review_dir={cfg.review_dir.name} comment_level={cfg.comment_level} step={args.step}"
    print("=" * len(banner))
    print(banner)
    print("=" * len(banner))
    results = run_pipeline(cfg, steps=steps)
    for k, v in results.items():
        print(f"{k}: {v}")


def main() -> None:
    p = argparse.ArgumentParser(description="Rigorous topic discovery pipeline")
    p.add_argument("--run-id", default="2026-05-27_topic_merged_bge_hdbscan_sensitivity")
    p.add_argument("--experiments-root", type=Path, default=Path("output/experiments"))
    p.add_argument("--base-mcs", type=int, default=50)
    p.add_argument(
        "--comment-level",
        type=int,
        choices=[1, 2],
        default=None,
        help="Filter shared corpus by comment_level (1=一级, 2=二级). Omit for pooled.",
    )
    p.add_argument(
        "--review-dir",
        type=str,
        default=None,
        help=(
            "Sub-directory under the run for this track's outputs. "
            "Defaults: pooled→topic_discovery_review, L1→topic_discovery_l1, L2→topic_discovery_l2."
        ),
    )
    p.add_argument(
        "--run-both-levels",
        action="store_true",
        help="Run L1 then L2 in sequence (overrides --comment-level/--review-dir).",
    )
    p.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device for SentenceTransformer when fitting level HDBSCAN (cpu/mps/auto). Default cpu.",
    )
    p.add_argument(
        "--step",
        choices=STEP_CHOICES,
        default="all",
        help="Pipeline step. 'all' = freeze+select+review+codebook+sensitivity+validate+document (+fit for level runs).",
    )
    args = p.parse_args()

    if args.run_both_levels:
        for level, sub in ((1, "topic_discovery_l1"), (2, "topic_discovery_l2")):
            _run_one(args, comment_level=level, review_dir=sub)
        return

    review_dir = _resolve_review_dir(args)
    _run_one(args, comment_level=args.comment_level, review_dir=review_dir)


if __name__ == "__main__":
    main()
