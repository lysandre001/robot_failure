#!/usr/bin/env python3
"""[辅助] 从 Phase 1 clean 表导出 shared analyzable corpus（不跑主题建模）。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase1.config import ROOT
from phase1.topic_modeling import TopicModelingConfig, build_shared_analyzable_corpus, load_topic_stopwords


def export_shared_corpus(
    *,
    input_csv: Path,
    out_shared: Path,
    out_excluded: Path | None = None,
    out_summary: Path | None = None,
) -> dict:
    cfg = TopicModelingConfig(
        run_id="export_shared",
        input_csv=input_csv,
    )
    stopwords = load_topic_stopwords()
    shared, excluded, summary = build_shared_analyzable_corpus(cfg, stopwords=stopwords)

    out_shared.parent.mkdir(parents=True, exist_ok=True)
    shared.to_csv(out_shared, index=False, encoding="utf-8-sig")
    if out_excluded is not None:
        excluded.to_csv(out_excluded, index=False, encoding="utf-8-sig")
    if out_summary is not None:
        out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="导出 shared analyzable corpus（LDA/NMF/BERTopic 共用输入）")
    ap.add_argument(
        "--input-csv",
        type=Path,
        default=ROOT / "data" / "clean" / "clean_comments_unified.csv",
    )
    ap.add_argument(
        "--out-shared",
        type=Path,
        default=ROOT / "data" / "clean" / "shared_analyzable_corpus.csv",
    )
    ap.add_argument(
        "--out-excluded",
        type=Path,
        default=ROOT / "data" / "clean" / "excluded_meaningless.csv",
    )
    ap.add_argument(
        "--out-summary",
        type=Path,
        default=ROOT / "data" / "clean" / "shared_corpus_summary.json",
    )
    args = ap.parse_args()
    summary = export_shared_corpus(
        input_csv=args.input_csv,
        out_shared=args.out_shared,
        out_excluded=args.out_excluded,
        out_summary=args.out_summary,
    )
    print(f"Wrote {args.out_shared} (n_shared={summary['n_shared']:,}, n_raw={summary['n_raw']:,})")
    print(f"Wrote {args.out_excluded}")
    print(f"Wrote {args.out_summary}")


if __name__ == "__main__":
    main()
