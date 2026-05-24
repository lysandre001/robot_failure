"""小红书宽表导入与两批合并（库函数；CLI 见 tools/）。"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from phase1.config import ROOT
from phase1.preprocess import normalize_post_id

EXPECTED_COLS = 30
POST_ID_RE = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)


def is_valid_post_id(pid) -> bool:
    key = normalize_post_id(pid)
    return bool(key and POST_ID_RE.match(key))


def sanitize_xhs_wide_csv(
    input_csv: Path,
    *,
    output_csv: Path | None = None,
    qc_md: Path | None = None,
    expected_cols: int = EXPECTED_COLS,
) -> tuple[pd.DataFrame, dict]:
    """读字节流去 NUL，UTF-8 容错解码，仅保留字段数正确的行。"""
    raw_bytes = input_csv.read_bytes()
    n_nul = raw_bytes.count(b"\x00")
    cleaned = raw_bytes.replace(b"\x00", b"")
    text = cleaned.decode("utf-8-sig", errors="replace")

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError(f"空文件: {input_csv}")

    header = [h.strip().lstrip("\ufeff") for h in header]
    if len(header) != expected_cols:
        raise ValueError(f"表头列数 {len(header)} != 预期 {expected_cols}: {header[:5]}...")

    good_rows: list[list[str]] = []
    bad_rows: list[tuple[int, int, str]] = []
    pid_idx = header.index("帖子id") if "帖子id" in header else 0

    for line_no, row in enumerate(reader, start=2):
        if len(row) != expected_cols:
            bad_rows.append((line_no, len(row), "wrong_field_count"))
            continue
        if not is_valid_post_id(row[pid_idx]):
            bad_rows.append((line_no, len(row), "invalid_post_id"))
            continue
        good_rows.append(row)

    df = pd.DataFrame(good_rows, columns=header)
    if "帖子id" in df.columns:
        mask = df["帖子id"].map(is_valid_post_id)
        n_invalid_pid = int((~mask).sum())
        df = df.loc[mask].reset_index(drop=True)
    else:
        n_invalid_pid = 0

    qc: dict = {
        "input_csv": str(input_csv.resolve()),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_bytes_raw": len(raw_bytes),
        "n_nul_removed": n_nul,
        "n_header_cols": len(header),
        "n_good_rows": len(good_rows),
        "n_dropped_invalid_post_id_after_parse": n_invalid_pid,
        "n_output_rows": len(df),
        "n_skipped_rows": len(bad_rows),
        "n_unique_posts": int(df["帖子id"].nunique()) if "帖子id" in df.columns else None,
        "skipped_reasons": dict(Counter(r for _, _, r in bad_rows).most_common()),
        "skipped_field_counts": dict(Counter(n for _, n, _ in bad_rows if _ == "wrong_field_count").most_common(20)),
        "skipped_line_samples": [(ln, n, r) for ln, n, r in bad_rows[:30]],
    }

    out = output_csv or ROOT / "data" / "rawdata" / "xhs_batch2_wide_sanitized.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    qc["output_csv"] = str(out.resolve())

    qc_path = qc_md or ROOT / "data" / "rawdata" / "xhs_merge_qc.md"
    qc_path.parent.mkdir(parents=True, exist_ok=True)
    _write_qc_md(qc_path, qc, bad_rows)
    qc["qc_md"] = str(qc_path.resolve())

    return df, qc


def _write_qc_md(path: Path, qc: dict, bad_rows: list[tuple[int, int, str]]) -> None:
    lines = [
        "# 第二批 CSV 清洗 QC",
        "",
        f"- 生成时间：{qc['generated_at']}",
        f"- 输入：`{qc['input_csv']}`",
        f"- 输出：`{qc.get('output_csv', '')}`",
        "",
        "## 统计",
        "",
        "| 指标 | 值 |",
        "|------|-----|",
        f"| 原始字节 | {qc['n_bytes_raw']:,} |",
        f"| 移除 NUL | {qc['n_nul_removed']:,} |",
        f"| 保留行 | {qc['n_good_rows']:,} |",
        f"| 跳过行 | {qc['n_skipped_rows']:,} |",
        f"| 唯一帖子数 | {qc['n_unique_posts']} |",
        "",
        "## 跳过行字段数分布（前 20）",
        "",
    ]
    for reason, cnt in qc.get("skipped_reasons", {}).items():
        lines.append(f"- `{reason}`：{cnt} 行")
    for n_fields, cnt in qc.get("skipped_field_counts", {}).items():
        lines.append(f"- 字段数 `{n_fields}`：{cnt} 行")
    lines.extend(["", "## 跳过行样例（行号, 列数, 原因）", ""])
    for line_no, ncols, reason in bad_rows[:50]:
        lines.append(f"- L{line_no}: {ncols} 列, {reason}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def check_overlap_with_batch1(df: pd.DataFrame, batch1_xlsx: Path) -> dict:
    b1 = pd.read_excel(batch1_xlsx, sheet_name="小红书帖子数据", usecols=["帖子id"])
    ids_b1 = {normalize_post_id(x) for x in b1["帖子id"] if normalize_post_id(x)}
    ids_b2 = {normalize_post_id(x) for x in df["帖子id"] if normalize_post_id(x)}
    overlap = ids_b1 & ids_b2
    return {
        "batch1_posts": len(ids_b1),
        "batch2_posts": len(ids_b2),
        "overlap_count": len(overlap),
        "overlap_ids": sorted(overlap)[:20],
    }


def _align_columns(batch1: pd.DataFrame, batch2: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = list(batch1.columns)
    b2 = batch2.copy()
    for c in cols:
        if c not in b2.columns:
            b2[c] = pd.NA
    extra = [c for c in b2.columns if c not in cols]
    if extra:
        for c in extra:
            cols.append(c)
            batch1 = batch1.copy()
            batch1[c] = pd.NA
    return batch1[cols], b2[cols]


def build_counts_sheet(
    main: pd.DataFrame,
    counts_batch1: pd.DataFrame,
    *,
    batch2_unknown_category: str = "unknown",
) -> pd.DataFrame:
    counts = counts_batch1.copy()
    ren = {}
    if "类别" in counts.columns and "post_category" not in counts.columns:
        ren["类别"] = "post_category"
    if ren:
        counts = counts.rename(columns=ren)
    if "post_category" not in counts.columns:
        counts["post_category"] = batch2_unknown_category

    pid_col = "帖子id"
    ids_b1 = {normalize_post_id(x) for x in counts[pid_col] if normalize_post_id(x)}

    grp = main.groupby(pid_col, dropna=False).size().reset_index(name="计数")
    new_rows = []
    for _, row in grp.iterrows():
        key = normalize_post_id(row[pid_col])
        if key and key not in ids_b1:
            new_rows.append(
                {
                    pid_col: row[pid_col],
                    "计数": int(row["计数"]),
                    "post_category": batch2_unknown_category,
                }
            )
    if new_rows:
        extra = pd.DataFrame(new_rows)
        if "类别" in counts_batch1.columns:
            extra = extra.rename(columns={"post_category": "类别"})
            counts = counts.rename(columns={"post_category": "类别"})
        counts = pd.concat([counts, extra], ignore_index=True)
    return counts


def build_merged_xlsx(
    batch1_xlsx: Path,
    batch2_csv: Path,
    *,
    merged_xlsx: Path,
    posts_csv: Path,
) -> dict:
    main1 = pd.read_excel(batch1_xlsx, sheet_name="小红书帖子数据")
    counts1 = pd.read_excel(batch1_xlsx, sheet_name="导出计数_帖子id")
    main2 = pd.read_csv(batch2_csv, encoding="utf-8-sig")
    n2_before = len(main2)
    main2 = main2[main2["帖子id"].map(is_valid_post_id)].reset_index(drop=True)
    n2_dropped = n2_before - len(main2)

    main1, main2 = _align_columns(main1, main2)
    merged_main = pd.concat([main1, main2], ignore_index=True)
    merged_counts = build_counts_sheet(merged_main, counts1)

    merged_xlsx.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(merged_xlsx, engine="openpyxl") as writer:
        merged_main.to_excel(writer, sheet_name="小红书帖子数据", index=False)
        merged_counts.to_excel(writer, sheet_name="导出计数_帖子id", index=False)

    posts = merged_main.drop_duplicates(subset=["帖子id"], keep="first")[
        ["帖子id", "帖子链接", "帖子正文"]
    ]
    posts_csv.parent.mkdir(parents=True, exist_ok=True)
    posts.to_csv(posts_csv, index=False, encoding="utf-8-sig")

    ids_all = {normalize_post_id(x) for x in merged_main["帖子id"] if normalize_post_id(x)}
    return {
        "n_main_rows": len(merged_main),
        "n_batch1_rows": len(main1),
        "n_batch2_rows": len(main2),
        "n_batch2_dropped_invalid_post_id": n2_dropped,
        "n_unique_posts": len(ids_all),
        "n_posts_csv": len(posts),
        "merged_xlsx": str(merged_xlsx.resolve()),
        "posts_csv": str(posts_csv.resolve()),
    }
