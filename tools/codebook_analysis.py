#!/usr/bin/env python3
"""码本标签 × 帖子分类横切表（论文数字真源 → output/analysis/）。"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from phase1.config import ROOT
from phase1.post_category_labels import HUMAN_ROLES_CANONICAL, normalize_human_role

ROBOT_STATES = ["失败", "弱势", "常态", "强势", "混合"]
ROBOT_ORDER = ROBOT_STATES + ["unknown"]


def _load_labels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, low_memory=False)
    if "comment_id" not in df.columns:
        raise ValueError(f"{path} 需含 comment_id")
    return df


def _load_clean(platform: str, batch: str) -> pd.DataFrame:
    p = ROOT / "data" / "clean" / platform / batch / "clean_comments_unified.csv"
    if not p.is_file():
        raise FileNotFoundError(p)
    df = pd.read_csv(p, dtype=str, low_memory=False)
    for c in ("robot_status", "human_role", "post_category"):
        if c not in df.columns:
            df[c] = ""
    df["human_role"] = df["human_role"].map(lambda v: normalize_human_role(v) or "unknown")
    rs = df["robot_status"].fillna("").astype(str).str.strip()
    df["robot_status"] = rs.where(rs.isin(ROBOT_STATES) & rs.str.len().gt(0), "unknown")
    return df


def marginal(df: pd.DataFrame, col: str, order: list[str] | None = None) -> pd.DataFrame:
    vc = df[col].value_counts(dropna=False)
    if order:
        vc = vc.reindex(order + [x for x in vc.index if x not in order]).fillna(0).astype(int)
    out = vc.reset_index()
    out.columns = [col, "n_comments"]
    out["pct"] = (out["n_comments"] / out["n_comments"].sum() * 100).round(1)
    return out


def crosstab_post(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    ct = pd.crosstab(df["robot_status"], df["human_role"], values=df[value_col], aggfunc="count")
    ct = ct.reindex(index=ROBOT_ORDER, columns=list(HUMAN_ROLES_CANONICAL) + ["unknown"]).fillna(0).astype(int)
    return ct


def run(
    *,
    labels_path: Path,
    platform: str,
    batch: str,
    out_dir: Path,
    subject_col: str = "主体",
    emotion_col: str = "情感",
    stance_col: str = "stance",
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = _load_labels(labels_path)
    clean = _load_clean(platform, batch)
    merged = labels.merge(
        clean[["comment_id", "robot_status", "human_role", "post_category"]],
        on="comment_id",
        how="left",
    )
    merged["robot_status"] = merged["robot_status"].fillna("unknown")
    merged["human_role"] = merged["human_role"].fillna("unknown")

    meta = {
        "labels_path": str(labels_path.resolve()),
        "platform": platform,
        "batch": batch,
        "n_labels": len(labels),
        "n_merged": len(merged),
    }
    pd.DataFrame([meta]).to_csv(out_dir / "run_meta.csv", index=False, encoding="utf-8-sig")

    for col, fname in [
        (subject_col, "marginal_subject.csv"),
        (emotion_col, "marginal_emotion.csv"),
        (stance_col, "marginal_stance.csv"),
    ]:
        if col in merged.columns:
            marginal(merged, col).to_csv(out_dir / fname, index=False, encoding="utf-8-sig")

    if subject_col in merged.columns:
        crosstab_post(merged, subject_col).to_csv(
            out_dir / "crosstab_robot_human_subject.csv", encoding="utf-8-sig"
        )
    if stance_col in merged.columns:
        crosstab_post(merged, stance_col).to_csv(
            out_dir / "crosstab_robot_human_stance.csv", encoding="utf-8-sig"
        )

    print(f"written → {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser(description="码本标签 × 帖子分类 → output/analysis/")
    ap.add_argument("--labels", type=Path, required=True, help="gold 或 LLM comparison_wide.csv")
    ap.add_argument("--platform", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--analysis-id", default="codebook_postdist")
    args = ap.parse_args()
    out = args.out_dir or (ROOT / "output" / "analysis" / args.analysis_id)
    run(labels_path=args.labels, platform=args.platform.strip(), batch=args.batch.strip(), out_dir=out)


if __name__ == "__main__":
    main()
