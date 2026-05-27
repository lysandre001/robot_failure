"""帖子级研究设计标签：读 config/post_category_by_post.csv 并解析 robot / human 维度。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from phase1.config import POST_CATEGORY_BY_POST_CSV


def normalize_robot_status_label(robot_status: Any) -> str | None:
    """原样保留编码表取值，不做状态别名替换（常态≠中性）。"""
    if robot_status is None or (isinstance(robot_status, float) and pd.isna(robot_status)):
        return None
    s = str(robot_status).strip()
    return s or None


def split_post_category(s: Any) -> tuple[str, str]:
    if pd.isna(s) or str(s).strip() == "":
        return "", ""
    parts = str(s).split("|", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return parts[0].strip(), ""


def load_post_category_by_post(csv_path: Path | str | None = None) -> pd.DataFrame:
    """
    读帖子标签表，返回列：
    帖子id, post_cate_robot, post_cate_human, post_category, robot_status, human_role

    支持两种 CSV 格式：
    - `类别`（状态|角色）
    - `机器人状态` + `人的形象`（或 post_cate_robot / post_cate_human）
    """
    path = Path(csv_path) if csv_path is not None else POST_CATEGORY_BY_POST_CSV
    pc = pd.read_csv(path, encoding="utf-8-sig")
    pc = pc.copy()

    if "类别" in pc.columns:
        pc["post_category"] = pc["类别"].astype(str)
    elif {"机器人状态", "人的形象"}.issubset(pc.columns):
        pc["post_cate_robot"] = pc["机器人状态"].astype(str).str.strip()
        pc["post_cate_human"] = pc["人的形象"].astype(str).str.strip()
        pc["post_category"] = pc["post_cate_robot"] + "|" + pc["post_cate_human"]
    elif {"post_cate_robot", "post_cate_human"}.issubset(pc.columns):
        pc["post_cate_robot"] = pc["post_cate_robot"].astype(str).str.strip()
        pc["post_cate_human"] = pc["post_cate_human"].astype(str).str.strip()
        pc["post_category"] = pc["post_cate_robot"] + "|" + pc["post_cate_human"]
    else:
        raise ValueError(
            f"{path} 需含「类别」或「机器人状态+人的形象」或 post_cate_robot+post_cate_human"
        )

    if "post_cate_robot" not in pc.columns:
        split = pc["post_category"].map(split_post_category)
        pc["post_cate_robot"] = split.map(lambda x: x[0])
        pc["post_cate_human"] = split.map(lambda x: x[1])

    pc["robot_status"] = pc["post_cate_robot"].map(normalize_robot_status_label)
    pc["human_role"] = pc["post_cate_human"].astype(str).str.strip()
    pc.loc[pc["human_role"].isin(("", "nan")), "human_role"] = pd.NA

    keep = ["帖子id", "post_cate_robot", "post_cate_human", "post_category", "robot_status", "human_role"]
    return pc[keep].drop_duplicates(subset=["帖子id"])
