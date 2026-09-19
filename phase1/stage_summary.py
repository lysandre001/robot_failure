"""Phase1 各阶段计数表（跨平台统一格式）。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_stage_summary_rows(
    *,
    platform: str,
    source_batch: str,
    n_posts: int,
    unified_before: pd.DataFrame,
    unified_after: pd.DataFrame,
    shared_n: int | None = None,
    notes: str = "",
) -> list[dict]:
    def _lvl(df: pd.DataFrame, level: int) -> int:
        if "comment_level" not in df.columns:
            return 0
        return int((df["comment_level"] == level).sum())

    l1_b, l2_b = _lvl(unified_before, 1), _lvl(unified_before, 2)
    l1_a, l2_a = _lvl(unified_after, 1), _lvl(unified_after, 2)

    rows = [
        {
            "stage": "A4_unified_before_filter",
            "description": "一二级合并长表（Phase1过滤前）",
            "rows": len(unified_before),
            "unique_posts": int(unified_before["帖子id"].nunique()) if len(unified_before) else 0,
            "unique_comment_id": len(unified_before),
            "notes": f"L1={l1_b}; L2={l2_b}; platform={platform}; batch={source_batch}",
        },
        {
            "stage": "A5_unified_after_filter",
            "description": "Phase1过滤后（clean_comments_unified）",
            "rows": len(unified_after),
            "unique_posts": int(unified_after["帖子id"].nunique()) if len(unified_after) else 0,
            "unique_comment_id": len(unified_after),
            "notes": f"L1={l1_a}; L2={l2_a}; platform={platform}; batch={source_batch}",
        },
    ]
    if shared_n is not None:
        rows.append(
            {
                "stage": "A6_shared_corpus",
                "description": "主题建模shared analyzable corpus",
                "rows": shared_n,
                "unique_posts": int(unified_after["帖子id"].nunique()) if len(unified_after) else 0,
                "unique_comment_id": shared_n,
                "notes": notes or f"platform={platform}; batch={source_batch}",
            }
        )
    return rows


def write_stage_summary(
    out_dir: Path,
    rows: list[dict],
    *,
    meta: dict | None = None,
) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "phase1_preprocess_stage_summary.csv", index=False, encoding="utf-8-sig")
    if meta:
        lines = ["# Phase1 stage summary", ""]
        for k, v in meta.items():
            lines.append(f"- {k}: {v}")
        lines.extend(["", df.to_string(index=False)])
        (out_dir / "phase1_preprocess_stage_summary.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    return df
