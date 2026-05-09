"""步骤 A：读 Excel、合并类别、去重、统一评论表。"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from phase1.config import POST_CATEGORY_BY_POST_CSV, XLSX


def resolve_data_xlsx(xlsx: Path | str | None = None) -> Path:
    """
    解析数据 Excel 路径，优先级：显式参数 > 环境变量 ROBOTIC_FAILURE_XLSX > 项目根下默认文件名。
    """
    if xlsx is not None:
        return Path(xlsx).expanduser().resolve()
    env = os.environ.get("ROBOTIC_FAILURE_XLSX")
    if env:
        return Path(env).expanduser().resolve()
    return Path(XLSX).expanduser().resolve()


def load_raw_frames(xlsx: Path | str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """读取两个 sheet，返回 (主表, 计数/类别表)。xlsx 缺省则从环境变量或 config.XLSX 推断。"""
    path = resolve_data_xlsx(xlsx)
    if not path.is_file():
        raise FileNotFoundError(f"找不到 Excel 数据文件: {path}")
    main = pd.read_excel(path, sheet_name="小红书帖子数据")
    counts = pd.read_excel(path, sheet_name="导出计数_帖子id")
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


def normalize_post_id(pid) -> str | None:
    """把 Excel/CSV 里的帖子 id 规整成稳定字符串键，便于字典匹配。"""
    if pid is None or pd.isna(pid):
        return None
    if isinstance(pid, (np.integer, np.floating)):
        x = float(pid)
        if np.isnan(x):
            return None
        if x == int(x):
            return str(int(x))
        return str(pid).strip()
    if isinstance(pid, float):
        if pid == int(pid):
            return str(int(pid))
        return str(pid).strip()
    if isinstance(pid, int):
        return str(pid)
    s = str(pid).strip()
    if s.endswith(".0") and s[:-2].replace("-", "").isdigit():
        s = s[:-2]
    return s if s else None


def _read_post_id_category_csv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    tab = pd.read_csv(path, encoding="utf-8-sig")
    if tab.empty or tab.shape[1] < 2:
        return {}
    cols = list(tab.columns)
    id_col = "帖子id" if "帖子id" in cols else cols[0]
    cat_col = "类别" if "类别" in cols else cols[1]
    out: dict[str, str] = {}
    for _, row in tab.iterrows():
        key = normalize_post_id(row[id_col])
        if key is None:
            continue
        if pd.isna(row[cat_col]):
            continue
        val = str(row[cat_col]).strip()
        if not val or val.startswith("#"):
            continue
        out[key] = val
    return out


def apply_post_category_by_post(
    df: pd.DataFrame,
    *,
    overrides: dict[str | int, str] | None = None,
    csv_path: Path | str | None = None,
) -> pd.DataFrame:
    """
    用「帖子 id → 类别」表覆盖 `post_category`。未出现在表中的帖子保留 `merge_post_category` 的结果。

    默认读 `config/post_category_by_post.csv`（列为 `帖子id`,`类别`；列名也可换成前两列）。
    若在代码里传入 `overrides`，会与 CSV 合并（同 id 以 overrides 为准）。
    """
    out = df.copy()
    if "帖子id" not in out.columns or "post_category" not in out.columns:
        return out
    path = Path(csv_path) if csv_path is not None else POST_CATEGORY_BY_POST_CSV
    assign: dict[str, str] = _read_post_id_category_csv(path)
    if overrides:
        for k, v in overrides.items():
            nk = normalize_post_id(k)
            if nk and v:
                assign[nk] = str(v).strip()
    if not assign:
        return out
    new_cats = out["帖子id"].map(lambda p: assign.get(normalize_post_id(p)))
    out["post_category"] = new_cats.fillna(out["post_category"])
    return out


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


def _is_repeated_single_char(text: str) -> bool:
    """
    判断文本是否由同一个字符重复组成（忽略空白）。
    例如：哈哈哈哈、啊啊啊啊、111111。
    """
    t = "".join(str(text).split())
    if not t:
        return False
    return len(set(t)) == 1


def filter_valid_comments(
    u: pd.DataFrame,
    *,
    min_chars: int = 0,
    drop_empty_content: bool = True,
    drop_repeated_single_char: bool = False,
) -> pd.DataFrame:
    """
    对统一评论表进行有效性过滤。

    Parameters
    ----------
    u
        `unified_comments()` 产出的统一评论表。
    min_chars
        最小字符长度阈值（基于 `char_len`，含等号）。
    drop_empty_content
        是否去掉空内容。
    drop_repeated_single_char
        是否去掉“全字相同重复”的文本（如 哈哈哈哈 / 啊啊啊啊）。
    """
    out = u.copy()
    if "content" not in out.columns:
        return out

    out["content"] = out["content"].map(normalize_text)
    if "char_len" not in out.columns:
        out["char_len"] = out["content"].str.len()

    if drop_empty_content:
        out = out[out["char_len"] > 0]
    if min_chars > 0:
        out = out[out["char_len"] >= int(min_chars)]
    if drop_repeated_single_char:
        out = out[~out["content"].map(_is_repeated_single_char)]

    return out.reset_index(drop=True)
