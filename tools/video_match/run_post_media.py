"""
Orchestrator: dense caption + ASR + assemble post_media.csv

Usage:
  python -m tools.video_match.run_post_media
  python -m tools.video_match.run_post_media --platform xhs --batch merged
  python -m tools.video_match.run_post_media --skip-caption --skip-asr
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from phase1.config import ROOT
from tools.video_match.asr_audio import DEFAULT_MODEL as ASR_DEFAULT, run as run_asr
from tools.video_match.assemble_post_media import run as run_assemble
from tools.video_match.caption_video import run as run_caption
from tools.video_match.post_media_jobs import (
    JOBS,
    asr_jsonl,
    captions_jsonl,
    filter_jobs,
)


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


def seed_captions(job: dict) -> int:
    """Copy pre-existing caption jsonl ids into target so M3 skips them."""
    seed_path = job.get("seed_captions")
    if not seed_path:
        return 0
    seed_path = Path(seed_path)
    target = captions_jsonl(job)
    if not seed_path.is_file():
        return 0

    existing: set[str] = set()
    if target.is_file():
        for line in target.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line)["id"])
            except Exception:
                pass

    target.parent.mkdir(parents=True, exist_ok=True)
    added = 0
    with target.open("a", encoding="utf-8") as out_f:
        for line in seed_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            pid = str(rec.get("id", ""))
            if not pid or pid in existing:
                continue
            out_f.write(line.strip() + "\n")
            existing.add(pid)
            added += 1
    if added:
        print(f"[seed] {seed_path.name} -> {target.name}: +{added} ids")
    return added


def run_job(
    job: dict,
    *,
    skip_caption: bool = False,
    skip_asr: bool = False,
    skip_assemble: bool = False,
    caption_model: str | None = None,
    asr_model: str | None = None,
    legacy_caption: bool = False,
) -> None:
    clips = Path(job["clips"])
    cap_out = captions_jsonl(job)
    asr_out = asr_jsonl(job)

    print(f"\n=== {job['platform']}/{job['batch']} clips={clips} ===")

    if not skip_caption:
        seed_captions(job)
        if not clips.is_dir() or not any(clips.glob("*.mp4")):
            print(f"[caption] skip: no mp4 in {clips}")
        else:
            kwargs = {"legacy": legacy_caption}
            if caption_model:
                run_caption(clips, cap_out, caption_model, **kwargs)
            else:
                from tools.video_match.caption_video import DEFAULT_MODEL
                run_caption(clips, cap_out, DEFAULT_MODEL, **kwargs)

    if not skip_asr:
        if not clips.is_dir() or not any(clips.glob("*.mp4")):
            print(f"[asr] skip: no mp4 in {clips}")
        else:
            model = asr_model or ASR_DEFAULT
            print(f"[asr] model={model}")
            run_asr(clips, asr_out, model)

    if not skip_assemble:
        run_assemble([job], write_combined=False)


def run_all(
    jobs: list[dict],
    *,
    skip_caption: bool = False,
    skip_asr: bool = False,
    skip_assemble: bool = False,
    caption_model: str | None = None,
    asr_model: str | None = None,
    legacy_caption: bool = False,
) -> None:
    for job in jobs:
        run_job(
            job,
            skip_caption=skip_caption,
            skip_asr=skip_asr,
            skip_assemble=True,
            caption_model=caption_model,
            asr_model=asr_model,
            legacy_caption=legacy_caption,
        )
    if not skip_assemble:
        run_assemble(jobs, write_combined=True)


def main() -> None:
    load_env()
    p = argparse.ArgumentParser(description="Run caption + ASR + post_media assembly")
    p.add_argument("--platform", default="", help="xhs | tiktok | douyin")
    p.add_argument("--batch", default="", help="merged | 2604-marathon | 2608-olympic")
    p.add_argument("--skip-caption", action="store_true")
    p.add_argument("--skip-asr", action="store_true")
    p.add_argument("--skip-assemble", action="store_true")
    p.add_argument("--assemble-only", action="store_true", help="Only rebuild CSV from jsonl")
    p.add_argument("--caption-model", default="")
    p.add_argument("--asr-model", default="")
    p.add_argument("--legacy-caption", action="store_true")
    a = p.parse_args()

    jobs = filter_jobs(a.platform or None, a.batch or None) if (a.platform or a.batch) else JOBS

    if a.assemble_only:
        run_assemble(jobs, write_combined=len(jobs) == len(JOBS))
        return

    run_all(
        jobs,
        skip_caption=a.skip_caption,
        skip_asr=a.skip_asr,
        skip_assemble=a.skip_assemble,
        caption_model=a.caption_model or None,
        asr_model=a.asr_model or None,
        legacy_caption=a.legacy_caption,
    )


if __name__ == "__main__":
    main()
