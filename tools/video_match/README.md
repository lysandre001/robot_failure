# video_match — 跨平台同源视频匹配 + 帖子视听元数据

最小可用版。核心模块可独立运行。`caption_video.py` 是唯一 VLM 视觉模块；`asr_audio.py` 是唯一 ASR 模块；均可单独删除并核算成本。

## 数据上下文
2025 北京亦庄半程机器人马拉松。两侧均同期发帖，仅靠时间无法去重 → 必须读视频内容。

## 模块
| 模块 | 文件 | API | 输入 | 输出 |
|---|---|---|---|---|
| M1 聚合 | `aggregate_tiktok.py` | — | `data/tiktok/beijing_robot_marathon_帖子数据(1).csv` | `output/video_match/tiktok_post_category_by_post.csv` (post 粒度, L1/L2 计数, 机器人状态/人的形象留空, 含空 `matched_xhs_id` 列) |
| M2 切片 | `download_clip.py` | yt-dlp | id+url csv | `clips/{id}.mp4` (0–30s) |
| M3 caption | `caption_video.py` | **SiliconFlow VLM** | `clips/` (0–30s) | `output/video_match/{platform}_{batch}_captions.jsonl` |
| M3a ASR | `asr_audio.py` | **SiliconFlow** `Qwen/Qwen3-ASR-1.7B` | `clips/` (0–30s) | `output/video_match/{platform}_{batch}_asr.jsonl` |
| M4 匹配 | `match.py` | **SiliconFlow Embedding** | 两侧 meta + 两侧 caption jsonl | `match_pairs.csv` + 回写 M1 输出的 `matched_xhs_id` |
| M5 组装 | `assemble_post_media.py` | — | clip report + caption + ASR jsonl | `data/clean/{platform}/{batch}/post_media.csv` |
| 总入口 | `run_post_media.py` | — | 上述 M3+M3a+M5 | `data/clean/post_media.csv` |

## 帖子视听元数据（推荐入口）

clips 已下载到 `data/rawdata/{platform}/.../clips/` 后：

```bash
# 全平台：dense caption + ASR + 组装 CSV（读项目根 .env）
python -m tools.video_match.run_post_media

# 单源
python -m tools.video_match.run_post_media --platform xhs --batch merged

# 只重跑 CSV（jsonl 已有）
python -m tools.video_match.run_post_media --assemble-only
```

产物：
- `output/video_match/{platform}_{batch}_captions.jsonl`
- `output/video_match/{platform}_{batch}_asr.jsonl`
- `data/clean/{platform}/{batch}/post_media.csv`
- `data/clean/post_media.csv`（跨平台总表）

小红书会先 seed `config_captions.jsonl` 到 `xhs_merged_captions.jsonl`，避免重复 VLM 调用。

## 跨平台匹配（早期 pilot）

```bash
export SILICONFLOW_API_KEY=sk-...

# M1
python tools/video_match/aggregate_tiktok.py

# M2  下载两侧前 30s
python -m tools.download_all_clips

# M3 / M3a  见 run_post_media 或单独调用：
python tools/video_match/caption_video.py \
  --clip-dir data/rawdata/xhs/clips \
  --out      output/video_match/xhs_merged_captions.jsonl
python tools/video_match/asr_audio.py \
  --clip-dir data/rawdata/xhs/clips \
  --out      output/video_match/xhs_merged_asr.jsonl

# M4  匹配 + 回写
python tools/video_match/match.py \
  --xhs-meta data/rawdata/posts.csv \
  --xhs-caps output/video_match/xhs_merged_captions.jsonl \
  --tt-meta  output/video_match/tiktok_post_category_by_post.csv \
  --tt-caps  output/video_match/tiktok_2604-marathon_captions.jsonl \
  --out-pairs output/video_match/match_pairs.csv \
  --threshold 0.78
```

## M3 标注框架 (dense, 默认)
每 5 秒一段 (0–30s 共 6 段)，每段 VLM 三层:
1. **全局描述** — 该时段发生了什么
2. **五维追问** — scene / people / actions / interaction / temporal (Who-What-Where-When-How)
3. **异常追问** — 有无不寻常时刻

第 7 次纯文本调用合并为 `overview` + `timeline` + 汇总字段。输出仍含 `caption/robots/humans/scene/event` 供 M4 匹配。

## M3a ASR
- ffmpeg 抽 16 kHz mono wav → `output/video_match/_audio/{id}.wav`
- 默认模型：`Qwen/Qwen3-ASR-1.7B`（脚本内常量；可用 `--asr-model` 覆盖）
- 无语音 / 纯 BGM：`asr_has_speech=0`，`asr_status=empty_speech`

## 成本估算 (粗算)
- M3 dense: ~300 视频 × 7 次 VLM → 约 ¥100–350。
- M3a ASR: ~300 × 30s → 相对 VLM 便宜。
- M3 legacy (`--legacy`): 210 × 1 次 → < ¥5。
- M4: ~210 条短文本 embedding (bge-m3) → < ¥0.1。
- 不满意可只用 M3，把 caption 丢给人工对照；或换 7B 模型再降一档。

## 删除/替换 caption 模块
若决定不用 VLM：
1. 删除 `caption_video.py` 与产出的 `*_captions.jsonl`；
2. M4 仍可跑 (只用帖子文本签名，准确率下降，靠人工抽检 `match_pairs.csv`)。

## 校验
人工抽看 `match_pairs.csv`：按 `score` 倒序看前 50 + threshold 附近 ±0.05 的边界 20 条，调阈值即可。
