"""抖音爬虫宽表 → 统一 31 列 canonical 宽表。"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from phase1.preprocess import normalize_post_id, normalize_text

CANONICAL_COLS = [
    "帖子id",
    "帖子链接",
    "用户id",
    "帖子用户名",
    "帖子类型",
    "帖子标题",
    "帖子发布时间",
    "帖子正文",
    "帖子话题",
    "帖子IP属地",
    "帖子评论数",
    "帖子点赞数",
    "帖子转发数",
    "帖子收藏数",
    "一级评论用户名",
    "一级评论用户id",
    "一级评论内容",
    "一级评论时间",
    "一级评论地址",
    "一级评论点赞数",
    "一级评论回复数",
    "一级评论id",
    "一级评论图片链接",
    "二级评论用户名",
    "二级评论用户id",
    "二级评论内容",
    "二级评论时间",
    "二级评论地址",
    "二级评论点赞数",
    "二级评论id",
    "二级评论图片链接",
    "一级评论语言",
    "一级评论混合",
    "一级评论英文",
    "二级评论语言",
    "二级评论混合",
    "二级评论英文",
]

_LANG_COLS = [
    "一级评论语言",
    "一级评论混合",
    "一级评论英文",
    "二级评论语言",
    "二级评论混合",
    "二级评论英文",
]


def _stable_id(prefix: str, *parts) -> str:
    key = "|".join(normalize_text(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def douyin_rows_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """43 列抖音导出 → 31 列宽表（与 TikTok/XHS 下游一致）。"""
    work = df.copy()
    work["帖子id"] = work["作品视频ID"].map(normalize_post_id)
    work = work[work["帖子id"].notna()].reset_index(drop=True)

    out = pd.DataFrame(index=work.index)
    out["帖子id"] = work["帖子id"]
    out["帖子链接"] = work.get("作品视频链接", pd.Series([""] * len(work)))
    out["用户id"] = work.get("作者sec_uid", pd.Series([pd.NA] * len(work)))
    out["帖子用户名"] = work.get("作者昵称", pd.Series([pd.NA] * len(work)))
    out["帖子类型"] = "video"
    out["帖子标题"] = work.get("作品标题", pd.Series([""] * len(work)))
    out["帖子发布时间"] = work.get("作品发布日期", pd.Series([pd.NA] * len(work)))
    body = work.get("作品标题", pd.Series([""] * len(work))).fillna("").astype(str)
    topic = work.get("作品话题", pd.Series([""] * len(work))).fillna("").astype(str)
    out["帖子正文"] = (body + " " + topic).str.strip()
    out["帖子话题"] = topic.replace("", pd.NA)
    out["帖子IP属地"] = work.get("城市", pd.Series([pd.NA] * len(work)))
    out["帖子评论数"] = work.get("作品评论数", pd.Series([pd.NA] * len(work)))
    out["帖子点赞数"] = work.get("作品点赞数", pd.Series([pd.NA] * len(work)))
    out["帖子转发数"] = work.get("作品转发数", pd.Series([pd.NA] * len(work)))
    out["帖子收藏数"] = work.get("作品收藏数", pd.Series([pd.NA] * len(work)))

    out["一级评论用户名"] = work.get("一级评论名称", pd.Series([pd.NA] * len(work)))
    out["一级评论用户id"] = work.get("一级用户ID", pd.Series([pd.NA] * len(work)))
    out["一级评论内容"] = work.get("一级评论内容", pd.Series([pd.NA] * len(work)))
    out["一级评论时间"] = work.get("一级评论时间", pd.Series([pd.NA] * len(work)))
    out["一级评论地址"] = work.get("一级用户ip地址", pd.Series([pd.NA] * len(work)))
    out["一级评论点赞数"] = work.get("一级评论点赞量", pd.Series([pd.NA] * len(work)))
    out["一级评论回复数"] = pd.NA
    out["一级评论图片链接"] = work.get("一级评论图片", pd.Series([pd.NA] * len(work)))

    out["二级评论用户名"] = work.get("回复名称", pd.Series([pd.NA] * len(work)))
    out["二级评论用户id"] = work.get("回复用户ID", pd.Series([pd.NA] * len(work)))
    out["二级评论内容"] = work.get("回复内容", pd.Series([pd.NA] * len(work)))
    out["二级评论时间"] = work.get("回复时间", pd.Series([pd.NA] * len(work)))
    out["二级评论地址"] = work.get("回复用户ip地址", pd.Series([pd.NA] * len(work)))
    out["二级评论点赞数"] = pd.NA
    out["二级评论图片链接"] = work.get("二级评论图片", pd.Series([pd.NA] * len(work)))

    l1_ids = []
    l2_ids = []
    for _, row in work.iterrows():
        pid = row["帖子id"]
        l1_content = row.get("一级评论内容")
        if pd.isna(l1_content) or not str(l1_content).strip():
            l1_ids.append(pd.NA)
        else:
            l1_ids.append(
                _stable_id(
                    "dy_l1",
                    pid,
                    row.get("一级用户ID"),
                    l1_content,
                    row.get("一级评论时间"),
                )
            )
        reply = row.get("回复内容")
        if pd.isna(reply) or not str(reply).strip():
            l2_ids.append(pd.NA)
        else:
            l2_ids.append(
                _stable_id(
                    "dy_l2",
                    pid,
                    row.get("一级用户ID"),
                    l1_content,
                    row.get("回复用户ID"),
                    reply,
                    row.get("回复时间"),
                )
            )

    out["一级评论id"] = l1_ids
    out["二级评论id"] = l2_ids

    for col in _LANG_COLS:
        if col in work.columns:
            out[col] = work[col]

    has_l1 = out["一级评论id"].notna()
    out = out.loc[has_l1].reset_index(drop=True)
    for col in CANONICAL_COLS:
        if col not in out.columns:
            out[col] = pd.NA
    return out[CANONICAL_COLS]


def load_douyin_csv(path: Path | str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """返回 (main 宽表, counts/post_category 表)。"""
    raw = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    main = douyin_rows_to_canonical(raw)
    posts = main["帖子id"].drop_duplicates()
    counts = pd.DataFrame({"帖子id": posts, "post_category": "unknown"})
    return main, counts


def sanitize_douyin_csv(
    input_csv: Path,
    *,
    output_csv: Path | None = None,
    qc_md: Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    main, _counts = load_douyin_csv(input_csv)
    qc = {
        "platform": "douyin",
        "input_csv": str(input_csv.resolve()),
        "n_output_rows": len(main),
        "n_unique_posts": int(main["帖子id"].nunique()),
    }
    if output_csv is not None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        main.to_csv(output_csv, index=False, encoding="utf-8-sig")
        qc["output_csv"] = str(output_csv.resolve())
    if qc_md is not None:
        qc_md.parent.mkdir(parents=True, exist_ok=True)
        qc_md.write_text(
            "\n".join(
                [
                    "# 抖音宽表 canonical 化 QC",
                    "",
                    f"- 输入：`{input_csv}`",
                    f"- 输出行：{len(main):,}",
                    f"- 唯一帖子：{qc['n_unique_posts']}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        qc["qc_md"] = str(qc_md.resolve())
    return main, qc
