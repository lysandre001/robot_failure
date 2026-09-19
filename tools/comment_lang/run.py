#!/usr/bin/env python3
"""Annotate raw wide tables with comment language / is_mixed / English translation."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from phase1.config import ROOT
from phase1.douyin_io import _stable_id
from phase1.preprocess import normalize_post_id, normalize_text
from tools.comment_lang.checkpoint import purge_failed_checkpoint
from tools.comment_lang.detect import detect_language, load_config, needs_translation
from tools.comment_lang.io_utils import (
    normalize_comment_id,
    read_raw_csv,
    read_raw_xlsx,
    repair_tiktok_ids_from_clean,
    save_raw_csv,
    valid_en,
)
from tools.comment_lang.translate import translate_records

L1_LANG = "一级评论语言"
L1_MIXED = "一级评论混合"
L1_EN = "一级评论英文"
L2_LANG = "二级评论语言"
L2_MIXED = "二级评论混合"
L2_EN = "二级评论英文"

def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        cur = os.environ.get(key, "")
        if not cur or cur.startswith("your_"):
            os.environ[key] = val


JOBS = [
    {
        "platform": "xhs",
        "batch": "merged",
        "path": ROOT / "data" / "rawdata" / "小红书帖子数据_merged.xlsx",
        "kind": "xlsx",
    },
    {
        "platform": "tiktok",
        "batch": "2604-marathon",
        "path": ROOT / "data" / "rawdata" / "tiktok" / "2604-marathon" / "beijing_robot_marathon_帖子数据(1).csv",
        "kind": "csv",
        "clean_lookup": ROOT / "data" / "clean" / "tiktok" / "2604-marathon" / "clean_comments_unified.csv",
    },
    {
        "platform": "tiktok",
        "batch": "2608-olympic",
        "path": ROOT / "data" / "rawdata" / "tiktok" / "2608-olympic" / "tiktok_World_Humanoid_Robot_Games_帖子数据.csv",
        "kind": "csv",
    },
    {
        "platform": "douyin",
        "batch": "2608-olympic",
        "path": ROOT / "data" / "rawdata" / "douyin" / "2608-olympic" / "抖音_世界人形机器人运动会.csv",
        "kind": "douyin",
    },
    {
        "platform": "youtube",
        "batch": "2604-marathon",
        "path": ROOT / "data" / "clean" / "youtube" / "2604-marathon" / "clean_comments_unified.csv",
        "kind": "clean",
    },
    {
        "platform": "youtube",
        "batch": "2608-olympic",
        "path": ROOT / "data" / "clean" / "youtube" / "2608-olympic" / "clean_comments_unified.csv",
        "kind": "clean",
    },
]

CLEAN_LANG_COLS = ("language", "is_mixed", "content_en")


def _ensure_lang_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in (L1_LANG, L1_MIXED, L1_EN, L2_LANG, L2_MIXED, L2_EN):
        if c not in df.columns:
            df[c] = pd.NA
    return df


def _ensure_clean_lang_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in CLEAN_LANG_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    return df


def _job_kind(job: dict) -> str:
    return str(job.get("kind") or "csv")


def _douyin_l1_id(row: pd.Series) -> str | None:
    pid = normalize_post_id(row.get("作品视频ID"))
    content = row.get("一级评论内容")
    if pid is None or pd.isna(content) or not str(content).strip():
        return None
    return _stable_id("dy_l1", pid, row.get("一级用户ID"), content, row.get("一级评论时间"))


def _douyin_l2_id(row: pd.Series) -> str | None:
    pid = normalize_post_id(row.get("作品视频ID"))
    l1_content = row.get("一级评论内容")
    reply = row.get("回复内容")
    if pid is None or pd.isna(reply) or not str(reply).strip():
        return None
    return _stable_id(
        "dy_l2",
        pid,
        row.get("一级用户ID"),
        l1_content,
        row.get("回复用户ID"),
        reply,
        row.get("回复时间"),
    )


def extract_unique_comments(
    df: pd.DataFrame, *, platform: str, kind: str = "csv"
) -> list[dict[str, Any]]:
    """Return deduped comments: comment_id, content, level (1|2)."""
    plat = platform.lower()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    if kind == "clean":
        for _, row in df.iterrows():
            cid = normalize_comment_id(row.get("comment_id"))
            content = row.get("content")
            if not cid or cid in seen or pd.isna(content) or not str(content).strip():
                continue
            seen.add(cid)
            try:
                level = int(row.get("comment_level", 1))
            except (TypeError, ValueError):
                level = 1
            out.append({"comment_id": cid, "content": normalize_text(content), "level": level})
        return out

    if plat == "douyin":
        for _, row in df.iterrows():
            cid = _douyin_l1_id(row)
            content = row.get("一级评论内容")
            if cid and cid not in seen and pd.notna(content) and str(content).strip():
                seen.add(cid)
                out.append({"comment_id": cid, "content": normalize_text(content), "level": 1})
            cid2 = _douyin_l2_id(row)
            content2 = row.get("回复内容")
            if cid2 and cid2 not in seen and pd.notna(content2) and str(content2).strip():
                seen.add(cid2)
                out.append({"comment_id": cid2, "content": normalize_text(content2), "level": 2})
        return out

    for _, row in df.iterrows():
        cid = normalize_comment_id(row.get("一级评论id"))
        content = row.get("一级评论内容")
        if cid and pd.notna(content) and str(content).strip():
            if cid not in seen:
                seen.add(cid)
                out.append({"comment_id": cid, "content": normalize_text(content), "level": 1})
        cid2 = normalize_comment_id(row.get("二级评论id"))
        content2 = row.get("二级评论内容")
        if cid2 and pd.notna(content2) and str(content2).strip():
            if cid2 not in seen:
                seen.add(cid2)
                out.append({"comment_id": cid2, "content": normalize_text(content2), "level": 2})
    return out


def _row_for_rec(df: pd.DataFrame, rec: dict[str, Any], *, platform: str) -> pd.Series | None:
    plat = platform.lower()
    if plat == "douyin":
        for _, row in df.iterrows():
            if rec["level"] == 1 and _douyin_l1_id(row) == rec["comment_id"]:
                return row
            if rec["level"] == 2 and _douyin_l2_id(row) == rec["comment_id"]:
                return row
        return None
    id_col = "一级评论id" if rec["level"] == 1 else "二级评论id"
    mask = df[id_col].astype(str).str.strip() == rec["comment_id"]
    if not mask.any():
        return None
    return df.loc[mask].iloc[0]


def _lang_index(df: pd.DataFrame, *, platform: str, kind: str = "csv") -> dict[str, tuple[str, int]]:
    """comment_id -> (language, is_mixed) from raw columns."""
    plat = platform.lower()
    out: dict[str, tuple[str, int]] = {}
    if kind == "clean":
        sub = df[list({"comment_id", "language", "is_mixed"} & set(df.columns))].drop_duplicates("comment_id")
        for _, row in sub.iterrows():
            cid = normalize_comment_id(row.get("comment_id"))
            lang = row.get("language")
            if not cid or pd.isna(lang) or not str(lang).strip():
                continue
            mixed = row.get("is_mixed")
            try:
                mixed_i = int(mixed) if pd.notna(mixed) else 0
            except (TypeError, ValueError):
                mixed_i = 0
            out[cid] = (str(lang).strip().lower(), mixed_i)
        return out
    if plat == "douyin":
        for _, row in df.iterrows():
            for level, cid_fn in ((1, _douyin_l1_id), (2, _douyin_l2_id)):
                cid = cid_fn(row)
                if not cid:
                    continue
                lang_col = L1_LANG if level == 1 else L2_LANG
                mix_col = L1_MIXED if level == 1 else L2_MIXED
                lang = row.get(lang_col)
                if pd.isna(lang) or not str(lang).strip():
                    continue
                mixed = row.get(mix_col)
                try:
                    mixed_i = int(mixed) if pd.notna(mixed) else 0
                except (TypeError, ValueError):
                    mixed_i = 0
                out[cid] = (str(lang).strip().lower(), mixed_i)
        return out
    for id_col, lang_col, mix_col in (
        ("一级评论id", L1_LANG, L1_MIXED),
        ("二级评论id", L2_LANG, L2_MIXED),
    ):
        if id_col not in df.columns:
            continue
        for _, row in df[[id_col, lang_col, mix_col]].drop_duplicates(id_col).iterrows():
            cid = row[id_col]
            if pd.isna(cid):
                continue
            lang = row.get(lang_col)
            if pd.isna(lang) or not str(lang).strip():
                continue
            mixed = row.get(mix_col)
            try:
                mixed_i = int(mixed) if pd.notna(mixed) else 0
            except (TypeError, ValueError):
                mixed_i = 0
            out[str(cid).strip()] = (str(lang).strip().lower(), mixed_i)
    return out


def _lang_from_raw(df: pd.DataFrame, rec: dict[str, Any], *, platform: str) -> tuple[str, int] | None:
    row = _row_for_rec(df, rec, platform=platform)
    if row is None:
        return None
    lang_col = L1_LANG if rec["level"] == 1 else L2_LANG
    mix_col = L1_MIXED if rec["level"] == 1 else L2_MIXED
    lang = row.get(lang_col)
    if pd.isna(lang) or not str(lang).strip():
        return None
    mixed = row.get(mix_col)
    try:
        mixed_i = int(mixed) if pd.notna(mixed) else 0
    except (TypeError, ValueError):
        mixed_i = 0
    return str(lang).strip().lower(), mixed_i


def _already_annotated(df: pd.DataFrame, rec: dict[str, Any], *, platform: str) -> bool:
    """Skip if raw row already has English for this comment."""
    plat = platform.lower()
    if plat == "douyin":
        for _, row in df.iterrows():
            if rec["level"] == 1 and _douyin_l1_id(row) == rec["comment_id"]:
                en = row.get(L1_EN)
                return valid_en(en)
            if rec["level"] == 2 and _douyin_l2_id(row) == rec["comment_id"]:
                en = row.get(L2_EN)
                return valid_en(en)
        return False
    id_col = "一级评论id" if rec["level"] == 1 else "二级评论id"
    en_col = L1_EN if rec["level"] == 1 else L2_EN
    mask = df[id_col].astype(str).str.strip() == rec["comment_id"]
    if not mask.any():
        return False
    en_vals = df.loc[mask, en_col]
    return en_vals.map(valid_en).any()


def apply_annotations(
    df: pd.DataFrame,
    annotations: dict[str, dict[str, Any]],
    *,
    platform: str,
    kind: str = "csv",
) -> pd.DataFrame:
    if kind == "clean":
        df = _ensure_clean_lang_cols(df.copy())
        for idx, row in df.iterrows():
            cid = normalize_comment_id(row.get("comment_id"))
            if not cid or cid not in annotations:
                continue
            a = annotations[cid]
            df.at[idx, "language"] = a.get("language", "")
            df.at[idx, "is_mixed"] = int(a.get("is_mixed", 0))
            df.at[idx, "content_en"] = a.get("content_en", "")
        return df

    df = _ensure_lang_cols(df.copy())
    plat = platform.lower()

    if plat == "douyin":
        for idx, row in df.iterrows():
            cid1 = _douyin_l1_id(row)
            if cid1 and cid1 in annotations:
                a = annotations[cid1]
                df.at[idx, L1_LANG] = a.get("language", "")
                df.at[idx, L1_MIXED] = int(a.get("is_mixed", 0))
                df.at[idx, L1_EN] = a.get("content_en", "")
            cid2 = _douyin_l2_id(row)
            if cid2 and cid2 in annotations:
                a = annotations[cid2]
                df.at[idx, L2_LANG] = a.get("language", "")
                df.at[idx, L2_MIXED] = int(a.get("is_mixed", 0))
                df.at[idx, L2_EN] = a.get("content_en", "")
        return df

    for idx, row in df.iterrows():
        cid1 = row.get("一级评论id")
        if pd.notna(cid1):
            sc = str(cid1).strip()
            if sc in annotations:
                a = annotations[sc]
                df.at[idx, L1_LANG] = a.get("language", "")
                df.at[idx, L1_MIXED] = int(a.get("is_mixed", 0))
                df.at[idx, L1_EN] = a.get("content_en", "")
        cid2 = row.get("二级评论id")
        if pd.notna(cid2):
            sc2 = str(cid2).strip()
            if sc2 in annotations:
                a = annotations[sc2]
                df.at[idx, L2_LANG] = a.get("language", "")
                df.at[idx, L2_MIXED] = int(a.get("is_mixed", 0))
                df.at[idx, L2_EN] = a.get("content_en", "")
    return df


def load_raw(job: dict) -> tuple[pd.DataFrame, dict[str, pd.DataFrame] | None]:
    path = Path(job["path"])
    kind = _job_kind(job)
    if kind == "clean":
        return _ensure_clean_lang_cols(pd.read_csv(path, dtype=str, low_memory=False)), None
    if kind == "xlsx":
        return read_raw_xlsx(path)
    if kind == "douyin":
        return pd.read_csv(path, encoding="utf-8-sig", low_memory=False), None
    return read_raw_csv(path), None


def _merge_lang_into_sibling_csvs(clean_dir: Path, merge_map: pd.DataFrame) -> None:
    lang_cols = list(CLEAN_LANG_COLS)
    for fname in (
        "clean_l1_comments_filtered.csv",
        "clean_l2_comments_filtered.csv",
        "clean_comments_unified_before_filter.csv",
        "clean_l1_comments.csv",
        "clean_l2_comments.csv",
        "shared_analyzable_corpus.csv",
    ):
        p = clean_dir / fname
        if not p.is_file():
            continue
        sub = pd.read_csv(p, dtype=str, low_memory=False)
        sub = sub.drop(columns=[c for c in lang_cols if c in sub.columns], errors="ignore")
        sub = sub.merge(merge_map, on="comment_id", how="left")
        sub.to_csv(p, index=False, encoding="utf-8-sig")


def save_raw(job: dict, main: pd.DataFrame, extra: dict[str, pd.DataFrame] | None) -> None:
    path = Path(job["path"])
    kind = _job_kind(job)
    if kind == "clean":
        main = _ensure_clean_lang_cols(main)
        main.to_csv(path, index=False, encoding="utf-8-sig")
        merge_map = main[["comment_id", *CLEAN_LANG_COLS]].drop_duplicates(subset=["comment_id"])
        _merge_lang_into_sibling_csvs(path.parent, merge_map)
        return
    if kind == "xlsx":
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            main.to_excel(w, sheet_name="小红书帖子数据", index=False)
            if extra and "导出计数_帖子id" in extra:
                extra["导出计数_帖子id"].to_excel(w, sheet_name="导出计数_帖子id", index=False)
    elif job["kind"] == "csv":
        save_raw_csv(path, main)
    else:
        save_raw_csv(path, main)


def repair_raw_ids(job: dict) -> dict[str, Any] | None:
    clean_path = job.get("clean_lookup")
    if not clean_path or job.get("kind") != "csv":
        return None
    clean_path = Path(clean_path)
    if not clean_path.is_file():
        print(f"  [repair] skip: clean lookup missing {clean_path}")
        return None
    main, extra = load_raw(job)
    main, stats = repair_tiktok_ids_from_clean(main, clean_path)
    save_raw(job, main, extra)
    print(
        "  [repair] ids restored:"
        f" l1={stats['l1_fixed']} l2={stats['l2_fixed']}"
        f" miss l1={stats['l1_miss']} l2={stats['l2_miss']}"
    )
    return stats


def _existing_en_index(
    df: pd.DataFrame, *, platform: str, kind: str = "csv"
) -> dict[str, dict[str, Any]]:
    """comment_id -> annotation dict for rows that already have 英文."""
    plat = platform.lower()
    out: dict[str, dict[str, Any]] = {}
    if kind == "clean":
        cols = [c for c in ("comment_id", "language", "is_mixed", "content_en") if c in df.columns]
        sub = df[cols].drop_duplicates(subset=["comment_id"])
        for _, row in sub.iterrows():
            cid = normalize_comment_id(row.get("comment_id"))
            en = row.get("content_en")
            if not cid or not valid_en(en):
                continue
            mixed = row.get("is_mixed")
            try:
                mixed_i = int(mixed) if pd.notna(mixed) else 0
            except (TypeError, ValueError):
                mixed_i = 0
            out[cid] = {
                "language": row.get("language", ""),
                "is_mixed": mixed_i,
                "content_en": en,
                "status": "ok",
            }
        return out
    if plat == "douyin":
        for _, row in df.iterrows():
            for level, cid_fn in ((1, _douyin_l1_id), (2, _douyin_l2_id)):
                cid = cid_fn(row)
                if not cid:
                    continue
                en_col = L1_EN if level == 1 else L2_EN
                lang_col = L1_LANG if level == 1 else L2_LANG
                mix_col = L1_MIXED if level == 1 else L2_MIXED
                en = row.get(en_col)
                if not valid_en(en):
                    continue
                mixed = row.get(mix_col)
                try:
                    mixed_i = int(mixed) if pd.notna(mixed) else 0
                except (TypeError, ValueError):
                    mixed_i = 0
                out[cid] = {
                    "language": row.get(lang_col, ""),
                    "is_mixed": mixed_i,
                    "content_en": en,
                    "status": "ok",
                }
        return out
    for id_col, en_col, lang_col, mix_col in (
        ("一级评论id", L1_EN, L1_LANG, L1_MIXED),
        ("二级评论id", L2_EN, L2_LANG, L2_MIXED),
    ):
        if id_col not in df.columns or en_col not in df.columns:
            continue
        cols = [c for c in (id_col, en_col, lang_col, mix_col) if c in df.columns]
        sub = df[cols].drop_duplicates(subset=[id_col])
        for _, row in sub.iterrows():
            cid = row[id_col]
            en = row.get(en_col)
            if pd.isna(cid) or not valid_en(en):
                continue
            mixed = row.get(mix_col) if mix_col in row.index else 0
            try:
                mixed_i = int(mixed) if pd.notna(mixed) else 0
            except (TypeError, ValueError):
                mixed_i = 0
            out[str(cid).strip()] = {
                "language": row.get(lang_col, ""),
                "is_mixed": mixed_i,
                "content_en": en,
                "status": "ok",
            }
    return out


def _done_en_ids(df: pd.DataFrame, *, platform: str) -> set[str]:
    """Comment ids that already have non-empty 英文 in raw."""
    plat = platform.lower()
    done: set[str] = set()
    if plat == "douyin":
        for _, row in df.iterrows():
            cid1 = _douyin_l1_id(row)
            en1 = row.get(L1_EN)
            if cid1 and valid_en(en1):
                done.add(cid1)
            cid2 = _douyin_l2_id(row)
            en2 = row.get(L2_EN)
            if cid2 and valid_en(en2):
                done.add(cid2)
        return done
    for id_col, en_col in (("一级评论id", L1_EN), ("二级评论id", L2_EN)):
        if id_col not in df.columns or en_col not in df.columns:
            continue
        sub = df[[id_col, en_col]].dropna(subset=[id_col])
        sub = sub[sub[en_col].map(valid_en)]
        done.update(sub[id_col].astype(str).str.strip())
    return done


def scrub_placeholder_en(main: pd.DataFrame, *, kind: str = "csv") -> pd.DataFrame:
    """Turn bogus placeholder 英文 (e.g. literal '<NA>') into empty."""
    if kind == "clean":
        main = _ensure_clean_lang_cols(main.copy())
        for idx, val in main["content_en"].items():
            if not valid_en(val):
                main.at[idx, "content_en"] = pd.NA
        return main
    main = _ensure_lang_cols(main.copy())
    for en_col in (L1_EN, L2_EN):
        if en_col not in main.columns:
            continue
        for idx, val in main[en_col].items():
            if not valid_en(val):
                main.at[idx, en_col] = pd.NA
    return main


def clear_retranslations(main: pd.DataFrame, *, kind: str = "csv") -> pd.DataFrame:
    """Clear 英文 for rows that need LLM translation; keep copy for pure en."""
    if kind == "clean":
        main = _ensure_clean_lang_cols(main.copy())
        for idx, row in main.iterrows():
            lang = row.get("language")
            if pd.isna(lang) or not str(lang).strip():
                continue
            try:
                mixed = int(row.get("is_mixed", 0) or 0)
            except (TypeError, ValueError):
                mixed = 0
            if needs_translation(str(lang).strip().lower(), mixed):
                main.at[idx, "content_en"] = pd.NA
        return main
    main = _ensure_lang_cols(main.copy())
    for lang_col, mix_col, en_col in (
        (L1_LANG, L1_MIXED, L1_EN),
        (L2_LANG, L2_MIXED, L2_EN),
    ):
        if lang_col not in main.columns:
            continue
        for idx, row in main.iterrows():
            lang = row.get(lang_col)
            if pd.isna(lang) or not str(lang).strip():
                continue
            try:
                mixed = int(row.get(mix_col, 0) or 0)
            except (TypeError, ValueError):
                mixed = 0
            if needs_translation(str(lang).strip().lower(), mixed):
                main.at[idx, en_col] = pd.NA
    return main


def run_job(
    job: dict,
    *,
    cfg: dict[str, Any],
    detect_only: bool = False,
    force_retranslate: bool = False,
    limit: int | None = None,
    workers: int | None = None,
    checkpoint_dir: Path,
) -> dict[str, Any]:
    platform, batch = job["platform"], job["batch"]
    kind = _job_kind(job)
    print(f"[comment_lang] {platform}/{batch} <- {job['path']}")

    if job.get("clean_lookup") and kind == "csv":
        repair_raw_ids(job)

    main, extra = load_raw(job)
    if kind == "clean":
        main = scrub_placeholder_en(_ensure_clean_lang_cols(main), kind=kind)
    else:
        main = scrub_placeholder_en(_ensure_lang_cols(main), kind=kind)
    ckpt = checkpoint_dir / f"{platform}_{batch}.jsonl"
    if force_retranslate and not detect_only:
        main = clear_retranslations(main, kind=kind)
        if ckpt.is_file():
            ckpt.unlink()
        print("  force-retranslate: cleared prior LLM 英文 + checkpoint")
    comments = extract_unique_comments(main, platform=platform, kind=kind)
    print(f"  unique comments: {len(comments)}")

    existing_en = _existing_en_index(main, platform=platform, kind=kind)
    done_en = set(existing_en.keys())
    to_process = [c for c in comments if c["comment_id"] not in done_en]
    print(f"  pending translate: {len(to_process)} (already have EN: {len(comments) - len(to_process)})")

    lang_idx = _lang_index(main, platform=platform, kind=kind)
    records: list[dict[str, Any]] = []
    for rec in to_process:
        existing = lang_idx.get(rec["comment_id"])
        if existing:
            lang, mixed = existing
        else:
            lang, mixed = detect_language(rec["content"], cfg)
        records.append({
            "comment_id": rec["comment_id"],
            "content": rec["content"],
            "language": lang,
            "is_mixed": mixed,
            "level": rec["level"],
        })

    if limit is not None:
        records = records[:limit]

    annotations: dict[str, dict[str, Any]] = dict(existing_en)

    if detect_only:
        for r in records:
            content_en = r["content"] if not needs_translation(r["language"], r["is_mixed"]) else ""
            annotations[r["comment_id"]] = {
                "language": r["language"],
                "is_mixed": r["is_mixed"],
                "content_en": content_en,
                "status": "detect_only",
            }
    else:
        translated = translate_records(
            records, cfg=cfg, checkpoint_path=ckpt, limit=limit, workers=workers,
        )
        annotations.update(translated)

    main = apply_annotations(main, annotations, platform=platform, kind=kind)
    save_raw(job, main, extra)

    n_ok = sum(1 for a in annotations.values() if a.get("status") == "ok" or a.get("status") == "detect_only")
    n_fail = sum(1 for a in annotations.values() if a.get("status") == "fail")
    lang_counts = {}
    for a in annotations.values():
        lg = str(a.get("language", "und"))
        lang_counts[lg] = lang_counts.get(lg, 0) + 1

    summary = {
        "platform": platform,
        "batch": batch,
        "n_unique": len(comments),
        "n_annotated_this_run": len(records),
        "n_ok": n_ok,
        "n_fail": n_fail,
        "language_counts": lang_counts,
    }
    print(f"  done: annotated={len(records)} ok={n_ok} fail={n_fail}")
    return summary


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser(description="Raw 宽表评论语言标签 + 英译")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--platform", choices=["xhs", "tiktok", "douyin", "youtube"])
    ap.add_argument("--batch")
    ap.add_argument("--detect-only", action="store_true")
    ap.add_argument(
        "--force-retranslate",
        action="store_true",
        help="清空需译评论的 英文 列与 checkpoint，用当前 prompt 重跑",
    )
    ap.add_argument(
        "--purge-checkpoints",
        action="store_true",
        help="仅删除 checkpoint 中的 fail 行（保留 ok）",
    )
    ap.add_argument(
        "--repair-ids",
        action="store_true",
        help="从 clean 表恢复 TikTok 宽表中被 float 损坏的评论/用户 id",
    )
    ap.add_argument("--limit", type=int, default=None, help="仅处理前 N 条待标注评论（冒烟）")
    ap.add_argument(
        "--workers",
        type=int,
        default=None,
        help="并行 batch 数（默认读 config translation.max_workers）",
    )
    ap.add_argument("--config", type=Path, default=None)
    args = ap.parse_args()

    cfg = load_config(args.config or ROOT / "config" / "comment_lang.json")
    ckpt_dir = ROOT / "output" / "comment_lang"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    if args.purge_checkpoints:
        purge_jobs = JOBS if args.all else (
            [j for j in JOBS if j["platform"] == args.platform and j["batch"] == args.batch]
            if args.platform and args.batch else JOBS
        )
        for job in purge_jobs:
            ckpt = ckpt_dir / f"{job['platform']}_{job['batch']}.jsonl"
            n_ok, n_removed = purge_failed_checkpoint(ckpt)
            print(f"[purge] {job['platform']}/{job['batch']}: ok={n_ok} removed={n_removed}")
        return

    if args.repair_ids:
        repair_jobs = JOBS if args.all else (
            [j for j in JOBS if j["platform"] == args.platform and j["batch"] == args.batch]
            if args.platform and args.batch else [j for j in JOBS if j.get("clean_lookup")]
        )
        for job in repair_jobs:
            print(f"[repair] {job['platform']}/{job['batch']}")
            repair_raw_ids(job)
        if not args.platform and not args.all:
            return

    jobs = JOBS
    if not args.all:
        if not args.platform or not args.batch:
            ap.error("指定 --platform 与 --batch，或使用 --all")
        jobs = [j for j in JOBS if j["platform"] == args.platform and j["batch"] == args.batch]
        if not jobs:
            raise SystemExit(f"unknown job: {args.platform}/{args.batch}")

    summaries = []
    for job in jobs:
        summaries.append(run_job(
            job,
            cfg=cfg,
            detect_only=args.detect_only,
            force_retranslate=args.force_retranslate,
            limit=args.limit,
            workers=args.workers,
            checkpoint_dir=ckpt_dir,
        ))

    out = ROOT / "output" / "comment_lang" / "summary.json"
    out.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
