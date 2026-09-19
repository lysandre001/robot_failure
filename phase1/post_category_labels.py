"""帖子级研究设计标签：读 config/post_category_by_post.csv 并解析 robot / human 维度。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from phase1.config import POST_CATEGORY_BY_POST_CSV

HUMAN_ROLE_SERVICE_CARE = "服务照护"
HUMAN_ROLES_CANONICAL: tuple[str, ...] = (
    HUMAN_ROLE_SERVICE_CARE,
    "被超越者",
    "观众",
)
HUMAN_ROLES_LEGACY_TO_CANONICAL: dict[str, str] = {
    "服务者": HUMAN_ROLE_SERVICE_CARE,
    "抢救者": HUMAN_ROLE_SERVICE_CARE,
    "保护者": HUMAN_ROLE_SERVICE_CARE,
    HUMAN_ROLE_SERVICE_CARE: HUMAN_ROLE_SERVICE_CARE,
    "被超越者": "被超越者",
    "观众": "观众",
}
HUMAN_ROLE_MERGE_RULE = (
    "人的形象全局 schema 仅三档：服务照护、被超越者、观众。"
    "历史编码 服务者/抢救者/保护者 读入时归并为 服务照护。"
)
# 与 canonical 同序；保留别名供附录 / notebook
HUMAN_ROLE_ANALYSIS_ORDER: tuple[str, ...] = HUMAN_ROLES_CANONICAL
HUMAN_ROLE_ANALYSIS_GROUP_LABEL = HUMAN_ROLE_SERVICE_CARE
HUMAN_ROLE_ANALYSIS_EN: dict[str, str] = {
    HUMAN_ROLE_SERVICE_CARE: "Service and care",
    "被超越者": "The surpassed",
    "观众": "Spectator",
}


def normalize_human_role(human_role: Any) -> str | None:
    """帖子级「人的形象」→ schema 三档；空值返回 None。"""
    if human_role is None or (isinstance(human_role, float) and pd.isna(human_role)):
        return None
    s = str(human_role).strip()
    if not s or s.lower() == "nan":
        return None
    if s in HUMAN_ROLES_LEGACY_TO_CANONICAL:
        return HUMAN_ROLES_LEGACY_TO_CANONICAL[s]
    raise ValueError(
        f"未知 human_role={s!r}。允许：{', '.join(HUMAN_ROLES_CANONICAL)}；"
        f"legacy 服务者/抢救者/保护者 会自动归并为 服务照护。"
    )


def human_role_to_analysis_group(human_role: Any) -> str | None:
    """与 normalize_human_role 相同（兼容旧 notebook / 横切代码）。"""
    return normalize_human_role(human_role)


def normalize_robot_status_label(robot_status: Any) -> str | None:
    """原样保留编码表取值，不做状态别名替换（常态≠中性）。"""
    if robot_status is None or (isinstance(robot_status, float) and pd.isna(robot_status)):
        return None
    s = str(robot_status).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def split_post_category(s: Any) -> tuple[str, str]:
    if pd.isna(s) or str(s).strip() == "":
        return "", ""
    parts = str(s).split("|", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return parts[0].strip(), ""


def _apply_human_role_canonical(pc: pd.DataFrame) -> pd.DataFrame:
    out = pc.copy()
    if "post_cate_human" in out.columns:
        out["post_cate_human"] = out["post_cate_human"].map(
            lambda x: normalize_human_role(x) or (str(x).strip() if pd.notna(x) else "")
        )
    if "human_role" in out.columns:
        out["human_role"] = out["human_role"].map(normalize_human_role)
    if "post_cate_robot" in out.columns and "post_cate_human" in out.columns:
        both = out["post_cate_robot"].astype(str).str.len().gt(0) & out["post_cate_human"].astype(str).str.len().gt(0)
        out.loc[both, "post_category"] = (
            out.loc[both, "post_cate_robot"].astype(str).str.strip()
            + "|"
            + out.loc[both, "post_cate_human"].astype(str).str.strip()
        )
    elif "post_category" in out.columns:
        split = out["post_category"].map(split_post_category)
        rs = split.map(lambda x: x[0])
        hr = split.map(lambda x: normalize_human_role(x[1]) or x[1].strip())
        out["post_category"] = rs + "|" + hr.astype(str)
    return out


def load_post_category_by_post(csv_path: Path | str | None = None) -> pd.DataFrame:
    """
    读帖子标签表，返回列：
    帖子id, post_cate_robot, post_cate_human, post_category, robot_status, human_role
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

    pc = _apply_human_role_canonical(pc)
    pc["robot_status"] = pc["post_cate_robot"].map(normalize_robot_status_label)
    pc["human_role"] = pc["post_cate_human"].map(normalize_human_role)
    pc.loc[pc["human_role"].isna(), "human_role"] = pd.NA

    keep = ["帖子id", "post_cate_robot", "post_cate_human", "post_category", "robot_status", "human_role"]
    return pc[keep].drop_duplicates(subset=["帖子id"])
