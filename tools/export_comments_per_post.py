#!/usr/bin/env python3
"""[辅助] 从 clean 表导出每帖一级/二级评论数 + 链接。"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from phase1.config import POST_CATEGORY_BY_POST_CSV, ROOT
from phase1.post_links import DEFAULT_POSTS_CSV, load_post_links


def export_counts(
    input_csv: Path,
    out_csv: Path,
    posts_csv: Path | None = None,
) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    pc = pd.read_csv(POST_CATEGORY_BY_POST_CSV, encoding="utf-8-sig")
    b1_ids = set(pc["帖子id"].astype(str))

    g = df.groupby(["帖子id", "comment_level"]).size().unstack(fill_value=0)
    g = g.rename(columns={1: "L1", 2: "L2"})
    for c in ("L1", "L2"):
        if c not in g.columns:
            g[c] = 0
    g = g[["L1", "L2"]].astype(int)
    g["合计"] = g["L1"] + g["L2"]
    g = g.reset_index()
    g["corpus"] = g["帖子id"].astype(str).map(lambda x: "batch1" if x in b1_ids else "batch2_anchor")
    if "类别" in pc.columns:
        pc = pc.rename(columns={"类别": "post_category"})
    elif {"机器人状态", "人的形象"}.issubset(pc.columns):
        pc = pc.copy()
        pc["post_category"] = pc["机器人状态"].astype(str) + "|" + pc["人的形象"].astype(str)
    else:
        raise ValueError("post_category_by_post.csv 需含「类别」或「机器人状态+人的形象」")
    g = g.merge(pc[["帖子id", "post_category"]], on="帖子id", how="left")
    g["post_category"] = g["post_category"].fillna("(anchor)")

    posts = load_post_links(posts_csv)
    g = g.merge(posts, on="帖子id", how="left")
    g = g.sort_values(["corpus", "post_category", "帖子id"])

    cols = ["帖子id", "帖子链接", "corpus", "post_category", "L1", "L2", "合计"]
    if "帖子正文" in g.columns:
        cols.insert(3, "帖子正文")
    out = g[cols]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", type=Path, default=ROOT / "data" / "clean" / "clean_comments_unified.csv")
    ap.add_argument("--out-csv", type=Path, default=ROOT / "data" / "clean" / "comments_per_post_L1_L2.csv")
    ap.add_argument("--posts-csv", type=Path, default=DEFAULT_POSTS_CSV)
    args = ap.parse_args()
    out = export_counts(args.input_csv, args.out_csv, args.posts_csv)
    print(f"Wrote {args.out_csv} ({len(out)} posts)")
    if out["帖子链接"].isna().any():
        print(f"  WARN: {out['帖子链接'].isna().sum()} posts missing link")


if __name__ == "__main__":
    main()
