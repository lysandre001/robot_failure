"""Shared job definitions for clip download + post media (caption / ASR) pipeline."""
from __future__ import annotations

from pathlib import Path

from phase1.config import ROOT

OUTPUT_ROOT = ROOT / "output" / "video_match"
CLEAN_ROOT = ROOT / "data" / "clean"

JOBS: list[dict] = [
    {
        "platform": "xhs",
        "batch": "merged",
        "raw": ROOT / "data" / "rawdata" / "posts.csv",
        "id_col": "帖子id",
        "url_col": "帖子链接",
        "title_col": None,
        "text_col": "帖子正文",
        "clips": ROOT / "data" / "rawdata" / "xhs" / "clips",
        "reuse": ROOT / "output" / "video_match" / "clips" / "xhs",
        "seed_captions": ROOT / "output" / "video_match" / "config_captions.jsonl",
    },
    {
        "platform": "tiktok",
        "batch": "2604-marathon",
        "raw": ROOT / "data" / "rawdata" / "tiktok" / "2604-marathon" / "beijing_robot_marathon_帖子数据(1).csv",
        "id_col": "帖子id",
        "url_col": "帖子链接",
        "title_col": "帖子标题",
        "text_col": "帖子正文",
        "clips": ROOT / "data" / "rawdata" / "tiktok" / "2604-marathon" / "clips",
        "reuse": ROOT / "output" / "video_match" / "clips" / "tiktok",
    },
    {
        "platform": "tiktok",
        "batch": "2608-olympic",
        "raw": ROOT / "data" / "rawdata" / "tiktok" / "2608-olympic" / "tiktok_World_Humanoid_Robot_Games_帖子数据.csv",
        "id_col": "帖子id",
        "url_col": "帖子链接",
        "title_col": "帖子标题",
        "text_col": "帖子正文",
        "clips": ROOT / "data" / "rawdata" / "tiktok" / "2608-olympic" / "clips",
    },
    {
        "platform": "douyin",
        "batch": "2608-olympic",
        "raw": ROOT / "data" / "rawdata" / "douyin" / "2608-olympic" / "抖音_世界人形机器人运动会.csv",
        "id_col": "作品视频ID",
        "url_col": "作品视频链接",
        "title_col": "作品标题",
        "text_col": "作品标题",
        "clips": ROOT / "data" / "rawdata" / "douyin" / "2608-olympic" / "clips",
    },
]


def job_key(job: dict) -> str:
    return f"{job['platform']}_{job['batch']}"


def captions_jsonl(job: dict) -> Path:
    return OUTPUT_ROOT / f"{job_key(job)}_captions.jsonl"


def asr_jsonl(job: dict) -> Path:
    return OUTPUT_ROOT / f"{job_key(job)}_asr.jsonl"


def post_media_csv(job: dict) -> Path:
    return CLEAN_ROOT / job["platform"] / job["batch"] / "post_media.csv"


def combined_post_media_csv() -> Path:
    return CLEAN_ROOT / "post_media.csv"


def filter_jobs(platform: str | None = None, batch: str | None = None) -> list[dict]:
    out = JOBS
    if platform:
        out = [j for j in out if j["platform"] == platform]
    if batch:
        out = [j for j in out if j["batch"] == batch]
    if not out:
        raise SystemExit(f"No job matched platform={platform!r} batch={batch!r}")
    return out
