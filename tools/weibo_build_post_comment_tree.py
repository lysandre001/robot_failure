#!/usr/bin/env python3
"""[外部数据] 微博帖-评层级还原（与小红书主流程无关）。"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _strip_bom(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).lstrip("\ufeff")


def _norm_comment_row(row: dict[str, Any]) -> dict[str, str]:
    """统一成 comment_user, comment_text。"""
    keys = {_strip_bom(k): v for k, v in row.items()}
    post_id = _strip_bom(keys.get("post_id", ""))
    uid = _strip_bom(keys.get("user_id", ""))
    url = keys.get("comment_url")  # 错位时可能是评论者昵称
    cu = keys.get("comment_user")
    ct = keys.get("comment_text")

    if ct is None or (isinstance(ct, str) and not ct.strip()):
        # 4 列数据 + 5 列表头：正文进了 comment_user，昵称在 comment_url
        text = _strip_bom(cu) if cu else ""
        nick = _strip_bom(url) if url else ""
    else:
        text = _strip_bom(ct)
        nick = _strip_bom(cu) if cu else ""
    return {
        "post_id": post_id,
        "user_id": uid,
        "comment_user": nick,
        "comment_text": text,
    }


def load_posts(path: Path) -> dict[str, dict[str, str]]:
    by_bid: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            row = {_strip_bom(k): (v or "") for k, v in row.items()}
            bid = row.get("bid", "").strip()
            if not bid:
                continue
            by_bid[bid] = row
    return by_bid


def load_comments_grouped(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for raw in r:
            c = _norm_comment_row(raw)
            pid = c["post_id"]
            if not pid:
                continue
            grouped[pid].append(c)
    return grouped


def build_tree(
    posts_by_bid: dict[str, dict[str, str]],
    comments_by_post_id: dict[str, list[dict[str, str]]],
    *,
    include_empty_posts: bool,
) -> list[dict[str, Any]]:
    """层级：每条 post 下挂 comments 列表；可选是否包含无评论的帖。"""
    trees: list[dict[str, Any]] = []
    seen_bids = set(posts_by_bid.keys()) | set(comments_by_post_id.keys())

    for bid in sorted(seen_bids):
        post = posts_by_bid.get(bid)
        comments = comments_by_post_id.get(bid, [])
        if not include_empty_posts and not comments:
            continue
        node: dict[str, Any] = {
            "bid": bid,
            "post_id_numeric": post.get("id", "") if post else "",
            "post": post,
            "comments": comments,
            "comment_count": len(comments),
        }
        trees.append(node)
    return trees


def print_tree_sample(trees: list[dict[str, Any]], max_posts: int, text_preview: int) -> None:
    for i, t in enumerate(trees[:max_posts]):
        post = t.get("post") or {}
        body = (post.get("微博正文") or "")[:text_preview]
        print(f"\n{'='*60}")
        print(f"[{i+1}] bid={t['bid']}  id={t.get('post_id_numeric', '')}")
        print(f"    用户: {post.get('用户昵称', '')}")
        print(f"    正文: {body}{'...' if len(post.get('微博正文') or '') > text_preview else ''}")
        print(f"    评论数: {t['comment_count']}")
        for j, c in enumerate(t["comments"], 1):
            tx = c["comment_text"][:200]
            print(f"      {j}. @{c['comment_user']}: {tx}{'...' if len(c['comment_text']) > 200 else ''}")


def main() -> None:
    ap = argparse.ArgumentParser(description="用 bid ↔ post_id 连接微博帖与评论，输出层级结构")
    ap.add_argument(
        "--dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="含 机器人摔倒(post).csv 与 机器人摔倒(comment).csv 的目录",
    )
    ap.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="写出 JSON 层级（默认: 同目录 post_comment_tree.json）",
    )
    ap.add_argument(
        "--no-print",
        action="store_true",
        help="不打印样例，只写文件",
    )
    ap.add_argument(
        "--all-posts",
        action="store_true",
        help="包含无评论的帖（默认只输出至少有一条评论的帖）",
    )
    ap.add_argument("--sample-posts", type=int, default=5, help="终端打印前 N 条有结构的帖")
    ap.add_argument("--text-preview", type=int, default=120, help="正文字预览长度")
    args = ap.parse_args()

    d = args.dir
    post_path = d / "机器人摔倒(post).csv"
    cmt_path = d / "机器人摔倒(comment).csv"
    for p in (post_path, cmt_path):
        if not p.is_file():
            raise SystemExit(f"缺少文件: {p}")

    posts = load_posts(post_path)
    comments = load_comments_grouped(cmt_path)
    tree = build_tree(posts, comments, include_empty_posts=args.all_posts)

    out_path = args.out_json or (d / "post_comment_tree.json")

    # JSON 可序列化：post 行里已是字符串
    serializable: list[dict[str, Any]] = []
    for node in tree:
        p = node["post"]
        serializable.append(
            {
                "bid": node["bid"],
                "post_id_numeric": node["post_id_numeric"],
                "post_summary": {
                    "id": p.get("id", "") if p else "",
                    "user_id": p.get("user_id", "") if p else "",
                    "用户昵称": p.get("用户昵称", "") if p else "",
                    "微博正文": p.get("微博正文", "") if p else "",
                    "发布时间": p.get("发布时间", "") if p else "",
                }
                if p
                else None,
                "comment_count": node["comment_count"],
                "comments": node["comments"],
            }
        )

    out_path.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已写出: {out_path}  （共 {len(serializable)} 条顶层帖节点）")

    # 关系统计
    only_cmt = set(comments) - set(posts)
    only_post = set(posts) - set(comments)
    if only_cmt:
        print(f"警告: 评论中有 {len(only_cmt)} 个 post_id 在 post 表无对应 bid（示例: {list(only_cmt)[:3]}）")
    if args.all_posts:
        print(f"无评论的帖: {len([t for t in tree if t['comment_count']==0])} 条；仅有帖无抓评论: {len(only_post - set(comments))} 条")

    if not args.no_print:
        print_tree_sample(tree, args.sample_posts, args.text_preview)


if __name__ == "__main__":
    main()
