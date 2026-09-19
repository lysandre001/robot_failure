#!/usr/bin/env python3
"""汇总各平台 clean 产物 → data/corpus_inventory.csv。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from phase1.config import ROOT

DEFAULT_OUT = ROOT / "data" / "corpus_inventory.csv"


def _read_stage_summary(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    df = pd.read_csv(path)
    return {str(r["stage"]): int(r["rows"]) for _, r in df.iterrows()}


def _read_filter_report(path: Path) -> dict:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scan_clean_dir(
    clean_dir: Path,
    *,
    platform: str,
    source_batch: str,
    raw_path: str = "",
) -> dict:
    stage = _read_stage_summary(clean_dir / "phase1_preprocess_stage_summary.csv")
    filt = _read_filter_report(clean_dir / "comment_content_filter_report.json")
    shared_json = clean_dir / "shared_corpus_summary.json"
    shared_summary = {}
    if shared_json.is_file():
        shared_summary = json.loads(shared_json.read_text(encoding="utf-8"))

    n_before = stage.get("A4_unified_before_filter", 0)
    n_after = stage.get("A5_unified_after_filter", 0)
    n_shared = int(shared_summary.get("n_shared") or stage.get("A6_shared_corpus", 0) or 0)

    posts = 0
    cpp = clean_dir / "comments_per_post_L1_L2.csv"
    if cpp.is_file():
        posts = len(pd.read_csv(cpp))

    return {
        "platform": platform,
        "source_batch": source_batch,
        "raw_path": raw_path,
        "clean_dir": str(clean_dir.resolve()),
        "clean_comments_unified": str((clean_dir / "clean_comments_unified.csv").resolve()),
        "n_posts": posts,
        "n_unified_before_filter": n_before,
        "n_unified_after_filter": n_after,
        "n_shared_corpus": n_shared,
        "filter_retention_pct": round(100.0 * n_after / n_before, 2) if n_before else None,
        "shared_retention_pct": round(100.0 * n_shared / n_after, 2) if n_after else None,
        "filter_dropped_by_rules": filt.get("n_dropped_by_content_rules"),
        "filter_by_reason": json.dumps(filt.get("by_reason", {}), ensure_ascii=False),
        "shared_exclude_stats": json.dumps(
            {k: v for k, v in shared_summary.items() if k.startswith("excluded_")},
            ensure_ascii=False,
        ),
    }


def discover_and_build(
    clean_root: Path,
    *,
    extra_rows: list[dict] | None = None,
) -> pd.DataFrame:
    rows: list[dict] = list(extra_rows or [])
    if not clean_root.is_dir():
        raise FileNotFoundError(clean_root)

    for plat_dir in sorted(clean_root.iterdir()):
        if not plat_dir.is_dir() or plat_dir.name.startswith("."):
            continue
        platform = plat_dir.name
        batches = [p for p in plat_dir.iterdir() if p.is_dir()]
        if batches:
            for batch_dir in sorted(batches):
                meta_path = batch_dir / "phase1_preprocess_stage_summary.md"
                raw_path = ""
                if meta_path.is_file():
                    for line in meta_path.read_text(encoding="utf-8").splitlines():
                        if line.startswith("- raw_input:"):
                            raw_path = line.split(":", 1)[1].strip()
                rows.append(
                    scan_clean_dir(
                        batch_dir,
                        platform=platform,
                        source_batch=batch_dir.name,
                        raw_path=raw_path,
                    )
                )
        elif (plat_dir / "clean_comments_unified.csv").is_file():
            rows.append(
                scan_clean_dir(
                    plat_dir,
                    platform=platform,
                    source_batch="legacy_root",
                )
            )

    legacy = clean_root / "clean_comments_unified.csv"
    if legacy.is_file() and not any(r.get("platform") == "xhs" for r in rows):
        rows.append(
            scan_clean_dir(
                clean_root,
                platform="xhs",
                source_batch="legacy_root",
                raw_path=str(ROOT / "data" / "rawdata" / "小红书帖子数据_merged.xlsx"),
            )
        )

    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="构建跨平台 corpus inventory 表")
    ap.add_argument("--clean-root", type=Path, default=ROOT / "data" / "clean")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    df = discover_and_build(args.clean_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"Wrote {args.out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
