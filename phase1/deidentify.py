"""Public-observation de-identification: PII sidecar + publication-safe clean tables."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from phase1.preprocess import normalize_text

# Never appear in clean/shared/demo/analysis outputs (IRB 8a).
PII_COMMENT_COLUMNS = ("user_id", "location")

SIDECAR_FILENAME = "comment_pii_sidecar.csv"
DEIDENTIFY_REPORT_FILENAME = "comment_deidentify_report.json"
SIDECAR_COLUMNS = ("comment_id", "user_id", "location", "platform", "source_batch")

_EMPTY_UID = frozenset({"", "nan", "none", "<na>", "null"})


def _norm_user_id(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    return "" if s.lower() in _EMPTY_UID else s


def dedupe_user_identical_content(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Remove 刷屏：同一 user_id + 规范化后 identical content，保留 comment_id 字典序第一条。
    无 user_id 的行不参与此规则（仍保留）。
    """
    if df.empty or "content" not in df.columns:
        return df, {
            "removed_user_identical_content": 0,
            "n_rows_before": 0,
            "n_rows_after": 0,
            "n_distinct_user_id": 0,
        }

    work = df.copy()
    work["_content_norm"] = work["content"].map(normalize_text)
    if "user_id" in work.columns:
        work["_uid"] = work["user_id"].map(_norm_user_id)
    else:
        work["_uid"] = ""
    eligible = work["_uid"].astype(str).str.len() > 0

    dup_mask = pd.Series(False, index=work.index)
    sub = work.loc[eligible].sort_values("comment_id", kind="mergesort")
    if len(sub):
        is_dup = sub.duplicated(subset=["_uid", "_content_norm"], keep="first")
        dup_mask.loc[sub.index[is_dup]] = True

    kept = work.loc[~dup_mask].drop(columns=["_content_norm", "_uid"], errors="ignore")
    uid_kept = work.loc[~dup_mask & eligible, "_uid"]
    stats: dict[str, Any] = {
        "removed_user_identical_content": int(dup_mask.sum()),
        "n_rows_before": int(len(df)),
        "n_rows_after": int(len(kept)),
        "n_distinct_user_id": int(uid_kept.nunique()) if len(uid_kept) else 0,
        "notes": "Distinct users counted on final clean (non-empty platform user_id). "
        "Dedup key: (user_id, normalize_text(content)); keep first comment_id.",
    }
    return kept, stats


def count_distinct_users(df: pd.DataFrame) -> int:
    if "user_id" not in df.columns or df.empty:
        return 0
    uids = df["user_id"].map(_norm_user_id)
    uids = uids[uids.str.len() > 0]
    return int(uids.nunique()) if len(uids) else 0


def extract_pii_sidecar(df: pd.DataFrame) -> pd.DataFrame:
    """One row per comment_id; for local QC/dedup only — not for publication."""
    if "comment_id" not in df.columns:
        return pd.DataFrame(columns=list(SIDECAR_COLUMNS))
    cols = [c for c in SIDECAR_COLUMNS if c in df.columns]
    out = df[cols].drop_duplicates(subset=["comment_id"], keep="first").copy()
    for c in SIDECAR_COLUMNS:
        if c not in out.columns:
            out[c] = ""
    return out[list(SIDECAR_COLUMNS)]


def drop_pii_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in PII_COMMENT_COLUMNS:
        if c in out.columns:
            out = out.drop(columns=[c])
    return out


def deidentify_for_public(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (public_df, pii_sidecar)."""
    sidecar = extract_pii_sidecar(df)
    public = drop_pii_columns(df)
    return public, sidecar


def write_pii_sidecar(sidecar: pd.DataFrame, out_dir: Path) -> Path | None:
    if sidecar.empty:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / SIDECAR_FILENAME
    sidecar.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def write_deidentify_report(out_dir: Path, report: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / DEIDENTIFY_REPORT_FILENAME
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
