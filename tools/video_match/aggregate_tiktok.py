"""
M1: TikTok 帖子粒度聚合
- 输入: data/tiktok/beijing_robot_marathon_帖子数据(1).csv (长表, post+L1+L2 展平)
- 输出: output/video_match/tiktok_post_category_by_post.csv
  字段对齐 config/post_category_by_post.csv:
      帖子id, 机器人状态, 人的形象, 帖子链接, 一级评论次数, 二级评论次数
  + 新增: matched_xhs_id (留空, 由 M4 填回), 帖子标题, 帖子正文 (供 M4 复核)
- 机器人状态 / 人的形象 留空, 由人工或后续 LLM 打标.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IN = ROOT / "data/tiktok/beijing_robot_marathon_帖子数据(1).csv"
DEFAULT_OUT = ROOT / "output/video_match/tiktok_post_category_by_post.csv"


def aggregate(in_path: Path, out_path: Path, min_l1: int = 0) -> pd.DataFrame:
    df = pd.read_csv(in_path)

    # post-grain: 帖子id 第一次出现的元信息
    post_cols = ["帖子id", "帖子链接", "帖子标题", "帖子正文"]
    posts = df[post_cols].drop_duplicates("帖子id").set_index("帖子id")

    # L1: 唯一一级评论id 计数 (per post)
    l1 = (
        df.dropna(subset=["一级评论id"])
        .drop_duplicates(["帖子id", "一级评论id"])
        .groupby("帖子id")
        .size()
        .rename("一级评论次数")
    )

    # L2: 唯一二级评论id 计数 (per post)
    l2 = (
        df.dropna(subset=["二级评论id"])
        .drop_duplicates(["帖子id", "二级评论id"])
        .groupby("帖子id")
        .size()
        .rename("二级评论次数")
    )

    out = posts.join(l1, how="left").join(l2, how="left").reset_index()
    out["一级评论次数"] = out["一级评论次数"].fillna(0).astype(int)
    out["二级评论次数"] = out["二级评论次数"].fillna(0).astype(int)
    out["机器人状态"] = ""
    out["人的形象"] = ""
    out["matched_xhs_id"] = ""

    out = out[[
        "帖子id", "机器人状态", "人的形象", "帖子链接",
        "一级评论次数", "二级评论次数",
        "matched_xhs_id", "帖子标题", "帖子正文",
    ]]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 永远先落一份全量, 方便回溯
    all_path = out_path.with_name(out_path.stem + "_all.csv")
    out.to_csv(all_path, index=False)

    if min_l1 > 0:
        kept = out[out["一级评论次数"] >= min_l1].reset_index(drop=True)
    else:
        kept = out
    kept.to_csv(out_path, index=False)
    print(f"[M1] all={len(out)} kept(L1>={min_l1})={len(kept)}")
    print(f"[M1] all  -> {all_path}")
    print(f"[M1] kept -> {out_path}")
    return kept


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", default=str(DEFAULT_IN))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--min-l1", type=int, default=30,
                   help="保留一级评论次数 >= 该阈值的帖子; 默认 30 (≈xhs P10), 设 0 关闭过滤")
    a = p.parse_args()
    aggregate(Path(a.inp), Path(a.out), min_l1=a.min_l1)


if __name__ == "__main__":
    main()
