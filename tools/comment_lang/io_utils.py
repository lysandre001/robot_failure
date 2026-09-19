"""Raw wide-table IO with stable comment/post id strings."""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import pandas as pd

from phase1.preprocess import normalize_text

ID_COLUMNS = ("帖子id", "一级评论id", "二级评论id")
STRING_ID_COLUMNS = ID_COLUMNS + ("用户id", "一级评论用户id", "二级评论用户id")


def normalize_comment_id(cid) -> str | None:
    if cid is None or (isinstance(cid, float) and pd.isna(cid)):
        return None
    if isinstance(cid, str):
        s = cid.strip()
        if not s or s.lower() == "nan":
            return None
        if "e+" in s.lower() or "e-" in s.lower():
            return None
        return s
    if isinstance(cid, float):
        if cid != cid:
            return None
        as_int = int(cid)
        if float(as_int) != cid:
            return None
        return str(as_int)
    if isinstance(cid, int):
        return str(cid)
    s = str(cid).strip()
    return s or None


def _coerce_id_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ID_COLUMNS:
        if col not in out.columns:
            continue
        out[col] = out[col].map(normalize_comment_id)
    return out


def read_raw_csv(path: Path) -> pd.DataFrame:
    """Read CSV with all fields as strings (avoids snowflake id float corruption)."""
    raw = path.read_bytes().replace(b"\x00", b"")
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = [{k: (v if v != "" else pd.NA) for k, v in row.items()} for row in reader]
    df = pd.DataFrame(rows)
    return _coerce_id_columns(df)


def read_raw_xlsx(path: Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    main = pd.read_excel(
        path,
        sheet_name="小红书帖子数据",
        dtype={c: str for c in ID_COLUMNS},
    )
    counts = pd.read_excel(path, sheet_name="导出计数_帖子id")
    return _coerce_id_columns(main), {"导出计数_帖子id": counts}


_EMPTY_TOKENS = frozenset({"", "nan", "none", "<na>", "null"})


def _cell_str(val) -> str:
    if val is None or val is pd.NA or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.lower() in _EMPTY_TOKENS:
        return ""
    return s


def valid_en(val) -> bool:
    return bool(_cell_str(val))


def save_raw_csv(path: Path, df: pd.DataFrame) -> None:
    """Write CSV without float-corrupting snowflake ids."""
    out = _coerce_id_columns(df.copy())
    for col in STRING_ID_COLUMNS:
        if col in out.columns:
            out[col] = out[col].map(_cell_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out.columns), extrasaction="ignore")
        writer.writeheader()
        for _, row in out.iterrows():
            rec = {c: _cell_str(row[c]) if c in STRING_ID_COLUMNS else row[c] for c in out.columns}
            writer.writerow(rec)


def _repair_key(post_id, content, comment_time) -> tuple[str, str, str]:
    return (
        _cell_str(post_id),
        normalize_text(content),
        _cell_str(comment_time),
    )


def _user_id_by_comment(clean_path: Path) -> dict[str, str]:
    """Public clean may omit user_id; read sidecar when present (local QC only)."""
    sidecar = clean_path.parent / "comment_pii_sidecar.csv"
    if not sidecar.is_file():
        return {}
    pii = pd.read_csv(sidecar, dtype=str)
    if "comment_id" not in pii.columns or "user_id" not in pii.columns:
        return {}
    return {
        _cell_str(r["comment_id"]): _cell_str(r["user_id"])
        for _, r in pii.iterrows()
        if _cell_str(r["comment_id"])
    }


def _build_clean_lookup(clean_path: Path) -> tuple[dict[tuple[str, str, str], list[dict[str, str]]], dict]:
    clean = pd.read_csv(clean_path, dtype=str)
    uid_map = _user_id_by_comment(clean_path)
    lookups: dict[int, dict[tuple[str, str, str], list[dict[str, str]]]] = {1: {}, 2: {}}
    stats: dict[str, Any] = {"l1_keys": 0, "l2_keys": 0, "l1_dup_keys": 0, "l2_dup_keys": 0}
    for level in (1, 2):
        sub = clean[clean["comment_level"] == str(level)]
        lk = lookups[level]
        for _, row in sub.iterrows():
            key = _repair_key(row["帖子id"], row["content"], row.get("comment_time", ""))
            cid = _cell_str(row["comment_id"])
            uid = _cell_str(row.get("user_id", "")) or uid_map.get(cid, "")
            entry = {"comment_id": cid, "user_id": uid}
            if key in lk:
                lk[key].append(entry)
                stats[f"l{level}_dup_keys"] += 1
            else:
                lk[key] = [entry]
                stats[f"l{level}_keys"] += 1
    return lookups[1], lookups[2], stats


def repair_tiktok_ids_from_clean(df: pd.DataFrame, clean_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Restore comment/user ids corrupted by pandas float round-trip."""
    l1_lookup, l2_lookup, lk_stats = _build_clean_lookup(clean_path)
    out = df.copy()
    use_counters: dict[tuple[int, tuple[str, str, str]], int] = {}
    stats: dict[str, Any] = {
        **lk_stats,
        "l1_fixed": 0,
        "l2_fixed": 0,
        "l1_user_fixed": 0,
        "l2_user_fixed": 0,
        "l1_miss": 0,
        "l2_miss": 0,
    }
    specs = (
        (1, "一级评论id", "一级评论内容", "一级评论时间", "一级评论用户id", l1_lookup),
        (2, "二级评论id", "二级评论内容", "二级评论时间", "二级评论用户id", l2_lookup),
    )
    for idx, row in out.iterrows():
        for level, id_col, content_col, time_col, user_col, lookup in specs:
            content = row.get(content_col)
            if content is None or (isinstance(content, float) and pd.isna(content)):
                continue
            if not str(content).strip():
                continue
            key = _repair_key(row.get("帖子id"), content, row.get(time_col))
            bucket = lookup.get(key)
            if not bucket:
                stats[f"l{level}_miss"] += 1
                continue
            counter_key = (level, key)
            pos = use_counters.get(counter_key, 0)
            use_counters[counter_key] = pos + 1
            pick = bucket[min(pos, len(bucket) - 1)]
            cur_id = normalize_comment_id(row.get(id_col))
            if cur_id != pick["comment_id"]:
                out.at[idx, id_col] = pick["comment_id"]
                stats[f"l{level}_fixed"] += 1
            if pick["user_id"] and _cell_str(row.get(user_col)) != pick["user_id"]:
                out.at[idx, user_col] = pick["user_id"]
                stats[f"l{level}_user_fixed"] += 1
    return out, stats
