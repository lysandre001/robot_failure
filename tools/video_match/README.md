# video_match — 跨平台同源视频匹配 (xhs ↔ tiktok)

最小可用版。4 个独立模块。`caption_video.py` 是唯一调用 LLM 的视觉模块，可单独删除并核算成本。

## 数据上下文
2025 北京亦庄半程机器人马拉松。两侧均同期发帖，仅靠时间无法去重 → 必须读视频内容。

## 模块
| 模块 | 文件 | API | 输入 | 输出 |
|---|---|---|---|---|
| M1 聚合 | `aggregate_tiktok.py` | — | `data/tiktok/beijing_robot_marathon_帖子数据(1).csv` | `output/video_match/tiktok_post_category_by_post.csv` (post 粒度, L1/L2 计数, 机器人状态/人的形象留空, 含空 `matched_xhs_id` 列) |
| M2 切片 | `download_clip.py` | yt-dlp | id+url csv | `clips/{id}.mp4` (0–30s) |
| M3 caption | `caption_video.py` | **SiliconFlow VLM** | `clips/` | `*_captions.jsonl` |
| M4 匹配 | `match.py` | **SiliconFlow Embedding** | 两侧 meta + 两侧 caption jsonl | `match_pairs.csv` + 回写 M1 输出的 `matched_xhs_id` |

## 端到端命令
```bash
export SILICONFLOW_API_KEY=sk-...

# M1
python tools/video_match/aggregate_tiktok.py

# M2  下载两侧前 30s
python tools/video_match/download_clip.py \
  --in  data/rawdata/posts.csv \
  --out-dir output/video_match/clips/xhs
python tools/video_match/download_clip.py \
  --in  output/video_match/tiktok_post_category_by_post.csv \
  --out-dir output/video_match/clips/tiktok

# M3  生 caption (可独立删除/重跑/换模型)
python tools/video_match/caption_video.py \
  --clip-dir output/video_match/clips/xhs \
  --out      output/video_match/xhs_captions.jsonl
python tools/video_match/caption_video.py \
  --clip-dir output/video_match/clips/tiktok \
  --out      output/video_match/tiktok_captions.jsonl

# M4  匹配 + 回写
python tools/video_match/match.py \
  --xhs-meta data/rawdata/posts.csv \
  --xhs-caps output/video_match/xhs_captions.jsonl \
  --tt-meta  output/video_match/tiktok_post_category_by_post.csv \
  --tt-caps  output/video_match/tiktok_captions.jsonl \
  --out-pairs output/video_match/match_pairs.csv \
  --threshold 0.78
```

## 成本估算 (粗算)
- M3: ~34 + 176 = 210 视频 × 1 次 VLM 调用 (3 帧 + 短 prompt)。Qwen2.5-VL-32B 单次 ~¥0.003–0.01 → 总 < ¥5。
- M4: ~210 条短文本 embedding (bge-m3) → < ¥0.1。
- 不满意可只用 M3，把 caption 丢给人工对照；或换 7B 模型再降一档。

## 删除/替换 caption 模块
若决定不用 VLM：
1. 删除 `caption_video.py` 与产出的 `*_captions.jsonl`；
2. M4 仍可跑 (只用帖子文本签名，准确率下降，靠人工抽检 `match_pairs.csv`)。

## 校验
人工抽看 `match_pairs.csv`：按 `score` 倒序看前 50 + threshold 附近 ±0.05 的边界 20 条，调阈值即可。
