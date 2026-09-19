"""步骤 A：读 Excel、合并类别、去重、统一评论表。"""
from __future__ import annotations

from typing import Any

import json
import os
from collections import Counter
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


def counts_from_main(main: pd.DataFrame, *, default_category: str = "unknown") -> pd.DataFrame:
    posts = main["帖子id"].drop_duplicates()
    return pd.DataFrame({"帖子id": posts, "post_category": default_category})


def load_raw_wide_table(
    input_path: Path | str,
    *,
    platform: str = "xhs",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    统一宽表读取：XHS Excel、TikTok/XHS CSV、抖音 43 列 CSV。
    返回 (main 宽表, post_category 计数表)。
    """
    path = Path(input_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"找不到数据文件: {path}")

    plat = platform.lower().strip()
    if plat == "douyin":
        from phase1.douyin_io import load_douyin_csv

        return load_douyin_csv(path)

    if path.suffix.lower() in (".xlsx", ".xls"):
        return load_raw_frames(path)

    from phase1.wide_io import read_wide_csv

    main = read_wide_csv(path, platform=plat)
    return main, counts_from_main(main)


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


def _split_post_category_label(s: Any) -> tuple[str, str]:
    if pd.isna(s) or str(s).strip() == "":
        return "", ""
    parts = str(s).split("|", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return parts[0].strip(), ""


def load_post_category_table(path: Path | str | None = None) -> pd.DataFrame:
    """
    读取帖子编码表，返回 ``帖子id, post_category, robot_status, human_role``。

    支持三种 config 格式：
    - ``机器人状态`` + ``人的形象``（当前 canonical）
    - ``post_category`` 或 ``类别``（``状态|角色`` 合并字符串）
    """
    p = Path(path) if path is not None else POST_CATEGORY_BY_POST_CSV
    tab = pd.read_csv(p, encoding="utf-8-sig")
    if tab.empty:
        return pd.DataFrame(columns=["帖子id", "post_category", "robot_status", "human_role"])

    id_col = "帖子id" if "帖子id" in tab.columns else tab.columns[0]
    out = tab[[id_col]].copy().rename(columns={id_col: "帖子id"})
    out["帖子id"] = out["帖子id"].map(normalize_post_id)

    if {"机器人状态", "人的形象"}.issubset(tab.columns):
        out["robot_status"] = tab["机器人状态"].map(lambda x: "" if pd.isna(x) else str(x).strip())
        out["human_role"] = tab["人的形象"].map(lambda x: "" if pd.isna(x) else str(x).strip())
        out["post_category"] = out["robot_status"] + "|" + out["human_role"]
    elif "post_category" in tab.columns:
        out["post_category"] = tab["post_category"].map(lambda x: "" if pd.isna(x) else str(x).strip())
        split = out["post_category"].map(_split_post_category_label)
        out["robot_status"] = split.map(lambda x: x[0])
        out["human_role"] = split.map(lambda x: x[1])
    elif "类别" in tab.columns:
        out["post_category"] = tab["类别"].map(lambda x: "" if pd.isna(x) else str(x).strip())
        split = out["post_category"].map(_split_post_category_label)
        out["robot_status"] = split.map(lambda x: x[0])
        out["human_role"] = split.map(lambda x: x[1])
    else:
        cat_col = tab.columns[1]
        out["post_category"] = tab[cat_col].map(lambda x: "" if pd.isna(x) else str(x).strip())
        split = out["post_category"].map(_split_post_category_label)
        out["robot_status"] = split.map(lambda x: x[0])
        out["human_role"] = split.map(lambda x: x[1])

    out = out.dropna(subset=["帖子id"])
    out = out[out["post_category"].str.len() > 0]
    return out.drop_duplicates(subset=["帖子id"], keep="first")[
        ["帖子id", "post_category", "robot_status", "human_role"]
    ]


def _read_post_id_category_csv(path: Path) -> dict[str, str]:
    tab = load_post_category_table(path)
    return dict(zip(tab["帖子id"], tab["post_category"]))


def apply_post_category_by_post(
    df: pd.DataFrame,
    *,
    overrides: dict[str | int, str] | None = None,
    csv_path: Path | str | None = None,
) -> pd.DataFrame:
    """
    用研究编码表覆盖 ``post_category`` / ``robot_status`` / ``human_role``。

    默认读 ``config/post_category_by_post.csv``（``机器人状态`` + ``人的形象``，或 legacy ``类别``）。
    未出现在表中的帖子保留 ``merge_post_category`` 的结果；``robot_status`` / ``human_role`` 留空。
    """
    out = df.copy()
    if "帖子id" not in out.columns:
        return out
    path = Path(csv_path) if csv_path is not None else POST_CATEGORY_BY_POST_CSV
    if not path.is_file():
        return out

    prev_cat = out["post_category"] if "post_category" in out.columns else None
    pc = load_post_category_table(path)
    if overrides:
        extra_rows = []
        for k, v in overrides.items():
            nk = normalize_post_id(k)
            if not nk or not v:
                continue
            rs, hr = _split_post_category_label(str(v).strip())
            extra_rows.append(
                {"帖子id": nk, "post_category": str(v).strip(), "robot_status": rs, "human_role": hr}
            )
        if extra_rows:
            pc = pd.concat([pc, pd.DataFrame(extra_rows)], ignore_index=True)
            pc = pc.drop_duplicates(subset=["帖子id"], keep="last")

    out["帖子id"] = out["帖子id"].map(normalize_post_id)
    out = out.drop(columns=["post_category", "robot_status", "human_role"], errors="ignore")
    out = out.merge(pc, on="帖子id", how="left")
    if prev_cat is not None:
        out["post_category"] = out["post_category"].fillna(prev_cat)
    if "post_category" in out.columns:
        out["post_category"] = out["post_category"].fillna("unknown")
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
        "robot_status",
        "human_role",
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
        "一级评论语言",
        "一级评论混合",
        "一级评论英文",
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
            "一级评论语言": "language",
            "一级评论混合": "is_mixed",
            "一级评论英文": "content_en",
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
        "robot_status",
        "human_role",
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
        "二级评论语言",
        "二级评论混合",
        "二级评论英文",
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
            "二级评论语言": "language",
            "二级评论混合": "is_mixed",
            "二级评论英文": "content_en",
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
        "robot_status",
        "human_role",
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
        "language",
        "is_mixed",
        "content_en",
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


def refresh_post_labels(df: pd.DataFrame, *, csv_path: Path | str | None = None) -> pd.DataFrame:
    """在已有 clean 表上刷新 ``post_category`` / ``robot_status`` / ``human_role``。"""
    out = df.copy()
    out["帖子id"] = out["帖子id"].map(normalize_post_id)
    prev_cat = out["post_category"] if "post_category" in out.columns else None
    pc = load_post_category_table(csv_path)
    out = out.drop(columns=["post_category", "robot_status", "human_role"], errors="ignore")
    out = out.merge(pc, on="帖子id", how="left")
    if prev_cat is not None:
        out["post_category"] = out["post_category"].fillna(prev_cat)
    out["post_category"] = out["post_category"].fillna("unknown")
    return out


def filter_valid_comments(
    u: pd.DataFrame,
    *,
    min_chars: int = 0,
    drop_empty_content: bool = True,
    drop_repeated_single_char: bool = False,
    content_rules_path: Path | str | None = None,
    content_filter_report_path: Path | str | None = None,
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
        若传入 ``content_rules_path``，则该项被忽略（重复片段由 JSON 中 repeated_fragment 控制）。
    content_rules_path
        ``config/topic_modeling/comment_content_filter.json`` 等；启用纯 emoji / 含 @ 提及 / 重复短片段等规则。
    content_filter_report_path
        若给定，将本次规则命中统计写入 JSON（仅在与 content_rules_path 同时启用时有效）。
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
    if content_rules_path is not None:
        from phase1.comment_content_filter import classify_comment_noise, load_comment_filter_rules

        rules = load_comment_filter_rules(Path(content_rules_path))
        reasons = [classify_comment_noise(t, rules) for t in out["content"]]
        if content_filter_report_path is not None:
            ctr = Counter(r for r in reasons if r is not None)
            rep = {
                "content_rules_path": str(Path(content_rules_path).resolve()),
                "n_after_basic_filters": int(len(out)),
                "n_dropped_by_content_rules": int(sum(1 for r in reasons if r is not None)),
                "by_reason": dict(ctr.most_common()),
            }
            rp = Path(content_filter_report_path)
            rp.parent.mkdir(parents=True, exist_ok=True)
            with open(rp, "w", encoding="utf-8") as f:
                json.dump(rep, f, ensure_ascii=False, indent=2)
        out = out[[r is None for r in reasons]]
    elif drop_repeated_single_char:
        out = out[~out["content"].map(_is_repeated_single_char)]

    return out.reset_index(drop=True)
