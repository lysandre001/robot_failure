# 视频 Dense Caption 流程说明（论文正文与附录）

> **版本**：2026-09-09  
> **代码入口**：`tools/video_match/`（M3 VLM caption + M3a ASR + M5 组装；总入口 `run_post_media.py`）  
> **复现说明**：`tools/video_match/README.md`

---

## 一、研究用途

本流程服务于 **2025 北京亦庄半程机器人马拉松** 期间跨平台（小红书 ↔ TikTok）同源帖识别，并为帖子级视觉内容提供结构化描述。

**核心问题**：两侧平台同期大量转载同一赛事片段，发帖时间无法区分同源 → 必须在帖子文本之外读取 **视频画面内容**。

**与本项目主线的关系**：

| 用途 | 语料 | 当前状态 |
|------|------|----------|
| 跨平台视频去重 / 配对 | 小红书全量帖 + TikTok 抓取帖 | 早期 pilot：`xhs_captions.jsonl`（30 条 legacy）+ `tiktok_captions.jsonl`（70 条 legacy）→ `match_pairs.csv` |
| 理论抽样帖（16 帖矩阵）视觉描述 | `config/post_category_by_post.csv` | **已完成 dense run**：31/34 帖 → `output/video_match/config_captions.jsonl` |

主评论分析管线（Phase 1 清洗、主题建模）**不依赖** caption；caption 是独立的视觉侧产物，可按需并入帖子级变量或跨平台链接表。

---

## 二、端到端流程概览

```
帖子 CSV (id + url)
    │
    ▼  M2  download_clip.py / download_all_clips.py
data/rawdata/{platform}/clips/{id}.mp4  (前 30s)
    │
    ├─► M3  caption_video.py   SiliconFlow VLM (Qwen3-VL-30B)
    │       output/video_match/{platform}_{batch}_captions.jsonl
    │
    └─► M3a asr_audio.py       SiliconFlow SenseVoiceSmall
            output/video_match/{platform}_{batch}_asr.jsonl
    │
    ▼  M5  assemble_post_media.py
data/clean/post_media.csv  (帖子级：视觉描述 + ASR 全文)

（可选旁路）
    ▼  M4  match.py            BAAI/bge-m3 embedding + cosine
match_pairs.csv  (+ 回写 matched_xhs_id)
```

**M1**（`aggregate_tiktok.py`）仅整理 TikTok 侧帖子元数据；**推荐总入口** `python -m tools.video_match.run_post_media`。

---

## 三、M2：视频切片下载

**脚本**：`tools/video_match/download_clip.py`

**输入**：CSV，至少含 `帖子id`、`帖子链接`（列名可 `--id-col` / `--url-col` 指定）。

**输出**：`out_dir/{帖子id}.mp4`，内容为 **0–30 秒**（`yt-dlp --download-sections *0-30`）。

**依赖**：`yt-dlp`（项目 venv 已安装）、`ffmpeg`。

**失败处理**：多次重试后仍失败的 id 写入 `out_dir/failed.csv`；常见原因包括链接超时、token 过期、或 **图文帖无视频流**（yt-dlp 报 `No video formats found`）。

**理论抽样帖实测**（2026-05-31，`config/post_category_by_post.csv`，*N* = 34）：

| 结果 | 数量 |
|------|------|
| 成功下载 mp4 | 31 |
| 失败（见 `clips/config_subset/failed.csv`） | 3 |

失败 id：`69db34bb000000001a0348ae`、`69e44f3a000000002301079c`、`69e46032000000001f002048`（疑为图文帖或链接不可用；**未**纳入 caption）。

---

## 四、M3：Dense Video Caption（默认模式）

**脚本**：`tools/video_match/caption_video.py`

**模型**：SiliconFlow Chat Completions，`Qwen/Qwen3-VL-30B-A3B-Instruct`（可用 `--model` 更换）。

**环境变量**：`SILICONFLOW_API_KEY`

### 4.1 分析窗口与抽帧

- 分析窗口：**前 30 秒**（`--window-sec 30`，与 M2 切片一致）。
- 分段粒度：**每 5 秒一段**（`--segment-sec 5`），通常得 6 段（0–5, 5–10, …, 25–30）；若 clip 略短于 30s，末段相应缩短。
- 每段抽 **2 帧**（ffmpeg）：段内 **+0.5s** 与 **段中点**；缩放到宽 512px JPEG，缓存于 `output/video_match/_frames/{id}/`。

