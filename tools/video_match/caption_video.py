"""
M3: 视频 -> dense caption  (SiliconFlow VLM, 单文件可独立运行/可整体下线)

流程 (dense, 默认):
  1. ffmpeg 按 5s 切段 (0-30s), 每段抽 2 帧 (段首+段中)
  2. 每段一次 VLM: 三层标注 (全局 / 五维追问 / 异常)
  3. 纯文本 VLM 合并各段 -> overview + timeline + 汇总字段
  4. 输出 jsonl: {id, overview, caption, segments, scene, robots, humans, event, ...}

流程 (legacy, --legacy):
  3 帧单次调用, 兼容旧版短 caption

环境:
  SILICONFLOW_API_KEY=sk-xxx
  pip install requests

成本控制:
  dense: ~7 次 VLM/视频 (6 段 + 1 合并); legacy: 1 次
  失败可重跑 (基于 done set 跳过)
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
DEFAULT_WINDOW_SEC = 30.0
DEFAULT_SEGMENT_SEC = 5.0

SEGMENT_SYS_PROMPT = """你是视频内容标注员，正在标注机器人马拉松大型赛事视频，用于后续学术分析。
当前时间段: {t_start:.0f}s - {t_end:.0f}s。只描述你观察到的内容，不做解释、推断或价值判断。

请按三层结构输出 JSON:
1. global: 该时段整体发生了什么（自然段，80-120字）
2. dimensions: 五维标注 {{
     scene: 地点、空间布局、关键物体（物理空间如何组织）,
     people: 人物与角色（身份、外观；多人时区分个体并保持指称一致）,
     actions: 原子动作 + 复合事件（从具体动作到事件）,
     interaction: 视线接触、共同注意、人-机器人或者人-人之间的互动,
     temporal: 该时段内动作与状态的变化顺序
   }}
3. anomaly: 有无不寻常或与其他时刻明显不同的内容；没有则空字符串

只输出 JSON，不要解释。"""

MERGE_SYS_PROMPT = """你是视频标注整合员。下面是同一赛事视频前30秒、每5秒一段的分层标注。
请合并为完整的 dense video caption，用于跨平台视频匹配与后续分析。

输出 JSON:
- overview: 150-250字，严格按时间顺序叙述全程（开场→变化→关键事件→结尾）
- timeline: 数组，每项 {{t_start, t_end, summary}}，覆盖各时间段
- scene: 合并后的场景与环境
- robots: 机器人型号/颜色/数量/状态变化
- humans: 人物与角色汇总
- event: 全程最关键单一事件；没有则空字符串
- anomaly: 全程最突出的异常或不寻常时刻；没有则空字符串

只输出 JSON，不要解释。"""


def probe_duration(video: Path) -> float:
    try:
        return float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(video),
        ]).decode().strip())
    except Exception:
        return DEFAULT_WINDOW_SEC


def build_segments(window_sec: float, segment_sec: float, clip_dur: float) -> list[tuple[float, float]]:
    end_cap = min(window_sec, clip_dur)
    segments: list[tuple[float, float]] = []
    t = 0.0
    while t < end_cap - 0.1:
        seg_end = min(t + segment_sec, end_cap)
        if seg_end - t >= 0.5:
            segments.append((t, seg_end))
        t += segment_sec
    return segments


def extract_frame_at(video: Path, out: Path, t: float) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{t:.2f}", "-i", str(video),
        "-frames:v", "1", "-q:v", "4",
        "-vf", "scale=512:-2",
        str(out),
    ], check=True)
    return out


def extract_segment_frames(
    video: Path,
    out_dir: Path,
    t_start: float,
    t_end: float,
) -> list[tuple[float, Path]]:
    """每段抽 2 帧: 段首+0.5s 与段中点，捕捉局部动态。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    span = t_end - t_start
    ts = [
        min(t_start + 0.5, t_end - 0.1),
        t_start + span / 2,
    ]
    paths: list[tuple[float, Path]] = []
    for i, t in enumerate(ts):
        out = out_dir / f"s{int(t_start):02d}_f{i}.jpg"
        paths.append((t, extract_frame_at(video, out, t)))
    return paths


def extract_legacy_frames(video: Path, out_dir: Path, n: int = 3) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = probe_duration(video)
    ts = [1.0, max(dur / 2, 1.5), max(dur - 1.0, 2.0)] if n == 3 else [
        (i + 0.5) * dur / n for i in range(n)
    ]
    paths = []
    for i, t in enumerate(ts):
        out = out_dir / f"f{i}.jpg"
        paths.append(extract_frame_at(video, out, t))
    return paths


