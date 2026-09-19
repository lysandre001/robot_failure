"""Public-observation de-identification: PII sidecar + publication-safe clean tables."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Never appear in clean/shared/demo/analysis outputs (IRB 8a).
PII_COMMENT_COLUMNS = ("user_id", "location")

SIDECAR_FILENAME = "comment_pii_sidecar.csv"
SIDECAR_COLUMNS = ("comment_id", "user_id", "location", "platform", "source_batch")


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
