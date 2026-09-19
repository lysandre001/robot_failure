"""跨平台宽表 CSV 入库（TikTok / 小红书 CSV；抖音见 douyin_io）。"""
from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from phase1.preprocess import normalize_post_id

EXPECTED_WIDE_COLS = 31


def is_valid_wide_post_id(pid) -> bool:
    key = normalize_post_id(pid)
    if not key:
        return False
    digits = key.replace("-", "")
    return digits.isdigit() and len(digits) >= 8


def read_csv_bytes(path: Path) -> str:
    raw = path.read_bytes()
    cleaned = raw.replace(b"\x00", b"")
    return cleaned.decode("utf-8-sig", errors="replace")


def sanitize_wide_csv(
    input_csv: Path,
    *,
    platform: str = "tiktok",
    output_csv: Path | None = None,
    qc_md: Path | None = None,
    expected_cols: int = EXPECTED_WIDE_COLS,
    validate_post_id: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """NUL 清理 + 列数校验 + 可选 post_id 校验。"""
    text = read_csv_bytes(input_csv)
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError(f"空文件: {input_csv}")

    header = [h.strip().lstrip("\ufeff") for h in header]
    if len(header) != expected_cols:
        raise ValueError(
            f"[{platform}] 表头列数 {len(header)} != 预期 {expected_cols}: {header[:8]}..."
        )

    pid_idx = header.index("帖子id") if "帖子id" in header else 0
    good_rows: list[list[str]] = []
    bad_rows: list[tuple[int, int, str]] = []

    for line_no, row in enumerate(reader, start=2):
        if len(row) != expected_cols:
            bad_rows.append((line_no, len(row), "wrong_field_count"))
            continue
        if validate_post_id and not is_valid_wide_post_id(row[pid_idx]):
            bad_rows.append((line_no, len(row), "invalid_post_id"))
            continue
        good_rows.append(row)

    df = pd.DataFrame(good_rows, columns=header)
    if "帖子id" in df.columns:
        df["帖子id"] = df["帖子id"].map(normalize_post_id)

    qc: dict = {
        "platform": platform,
        "input_csv": str(input_csv.resolve()),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_header_cols": len(header),
        "n_good_rows": len(good_rows),
        "n_skipped_rows": len(bad_rows),
        "n_unique_posts": int(df["帖子id"].nunique()) if "帖子id" in df.columns else None,
        "skipped_reasons": dict(Counter(r for _, _, r in bad_rows).most_common()),
    }

    if output_csv is not None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, index=False, encoding="utf-8-sig")
        qc["output_csv"] = str(output_csv.resolve())

    if qc_md is not None:
        lines = [
            f"# {platform} 宽表入库 QC",
            "",
            f"- 输入：`{input_csv}`",
            f"- 保留行：{qc['n_good_rows']:,}",
            f"- 跳过行：{qc['n_skipped_rows']:,}",
            f"- 唯一帖子：{qc['n_unique_posts']}",
            "",
        ]
        for reason, cnt in qc.get("skipped_reasons", {}).items():
            lines.append(f"- `{reason}`：{cnt}")
        qc_md.parent.mkdir(parents=True, exist_ok=True)
        qc_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        qc["qc_md"] = str(qc_md.resolve())

    return df, qc


def read_wide_csv(input_csv: Path, *, platform: str = "tiktok") -> pd.DataFrame:
    df, _ = sanitize_wide_csv(
        input_csv,
        platform=platform,
        validate_post_id=True,
    )
    return df
