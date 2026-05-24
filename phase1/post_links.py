"""帖子 id → 链接/正文（供导出、标注抽样等复用）。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from phase1.config import ROOT

DEFAULT_POSTS_CSV = ROOT / "data" / "rawdata" / "posts.csv"


def load_post_links(posts_csv: Path | None = None) -> pd.DataFrame:
    """``帖子id`` → ``帖子链接``（及 ``帖子正文``）。"""
    path = posts_csv or DEFAULT_POSTS_CSV
    if not path.is_file():
        raise FileNotFoundError(f"找不到帖子链接表: {path}")
    posts = pd.read_csv(path, encoding="utf-8-sig")
    cols = ["帖子id", "帖子链接"]
    if "帖子正文" in posts.columns:
        cols.append("帖子正文")
    posts = posts.drop_duplicates(subset=["帖子id"], keep="first")
    return posts[cols]


def attach_post_links(df: pd.DataFrame, posts_csv: Path | None = None) -> pd.DataFrame:
    posts = load_post_links(posts_csv)
    out = df.copy()
    if "帖子链接" in out.columns:
        out = out.drop(columns=["帖子链接"])
    if "帖子正文" in out.columns and "帖子正文" in posts.columns:
        pass
    elif "帖子正文" in out.columns:
        posts = posts.drop(columns=["帖子正文"], errors="ignore")
    out = out.merge(posts, on="帖子id", how="left")
    missing = out["帖子链接"].isna().sum()
    if missing:
        print(f"[WARN] {missing} 行未匹配到帖子链接")
    return out
