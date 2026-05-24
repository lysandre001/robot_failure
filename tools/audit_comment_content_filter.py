#!/usr/bin/env python3
"""[辅助] 审计评论噪音规则：统计剔除原因 + 导出被删行 CSV。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase1.comment_content_filter import COMMENT_CONTENT_FILTER_JSON, run_filter_report


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description="评论噪音规则：统计 + 排除行全量 CSV")
    ap.add_argument(
        "--input-csv",
        type=str,
        default=str(root / "data" / "clean" / "clean_comments_unified_before_filter.csv"),
    )
    ap.add_argument("--rules", type=str, default=str(COMMENT_CONTENT_FILTER_JSON))
    ap.add_argument("--out-dropped", type=str, default=None)
    ap.add_argument("--sample-per-reason", type=int, default=None, metavar="N")
    args = ap.parse_args()
    rep = run_filter_report(
        Path(args.input_csv),
        rules_path=Path(args.rules),
        out_dropped=Path(args.out_dropped) if args.out_dropped else None,
        sample_per_reason=args.sample_per_reason,
    )
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