### 4.2 标注框架（Who / What / Where / When / How）

每个 5 秒段调用 **一次 VLM**，在同一次回复中完成三层结构（非多轮对话）：

| 层级 | 字段 | 内容 |
|------|------|------|
| **第一层：全局描述** | `global` | 该时段整体发生了什么（80–120 字自然段）；只描述观察，不做解释或价值判断 |
| **第二层：分维度追问** | `dimensions.scene` | 地点、空间布局、关键物体 |
| | `dimensions.people` | 人物/角色、外观；多人时区分个体 |
| | `dimensions.actions` | 原子动作 + 复合事件 |
| | `dimensions.interaction` | 视线、共同注意、人-机器人 / 人-人互动 |
| | `dimensions.temporal` | 该时段内动作与状态的变化顺序 |
| **第三层：异常追问** | `anomaly` | 不寻常或与前后明显不同的内容；无则空字符串 |

输入消息中每张截图前标注 `【t=Xs】`，便于模型建立时序。

### 4.3 段间合并（第 7 次 VLM 调用）

各段 JSON 汇总后，**纯文本**再调一次 VLM，生成帖子级字段：

| 字段 | 说明 |
|------|------|
| `overview` | 150–250 字，按时间顺序叙述全程 |
| `caption` | ≤40 字一句话摘要 |
| `timeline` | `[{t_start, t_end, summary}, …]` |
| `scene` | 合并后的场景与环境 |
| `robots` | 机器人型号/颜色/数量/状态 |
| `humans` | 人物与角色汇总 |
| `event` | 全程最关键单一事件 |
| `anomaly` | 全程最突出异常 |
| `segments` | 各段完整三层标注（保留供人工复查） |
| `mode` | `"dense"` |
| `window_sec` / `segment_sec` | 分析参数 |

### 4.4 API 调用与成本

每条 **视频** 约 **7 次** VLM 调用（6 段 + 1 合并）。理论抽样 31 条 ≈ 217 次；粗算 ¥15–35 量级（视 image token 与模型而定）。

**断点续跑**：已写入 jsonl 的 `id` 会自动跳过。

### 4.5 Legacy 模式（可选）

`--legacy`：旧版 **3 帧单次** 短 caption（`caption` / `robots` / `humans` / `scene` / `event`），成本低，时序信息弱。早期 pilot 的 `xhs_captions.jsonl`、`tiktok_captions.jsonl` 即此模式。

---

## 五、M3a：音频 ASR

**脚本**：`tools/video_match/asr_audio.py`

**模型**：SiliconFlow `FunAudioLLM/SenseVoiceSmall`（`--model` 可换）

**流程**：
- ffmpeg 从 30s clip 抽 16 kHz mono wav，缓存 `output/video_match/_audio/{id}.wav`
- `POST /v1/audio/transcriptions`；SenseVoice 返回 `{"text": "..."}`（无 word 级 timestamp）
- 无有效语音：`asr_has_speech=0`，`asr_status=empty_speech`

**输出 jsonl 字段**：`id, asr_text, segments, language, asr_has_speech, duration_sec, model, error`

**断点续跑**：jsonl 已有 `id` 跳过。

---

## 六、M5：帖子视听元数据表

**脚本**：`tools/video_match/assemble_post_media.py`（由 `run_post_media.py` 调用）

**产物**：
- 分源：`data/clean/{platform}/{batch}/post_media.csv`
- 总表：`data/clean/post_media.csv`

**主要列**：`post_id, url, post_title, post_text, video_overview, video_caption, asr_text, caption_status, asr_status, clip_status, ...`

小红书会先 seed `config_captions.jsonl` → `xhs_merged_captions.jsonl`，避免重复 VLM。

---

## 七、M4：跨平台匹配（使用 caption 的方式）

**脚本**：`tools/video_match/match.py`

**签名构造**（每帖）：

```
_sig = 帖子正文 (+ TikTok 标题)  ||  overview | caption | robots | humans | scene | event | anomaly
```

**嵌入**：SiliconFlow `BAAI/bge-m3`；对每个 TikTok 帖取 cosine 相似度最高的 xhs 帖；`score ≥ threshold`（默认 0.78）记为 matched。

**输出**：`match_pairs.csv`；并回写 TikTok 元数据表 `matched_xhs_id`。

