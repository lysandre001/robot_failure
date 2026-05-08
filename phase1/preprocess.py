"""步骤 A：读 Excel、合并类别、去重、统一评论表。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from phase1.config import XLSX


def load_raw_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """读取两个 sheet，返回 (主表, 计数/类别表)。"""
    main = pd.read_excel(XLSX, sheet_name="小红书帖子数据")
    counts = pd.read_excel(XLSX, sheet_name="导出计数_帖子id")
    ren = {}
    if "类别" in counts.columns:
        ren["类别"] = "post_category"
    if "计数" in counts.columns:
        ren["计数"] = "导出计数"
    if ren:
        counts = counts.rename(columns=ren)
    if "post_category" not in counts.columns:
        raise ValueError("导出计数 sheet 需含列「类别」或 post_category")
    pid = "帖子id" if "帖子id" in counts.columns else counts.columns[0]
    if pid != "帖子id":
        counts = counts.rename(columns={pid: "帖子id"})
    extra = ["导出计数"] if "导出计数" in counts.columns else []
    return main, counts[["帖子id", "post_category"] + extra]


def merge_post_category(main: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    df = main.merge(counts[["帖子id", "post_category"]], on="帖子id", how="left")
    df["post_category"] = df["post_category"].fillna("unknown")
    return df


def coerce_engagement(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in (
        "like_count",
        "reply_count",
        "帖子点赞数",
        "帖子评论数",
        "帖子收藏数",
        "帖子转发数",
    ):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def normalize_text(s) -> str:
    if pd.isna(s):
        return ""
    return str(s).strip()


def build_level1(df: pd.DataFrame) -> pd.DataFrame:
    """一级评论按 comment_id 去重一条一行。"""
    df = df.copy()
    rename_map = {}
    for c in df.columns:
        if "一级评" in c and "一级评论用户id" not in c and "一级评论内容" not in c:
            if "用户id" in c:
                rename_map[c] = "一级评论用户id"
    if rename_map:
        df = df.rename(columns=rename_map)

    cols = [
        "帖子id",
        "post_category",
        "帖子标题",
        "帖子正文",
        "帖子点赞数",
        "帖子评论数",
        "帖子收藏数",
        "帖子转发数",
        "一级评论id",
        "一级评论用户id",
        "一级评论内容",
        "一级评论时间",
        "一级评论地址",
        "一级评论点赞数",
        "一级评论回复数",
    ]
    use = [c for c in cols if c in df.columns]
    l1 = df[use].dropna(subset=["一级评论id"])
    l1 = l1.drop_duplicates(subset=["一级评论id"], keep="first")
    l1 = l1.rename(
        columns={
            "一级评论id": "comment_id",
            "一级评论用户id": "user_id",
            "一级评论内容": "content",
            "一级评论时间": "comment_time",
            "一级评论地址": "location",
            "一级评论点赞数": "like_count",
            "一级评论回复数": "reply_count",
        }
    )
    l1["comment_level"] = 1
    l1["parent_comment_id"] = np.nan
    return l1


def build_level2(df: pd.DataFrame) -> pd.DataFrame:
    """二级评论按二级 id 去重。"""
    cols = [
        "帖子id",
        "post_category",
        "帖子标题",
        "帖子点赞数",
        "帖子评论数",
        "一级评论id",
        "二级评论id",
        "二级评论用户id",
        "二级评论内容",
        "二级评论时间",
        "二级评论地址",
        "二级评论点赞数",
    ]
    use = [c for c in cols if c in df.columns]
    l2 = df[use].dropna(subset=["二级评论id"])
    l2 = l2.drop_duplicates(subset=["二级评论id"], keep="first")
    l2 = l2.rename(
        columns={
            "二级评论id": "comment_id",
            "一级评论id": "parent_comment_id",
            "二级评论用户id": "user_id",
            "二级评论内容": "content",
            "二级评论时间": "comment_time",
            "二级评论地址": "location",
            "二级评论点赞数": "like_count",
        }
    )
    l2["comment_level"] = 2
    l2["reply_count"] = np.nan
    return l2


def unified_comments(l1: pd.DataFrame, l2: pd.DataFrame) -> pd.DataFrame:
    """纵向合并一级+二级，不修改入参。"""
    l1 = l1.copy()
    l2 = l2.copy()
    common = [
        "帖子id",
        "post_category",
        "帖子标题",
        "帖子点赞数",
        "帖子评论数",
        "comment_level",
        "comment_id",
        "parent_comment_id",
        "user_id",
        "content",
        "comment_time",
        "location",
        "like_count",
        "reply_count",
    ]
    for t in (l1, l2):
        for c in common:
            if c not in t.columns:
                t[c] = np.nan
    u = pd.concat([l1[common], l2[common]], ignore_index=True)
    u["content"] = u["content"].map(normalize_text)
    u["char_len"] = u["content"].str.len()
    return u
