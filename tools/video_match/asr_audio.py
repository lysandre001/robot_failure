"""
M3a: 视频 -> ASR 转写 (SiliconFlow audio/transcriptions)

流程:
  1. ffmpeg 从 mp4 抽 16 kHz mono wav，缓存 output/video_match/_audio/{id}.wav
  2. POST /v1/audio/transcriptions（Qwen/Qwen3-ASR-1.7B）
  3. 输出 jsonl: {id, asr_text, segments, language, asr_has_speech, ...}

环境: SILICONFLOW_API_KEY
断点续跑: jsonl 已有 id 跳过
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

import requests

from phase1.config import ROOT

API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
DEFAULT_MODEL = "Qwen/Qwen3-ASR-1.7B"
MIN_SPEECH_CHARS = 2


def probe_duration(video: Path) -> float:
    try:
        return float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(video),
        ]).decode().strip())
    except Exception:
        return 0.0


def extract_audio_wav(video: Path, out_wav: Path) -> Path:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if out_wav.exists() and out_wav.stat().st_size > 0:
        return out_wav
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000",
        str(out_wav),
    ], check=True)
    return out_wav


def clean_sensevoice_text(raw: str) -> str:
    """Strip SenseVoice meta tags like <|zh|><|NEUTRAL|><|Speech|>."""
    text = re.sub(r"<\|[^|]+\|>", "", raw or "")
    return " ".join(text.split()).strip()


def detect_language(text: str) -> str:
    if not text:
        return ""
    if re.search(r"[\u4e00-\u9fff]", text):
        if re.search(r"[A-Za-z]", text):
            return "zh-en-mixed"
        return "zh"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "unknown"


def has_speech(text: str) -> int:
    cleaned = clean_sensevoice_text(text)
    # Drop punctuation-only residue
    alnum = re.sub(r"[\W_]+", "", cleaned, flags=re.UNICODE)
    return int(len(alnum) >= MIN_SPEECH_CHARS)


def transcribe_wav(
    wav: Path,
    model: str,
    api_key: str,
    timeout: int = 120,
) -> dict:
    with wav.open("rb") as fh:
        files = {
            "file": (wav.name, fh, "audio/wav"),
            "model": (None, model),
        }
        # Ignore shell HTTP_PROXY (often 127.0.0.1:7897 when VPN is off).
        with requests.Session() as session:
            session.trust_env = False
            r = session.post(
                API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                timeout=timeout,
            )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "text" in data:
        return data
    if isinstance(data, str):
        return {"text": data}
    raise ValueError(f"Unexpected ASR response: {str(data)[:200]}")


def build_record(
    pid: str,
    video: Path,
    model: str,
    api_key: str,
    audio_root: Path,
) -> dict:
    wav = audio_root / f"{pid}.wav"
    duration_sec = probe_duration(video)
    extract_audio_wav(video, wav)
    api_result = transcribe_wav(wav, model=model, api_key=api_key)
    raw_text = str(api_result.get("text", "") or "")
    asr_text = clean_sensevoice_text(raw_text)
    segments = api_result.get("segments") or []
    if not segments and asr_text:
        segments = [{"start": 0.0, "end": duration_sec, "text": asr_text}]
    speech = has_speech(asr_text)
    return {
        "id": pid,
        "asr_text": asr_text,
        "segments": segments,
        "language": detect_language(asr_text),
        "asr_has_speech": speech,
        "duration_sec": duration_sec,
        "model": model,
        "error": "",
    }


def iter_videos(clip_dir: Path) -> Iterable[Path]:
    yield from sorted(clip_dir.glob("*.mp4"))


def load_done(out_jsonl: Path) -> set[str]:
    """Skip ids with a successful prior record (no error field)."""
    done: set[str] = set()
    if not out_jsonl.exists():
        return done
    for line in out_jsonl.read_text().splitlines():
        try:
            rec = json.loads(line)
            if not rec.get("error"):
                done.add(rec["id"])
        except Exception:
            pass
    return done


def run(
    clip_dir: Path,
    out_jsonl: Path,
    model: str = DEFAULT_MODEL,
    audio_root: Path | None = None,
) -> None:
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise SystemExit("SILICONFLOW_API_KEY 未设置")

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    if audio_root is None:
        audio_root = out_jsonl.parent / "_audio"
    audio_root.mkdir(parents=True, exist_ok=True)

    done = load_done(out_jsonl)
    pending = [v for v in iter_videos(clip_dir) if v.stem not in done]
    print(f"[M3a] clip_dir={clip_dir} done={len(done)} pending={len(pending)}")

    with out_jsonl.open("a", encoding="utf-8") as f:
        for video in pending:
            pid = video.stem
            try:
                print(f"[M3a] {pid} ...")
                rec = build_record(pid, video, model, api_key, audio_root)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                status = "speech" if rec["asr_has_speech"] else "empty"
                preview = (rec["asr_text"] or "")[:60]
                print(f"[M3a] {pid} [{status}] -> {preview}")
            except Exception as e:
                err_rec = {
                    "id": pid,
                    "asr_text": "",
                    "segments": [],
                    "language": "",
                    "asr_has_speech": 0,
                    "duration_sec": probe_duration(video),
                    "model": model,
                    "error": str(e),
                }
                f.write(json.dumps(err_rec, ensure_ascii=False) + "\n")
                f.flush()
                print(f"[M3a-FAIL] {pid}: {e}")


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


def main() -> None:
    load_env()
    p = argparse.ArgumentParser(description="M3a: video clip -> ASR (SiliconFlow)")
    p.add_argument("--clip-dir", required=True)
    p.add_argument("--out", required=True, help="jsonl output path")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--audio-root", default="", help="wav cache dir (default: sibling _audio/)")
    a = p.parse_args()
    audio_root = Path(a.audio_root) if a.audio_root else None
    run(Path(a.clip_dir), Path(a.out), a.model, audio_root=audio_root)


if __name__ == "__main__":
    main()
