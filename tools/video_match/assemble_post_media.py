"""
Assemble post-level metadata CSV from clip reports + caption jsonl + ASR jsonl.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from phase1.preprocess import normalize_post_id
from tools.video_match.post_media_jobs import (
    JOBS,
    asr_jsonl,
    captions_jsonl,
    combined_post_media_csv,
    filter_jobs,
    post_media_csv,
)

CSV_COLUMNS = [
    "platform",
    "source_batch",
    "post_id",
    "url",
    "post_title",
    "post_text",
    "clip_path",
    "clip_status",
    "clip_bytes",
    "video_overview",
    "video_caption",
    "video_scene",
    "video_robots",
    "video_humans",
    "video_event",
    "video_anomaly",
    "caption_mode",
    "asr_text",
    "asr_has_speech",
    "asr_language",
    "asr_n_segments",
    "asr_model",
    "caption_status",
    "asr_status",
]


def load_jsonl_by_id(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        pid = str(rec.get("id", ""))
        if pid:
            out[pid] = rec
    return out


def _scalar(val) -> str:
    if val is None:
        return ""
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def load_post_meta(job: dict) -> pd.DataFrame:
    raw = Path(job["raw"])
    df = pd.read_csv(raw, low_memory=False, dtype={job["id_col"]: str, job["url_col"]: str})
    id_col = job["id_col"]
    url_col = job["url_col"]
    title_col = job.get("title_col")
    text_col = job["text_col"]

    cols = [id_col, url_col]
    if title_col and title_col in df.columns:
        cols.append(title_col)
    if text_col in df.columns and text_col not in cols:
        cols.append(text_col)

    posts = df[cols].copy()
    posts[id_col] = posts[id_col].map(normalize_post_id)
    posts = posts.dropna(subset=[id_col, url_col])
    posts = posts.drop_duplicates(id_col, keep="first")

    out = pd.DataFrame({
        "post_id": posts[id_col].astype(str),
        "url": posts[url_col].astype(str),
        "post_title": posts[title_col].fillna("").astype(str) if title_col and title_col in posts.columns else "",
        "post_text": posts[text_col].fillna("").astype(str) if text_col in posts.columns else "",
    })
    return out


def load_clip_report(job: dict) -> pd.DataFrame:
    report = Path(job["clips"]) / "download_report.csv"
    if report.is_file():
        rep = pd.read_csv(report, dtype={"id": str})
        rep = rep.rename(columns={"id": "post_id", "status": "clip_status", "bytes": "clip_bytes"})
        rep["post_id"] = rep["post_id"].map(normalize_post_id)
        rep["clip_path"] = rep["post_id"].map(
            lambda pid: str(Path(job["clips"]) / f"{pid}.mp4")
        )
        return rep[["post_id", "clip_path", "clip_status", "clip_bytes"]]

    urls = Path(job["clips"]) / "urls.csv"
    if urls.is_file():
        u = pd.read_csv(urls, dtype={"帖子id": str})
        u = u.rename(columns={"帖子id": "post_id"})
        u["post_id"] = u["post_id"].map(normalize_post_id)
        u["clip_path"] = u["post_id"].map(
            lambda pid: str(Path(job["clips"]) / f"{pid}.mp4")
        )
        u["clip_status"] = u["clip_path"].map(
            lambda p: "ok" if Path(p).is_file() and Path(p).stat().st_size > 0 else "fail"
        )
        u["clip_bytes"] = u["clip_path"].map(
            lambda p: Path(p).stat().st_size if Path(p).is_file() else 0
        )
        return u[["post_id", "clip_path", "clip_status", "clip_bytes"]]

    return pd.DataFrame(columns=["post_id", "clip_path", "clip_status", "clip_bytes"])


def caption_status(row: pd.Series) -> str:
    if row.get("clip_status") != "ok":
        return "skipped_no_clip"
    if row.get("video_overview") or row.get("video_caption"):
        return "ok"
    return "fail"


def asr_status(row: pd.Series) -> str:
    if row.get("clip_status") != "ok":
        return "skipped_no_clip"
    err = str(row.get("_asr_error", "") or "")
    if err:
        return "fail"
    if int(row.get("asr_has_speech", 0) or 0) == 1:
        return "ok"
    return "empty_speech"


def assemble_job(job: dict) -> pd.DataFrame:
    meta = load_post_meta(job)
    clips = load_clip_report(job)
    caps = load_jsonl_by_id(captions_jsonl(job))
    asrs = load_jsonl_by_id(asr_jsonl(job))

    df = meta.merge(clips, on="post_id", how="left")
    df["platform"] = job["platform"]
    df["source_batch"] = job["batch"]

    cap_rows = []
    for pid, rec in caps.items():
        cap_rows.append({
            "post_id": pid,
            "video_overview": _scalar(rec.get("overview")),
            "video_caption": _scalar(rec.get("caption")),
            "video_scene": _scalar(rec.get("scene")),
            "video_robots": _scalar(rec.get("robots")),
            "video_humans": _scalar(rec.get("humans")),
            "video_event": _scalar(rec.get("event")),
            "video_anomaly": _scalar(rec.get("anomaly")),
            "caption_mode": _scalar(rec.get("mode")),
        })
    if cap_rows:
        df = df.merge(pd.DataFrame(cap_rows), on="post_id", how="left")

    asr_rows = []
    for pid, rec in asrs.items():
        segs = rec.get("segments") or []
        asr_rows.append({
            "post_id": pid,
            "asr_text": _scalar(rec.get("asr_text")),
            "asr_has_speech": int(rec.get("asr_has_speech", 0) or 0),
            "asr_language": _scalar(rec.get("language")),
            "asr_n_segments": len(segs),
            "asr_model": _scalar(rec.get("model")),
            "_asr_error": _scalar(rec.get("error")),
        })
    if asr_rows:
        df = df.merge(pd.DataFrame(asr_rows), on="post_id", how="left")

    for col in CSV_COLUMNS:
        if col not in df.columns:
            if col in ("asr_has_speech", "asr_n_segments", "clip_bytes"):
                df[col] = 0
            elif col in ("caption_status", "asr_status"):
                df[col] = ""
            else:
                df[col] = ""

    df["clip_status"] = df["clip_status"].fillna("fail")
    df["clip_bytes"] = pd.to_numeric(df["clip_bytes"], errors="coerce").fillna(0).astype(int)
    df["asr_has_speech"] = pd.to_numeric(df["asr_has_speech"], errors="coerce").fillna(0).astype(int)
    df["asr_n_segments"] = pd.to_numeric(df["asr_n_segments"], errors="coerce").fillna(0).astype(int)

    df["caption_status"] = df.apply(caption_status, axis=1)
    df["asr_status"] = df.apply(asr_status, axis=1)

    if "_asr_error" in df.columns:
        df = df.drop(columns=["_asr_error"])

    return df[CSV_COLUMNS]


def run(jobs: list[dict] | None = None, write_combined: bool = True) -> pd.DataFrame:
    jobs = jobs or JOBS
    parts: list[pd.DataFrame] = []
    for job in jobs:
        df = assemble_job(job)
        out_path = post_media_csv(job)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"[assemble] {job['platform']}/{job['batch']} -> {out_path} ({len(df)} rows)")
        parts.append(df)

    combined = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=CSV_COLUMNS)
    if write_combined:
        combined_path = combined_post_media_csv()
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(combined_path, index=False, encoding="utf-8-sig")
        print(f"[assemble] combined -> {combined_path} ({len(combined)} rows)")
    return combined


def main() -> None:
    p = argparse.ArgumentParser(description="Assemble post_media.csv from caption + ASR jsonl")
    p.add_argument("--platform", default="")
    p.add_argument("--batch", default="")
    p.add_argument("--no-combined", action="store_true")
    a = p.parse_args()
    jobs = filter_jobs(a.platform or None, a.batch or None) if (a.platform or a.batch) else JOBS
    run(jobs, write_combined=not a.no_combined)


if __name__ == "__main__":
    main()
