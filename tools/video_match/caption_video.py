"""
M3: 视频 -> caption  (SiliconFlow VLM, 单文件可独立运行/可整体下线)

流程:
  1. ffmpeg 抽 3 帧 (1s / mid / end-1s) -> jpg
  2. 三帧拼成一条 multi-image message 送 Qwen2.5-VL
  3. 输出 jsonl: {id, caption, key_objects, scene, raw}

环境:
  SILICONFLOW_API_KEY=sk-xxx
  pip install requests pillow

成本控制要点 (后续可单独删除本脚本):
  - 模型默认 Qwen/Qwen2.5-VL-32B-Instruct, 可换 7B
  - 每视频只 3 帧, 短 prompt
  - 失败可重跑 (基于 done set 跳过)
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Iterable

import requests

API_URL = "https://api.siliconflow.cn/v1/chat/completions"
DEFAULT_MODEL = "Qwen/Qwen3-VL-30B-A3B-Instruct"

SYS_PROMPT = (
    "你是视频内容标注员。下面是 2025 年北京亦庄半程机器人马拉松的相关短视频的几帧截图。"
    "请用中文输出一个 JSON, 字段: "
    "caption(<=40字, 概括视频核心场景), "
    "robots(出现的机器人型号/颜色/数量, 没有则空字符串), "
    "humans(人的动作与角色, 如选手/观众/工作人员, 没有则空字符串), "
    "scene(地点/赛段/标志物, 如起跑线/补给点/终点门, 没有则空字符串), "
    "event(关键事件, 如摔倒/起身/冲线/被超越/被搀扶, 没有则空字符串)。"
    "只输出 JSON, 不要解释。"
)


def extract_frames(video: Path, out_dir: Path, n: int = 3) -> list[Path]:
    """抽 n 帧均匀分布 (1s, mid, end-1s 简化为 ffmpeg -vf select)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # 用 ffprobe 拿时长
    try:
        dur = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(video),
        ]).decode().strip())
    except Exception:
        dur = 30.0
    ts = [1.0, max(dur / 2, 1.5), max(dur - 1.0, 2.0)] if n == 3 else [
        (i + 0.5) * dur / n for i in range(n)
    ]
    paths = []
    for i, t in enumerate(ts):
        out = out_dir / f"f{i}.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{t:.2f}", "-i", str(video),
            "-frames:v", "1", "-q:v", "4",
            "-vf", "scale=512:-2",
            str(out),
        ], check=True)
        paths.append(out)
    return paths


def img_to_data_url(p: Path) -> str:
    b = p.read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(b).decode()


def caption_one(frames: list[Path], model: str, api_key: str) -> dict:
    content = [{"type": "text", "text": "请按系统要求输出 JSON。"}]
    for fr in frames:
        content.append({"type": "image_url", "image_url": {"url": img_to_data_url(fr)}})
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYS_PROMPT},
            {"role": "user", "content": content},
        ],
        "temperature": 0.1,
        "max_tokens": 400,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(API_URL, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, json=body, timeout=180)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(text)
    except Exception:
        return {"caption": text}


def iter_videos(clip_dir: Path) -> Iterable[Path]:
    yield from sorted(clip_dir.glob("*.mp4"))


def run(clip_dir: Path, out_jsonl: Path, model: str) -> None:
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise SystemExit("SILICONFLOW_API_KEY 未设置")

    done = set()
    if out_jsonl.exists():
        for line in out_jsonl.read_text().splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:
                pass

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    frames_root = out_jsonl.parent / "_frames"

    with out_jsonl.open("a") as f:
        for v in iter_videos(clip_dir):
            pid = v.stem
            if pid in done:
                continue
            try:
                frames = extract_frames(v, frames_root / pid)
                payload = caption_one(frames, model=model, api_key=api_key)
                payload["id"] = pid
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                f.flush()
                print(f"[M3] {pid} -> {payload.get('caption','')[:30]}")
            except Exception as e:
                print(f"[M3-FAIL] {pid}: {e}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--clip-dir", required=True)
    p.add_argument("--out", required=True, help="jsonl path")
    p.add_argument("--model", default=DEFAULT_MODEL)
    a = p.parse_args()
    run(Path(a.clip_dir), Path(a.out), a.model)


if __name__ == "__main__":
    main()