Caption 模块可整体删除，M4 仍可仅用文本签名运行（准确率下降，需人工抽检）。

---

## 八、已落盘产物（理论抽样帖）

| 路径 | 说明 |
|------|------|
| `config/post_category_by_post.csv` | 输入列表（34 帖；含 `机器人状态`、`人的形象` 研究编码） |
| `output/video_match/clips/config_subset/*.mp4` | 31 个 30s 切片 |
| `output/video_match/clips/config_subset/failed.csv` | 3 条下载失败 |
| `output/video_match/config_captions.jsonl` | **31 条 dense caption**（JSONL，一行一帖） |
| `output/video_match/_frames/` | 抽帧缓存（可删后重跑 M3） |

**早期跨平台 pilot**（legacy，非理论矩阵全量）：

| 路径 | 条数 |
|------|------|
| `output/video_match/xhs_captions.jsonl` | 30 |
| `output/video_match/tiktok_captions.jsonl` | 70 |
| `output/video_match/match_pairs.csv` | TikTok × xhs 配对表 |

---

## 九、输出 JSON 结构示例（dense）

```json
{
  "id": "69da7e87000000001a03484e",
  "mode": "dense",
  "overview": "…按时间顺序的 150–250 字叙述…",
  "caption": "…",
  "timeline": [{"t_start": 0, "t_end": 5, "summary": "…"}],
  "scene": "…",
  "robots": "…",
  "humans": "…",
  "event": "…",
  "anomaly": "",
  "segments": [
    {
      "t_start": 0, "t_end": 5,
      "global": "…",
      "dimensions": {
        "scene": "…", "people": "…", "actions": "…",
        "interaction": "…", "temporal": "…"
      },
      "anomaly": ""
    }
  ],
  "window_sec": 30.0,
  "segment_sec": 5.0
}
```

字段类型因 VLM 输出略有浮动（如 `robots` 有时为字符串、有时为对象数组）；下游匹配前如需严格 schema 可做规范化脚本。

---

## 十、复现命令

### 理论抽样帖（仅 caption）

```bash
cd /Users/yilin/project/2604-robotic_failure_research
export SILICONFLOW_API_KEY=sk-...

# M2
.venv/bin/python tools/video_match/download_clip.py \
  --in  config/post_category_by_post.csv \
  --out-dir output/video_match/clips/config_subset

# M3  dense
.venv/bin/python tools/video_match/caption_video.py \
  --clip-dir output/video_match/clips/config_subset \
  --out      output/video_match/config_captions.jsonl
```

### 全平台 caption + ASR + CSV

```bash
python -m tools.video_match.run_post_media
python -m tools.video_match.run_post_media --assemble-only   # 仅重跑 CSV
```

全量跨平台匹配流程见 `tools/video_match/README.md`。

---

## 十一、已知限制与后续

1. **图文帖**：yt-dlp 无法拉取无视频流帖子；当前 3 条未进入 caption。若需覆盖，可手动放入 `{id}.jpg` 并扩展 M3（单图一次标注，schema 对齐）——caption 侧易实现，拉图需 cookie 或原始爬虫图 URL。
2. **VLM 幻觉**：只要求「描述所见」；应用层仍建议 spot-check `segments` 与 `overview` 一致性。
3. **与帖子编码表联结**：`config/post_category_by_post.csv` 的 `机器人状态` / `人的形象` 为 **研究者事先编码**，可与 `config_captions.jsonl` 按 `id` = `帖子id` merge，用于对比视觉叙述与理论矩阵。
4. **模块可拆卸**：M3 为唯一 LLM 视觉成本；不满意可删脚本与 jsonl，不影响评论主题建模主线。

---

## 十二、正文可用稿（Methods 段落，草稿）

> 对于需读取帖子视频内容的任务，我们对每帖下载前 30 秒片段，并使用视觉语言模型（Qwen3-VL-30B，经 SiliconFlow API）进行 **dense video captioning**。视频按 5 秒分段；每段抽取两帧截图，模型在同一次结构化输出中完成全局描述、五维场景标注（场景、人物、动作、互动、时序）及异常检测，再经一次文本合并得到帖子级时序概述（`overview`）与分段摘要（`timeline`）。理论抽样帖（*N* = 34）中 31 帖成功获得视频 caption；3 帖因平台侧无视频流未能下载。该视觉描述与帖子级「机器人状态 × 人类角色」编码相互独立，可按帖子 ID 合并用于后续分析。