def img_to_data_url(p: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()


def chat_json(
    messages: list[dict],
    model: str,
    api_key: str,
    max_tokens: int = 800,
    timeout: int = 180,
) -> dict:
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(API_URL, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, json=body, timeout=timeout)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


def caption_segment(
    frames: list[tuple[float, Path]],
    t_start: float,
    t_end: float,
    model: str,
    api_key: str,
) -> dict:
    content: list[dict] = [{
        "type": "text",
        "text": (
            f"以下是 {t_start:.0f}s-{t_end:.0f}s 时段的截图（按时间从早到晚）。"
            "请完成三层标注。"
        ),
    }]
    for t, fr in frames:
        content.append({"type": "text", "text": f"【t={t:.1f}s】"})
        content.append({"type": "image_url", "image_url": {"url": img_to_data_url(fr)}})

    result = chat_json([
        {"role": "system", "content": SEGMENT_SYS_PROMPT.format(t_start=t_start, t_end=t_end)},
        {"role": "user", "content": content},
    ], model=model, api_key=api_key, max_tokens=900)
    result["t_start"] = t_start
    result["t_end"] = t_end
    return result


def merge_segments(segments: list[dict], model: str, api_key: str) -> dict:
    seg_text = json.dumps(segments, ensure_ascii=False, indent=2)
    return chat_json([
        {"role": "system", "content": MERGE_SYS_PROMPT},
        {"role": "user", "content": f"各段标注如下:\n\n{seg_text}"},
    ], model=model, api_key=api_key, max_tokens=1200, timeout=120)


def caption_legacy(frames: list[Path], model: str, api_key: str) -> dict:
    content = [{"type": "text", "text": "请按系统要求输出 JSON。"}]
    for fr in frames:
        content.append({"type": "image_url", "image_url": {"url": img_to_data_url(fr)}})
    return chat_json([
        {"role": "system", "content": LEGACY_SYS_PROMPT},
        {"role": "user", "content": content},
    ], model=model, api_key=api_key, max_tokens=400)


def caption_dense(
    video: Path,
    frames_root: Path,
    model: str,
    api_key: str,
    window_sec: float,
    segment_sec: float,
) -> dict:
    pid = video.stem
    clip_dur = probe_duration(video)
    segments_spec = build_segments(window_sec, segment_sec, clip_dur)
    seg_dir = frames_root / pid

    segment_results: list[dict] = []
    for t_start, t_end in segments_spec:
        frames = extract_segment_frames(video, seg_dir / f"{int(t_start):02d}", t_start, t_end)
        seg = caption_segment(frames, t_start, t_end, model=model, api_key=api_key)
        segment_results.append(seg)
        print(f"  [{pid}] {t_start:.0f}-{t_end:.0f}s ok")

    merged = merge_segments(segment_results, model=model, api_key=api_key)
    merged["segments"] = segment_results
    merged["window_sec"] = window_sec
    merged["segment_sec"] = segment_sec
    return merged


def iter_videos(clip_dir: Path) -> Iterable[Path]:
    yield from sorted(clip_dir.glob("*.mp4"))


def run(
    clip_dir: Path,
    out_jsonl: Path,
    model: str,
    *,
    legacy: bool = False,
    window_sec: float = DEFAULT_WINDOW_SEC,
    segment_sec: float = DEFAULT_SEGMENT_SEC,
) -> None:
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
    mode = "legacy" if legacy else "dense"

    with out_jsonl.open("a") as f:
        for v in iter_videos(clip_dir):
            pid = v.stem
            if pid in done:
                continue
            try:
                if legacy:
                    frames = extract_legacy_frames(v, frames_root / pid)
                    payload = caption_legacy(frames, model=model, api_key=api_key)
                else:
                    print(f"[M3-{mode}] {pid} ({int(window_sec)}s / {int(segment_sec)}s seg)")
                    payload = caption_dense(
                        v, frames_root, model=model, api_key=api_key,
                        window_sec=window_sec, segment_sec=segment_sec,
                    )
                payload["id"] = pid
                payload["mode"] = mode
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                f.flush()
                preview = payload.get("overview") or payload.get("caption", "")
                print(f"[M3] {pid} -> {preview[:50]}")
            except Exception as e:
                print(f"[M3-FAIL] {pid}: {e}")


def main() -> None:
    p = argparse.ArgumentParser(description="M3: video -> dense caption (SiliconFlow VLM)")
    p.add_argument("--clip-dir", required=True)
    p.add_argument("--out", required=True, help="jsonl path")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--legacy", action="store_true", help="旧版 3 帧单次调用")
    p.add_argument("--window-sec", type=float, default=DEFAULT_WINDOW_SEC, help="分析窗口 (默认 30s)")
    p.add_argument("--segment-sec", type=float, default=DEFAULT_SEGMENT_SEC, help="分段粒度 (默认 5s)")
    a = p.parse_args()
    run(
        Path(a.clip_dir), Path(a.out), a.model,
        legacy=a.legacy,
        window_sec=a.window_sec,
        segment_sec=a.segment_sec,
    )


if __name__ == "__main__":
    main()
