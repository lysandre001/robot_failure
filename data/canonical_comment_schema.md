# Data schema & contracts（XHS / TikTok / 抖音 / YouTube）

> **字段与阶段 I/O 契约**。操作命令见 [README.md](../README.md)；协议与码本索引见 [docs/registry.md](../docs/registry.md)。

## 宽表一行是什么

与 TikTok、小红书导出相同：**一行 = 一条一级评论**；若该一级下有二级回复，**每个二级再占一行**，帖子字段与一级字段在行内重复。没有二级的一级只占一行，二级相关列为空。

YouTube 导出通常已有帖子、一级、二级；作者、点赞、时间、话题、语言等 **有则填、无则留空**，不影响清洗。缺 **必填** 列则不能进 Phase 1。

---

## 1. 宽表导入列（raw → canonical）

实现参照 [phase1/douyin_io.py](../phase1/douyin_io.py) 中 `CANONICAL_COLS`（31 核心 + 6 语言可选）。

### 1.1 帖子级（同一视频/帖子多行重复）

| 列名 | 必填 | 含义 | 平台说明 |
|------|------|------|----------|
| `帖子id` | 是 | 帖子唯一键 | XHS/TikTok 多为数字字符串；YouTube 为 video id（约 11 位，可含字母） |
| `帖子链接` | 否 | 可打开链接 | 无则 YouTube 可拼 `https://www.youtube.com/watch?v={帖子id}` |
| `用户id` | 否 | 作者/频道 id | |
| `帖子用户名` | 否 | 作者/频道名 | |
| `帖子类型` | 否 | 内容类型 | 视频建议填 `video` |
| `帖子标题` | 否 | 标题 | 与正文至少一项有值更利于读帖与分类 |
| `帖子发布时间` | 否 | 发布时间 | |
| `帖子正文` | 否 | 正文/简介 description | |
| `帖子话题` | 否 | hashtag 等 | |
| `帖子IP属地` | 否 | IP 属地 | YouTube 通常无 |
| `帖子评论数` | 否 | 帖子级评论数 | 可与 clean 内实际数不一致 |
| `帖子点赞数` | 否 | 点赞 | |
| `帖子转发数` | 否 | 转发/分享 | |
| `帖子收藏数` | 否 | 收藏 | |

### 1.2 一级评论（每行至少有一级）

| 列名 | 必填 | 含义 |
|------|------|------|
| `一级评论id` | 是 | 一级评论唯一键；无稳定 id 时由适配层用内容+时间等哈希生成 |
| `一级评论内容` | 是 | 一级正文 |
| `一级评论用户名` | 否 | |
| `一级评论用户id` | 否 | |
| `一级评论时间` | 否 | |
| `一级评论地址` | 否 | 地点/IP |
| `一级评论点赞数` | 否 | |
| `一级评论回复数` | 否 | raw 计数；clean 内 L2 数以 `parent_comment_id` 为准 |
| `一级评论图片链接` | 否 | |
| `一级评论语言` | 否 | ISO 639-1，如 `en` / `zh` |
| `一级评论混合` | 否 | `0` / `1` |
| `一级评论英文` | 否 | 英译；不跑翻译可空 |

### 1.3 二级评论（该行无回复则下列全空）

| 列名 | 必填 | 含义 |
|------|------|------|
| `二级评论id` | 有回复时必填 | |
| `二级评论内容` | 有回复时必填 | |
| `二级评论用户名` | 否 | |
| `二级评论用户id` | 否 | |
| `二级评论时间` | 否 | |
| `二级评论地址` | 否 | |
| `二级评论点赞数` | 否 | |
| `二级评论图片链接` | 否 | |
| `二级评论语言` | 否 | |
| `二级评论混合` | 否 | |
| `二级评论英文` | 否 | |

**有二级时**：同一行必须能对应到所属的 `一级评论id`（宽表行结构已包含一级列）。

### 1.4 YouTube 列映射

导出列名因工具而异。在同目录写 `COLUMN_MAP.md`（左：导出列名，右：上表 canonical 列名）。映射后另存 `canonical.csv`，**不覆盖**原始抓取文件。

---

## 2. 清洗后长表（`clean_comments_unified.csv`）

一条评论一行，由 Phase 1 从宽表展开。

| 列名 | 含义 |
|------|------|
| `帖子id` | 与宽表一致 |
| `post_category` | `{机器人状态}\|{人的形象}`；未分类为 `unknown` |
| `robot_status` | 来自帖子分类表 |
| `human_role` | 来自帖子分类表 |
| `帖子标题` | |
| `帖子点赞数` / `帖子评论数` | 帖子级互动 |
| `comment_level` | `1` 或 `2` |
| `comment_id` | 对应宽表 `一级评论id` 或 `二级评论id` |
| `parent_comment_id` | 二级指向一级 `comment_id`；一级为空 |
| `content` | 评论正文 |
| `comment_time` | |
| `like_count` / `reply_count` | |
| `char_len` | 规范化后长度 |
| `platform` | 如 `xhs` / `tiktok` / `douyin` / `youtube` |
| `source_batch` | 如 `merged` / `2604-marathon` / `2608-olympic` |
| `language` / `is_mixed` / `content_en` | 若宽表有语言列则保留 |

同目录还有 `shared_analyzable_corpus.csv`（主题/嵌入用的更严子集，规则见 [comment_quality_gate_rules.md](clean/comment_quality_gate_rules.md)）。

**不含于 public clean**（IRB 8a）：`user_id`、评论 `location`（IP/地址）、一切用户昵称。技术用字段写入 **`comment_pii_sidecar.csv`**（与 public 表同目录，仅本地、不入库发表；见 [public_observation_deidentify.md](../docs/protocols/public_observation_deidentify.md)）。

宽表 raw 仍可含 `一级评论用户id` / `一级评论地址` 等，管线在写出 clean 前剥离。

---

## 3. 帖子内容分类表（config，人填）

不是模型输出。文件名建议：`config/post_category/{platform}_{batch}.csv`；小红书沿用 [config/post_category_by_post.csv](../config/post_category_by_post.csv)。

| 列名 | 必填 | 含义 |
|------|------|------|
| `帖子id` | 是 | 必须与 clean 中 `帖子id` 一致 |
| `机器人状态` | 是 | 仅允许：**失败** / **弱势** / **常态** / **强势** / **混合** |
| `人的形象` | 是 | 仅允许：**服务照护** / **被超越者** / **观众** |
| `帖子链接` | 否 | 便于人工核对 |

写入 clean 时：`post_category` = `机器人状态|人的形象`，并拆成 `robot_status`、`human_role`（与 config 三档一致）。读入时若遇历史取值 **保护者 / 抢救者 / 服务者**，管线会归并为 **服务照护**（见 [`phase1/post_category_labels.py`](../phase1/post_category_labels.py) 的 `normalize_human_role`）。

### 3.1 预留扩展列（后补 3 类）

类目名称未定前，可在分类表右侧 **加列**并在本节补充含义；**不要**写入 `post_category` 的 `|` 拼接，直到组内统一命名。Phase 1 透传这些列到 clean 即可（落地适配后生效）。

---

## 4. 人工金标（gold CSV）

| 项 | 约定 |
|----|------|
| **Path** | `human_label_llm/label_data/gold/{platform}_{batch}_YYYYMMDD.csv` |
| **Primary key** | `comment_id`（与 clean 一致） |
| **Must not edit** | `comment_id`, `content`, `帖子id`（及已有 `content_en`） |
| **Label columns** | 见 registry → `comment_three_layer` + [GOLD_PROTOCOL](../human_label_llm/label_data/GOLD_PROTOCOL.md)（`主体`, `stance`, `d1`–`d4`, `情感`；列 alias 见 [label_map.yaml](../config/codebook/label_map.yaml)） |
| **Written by** | 人工标注交回 |
| **Read by** | `run_experiment.py`, `tools.codebook_analysis` |
| **Must not** | 合并进 `clean_comments_unified.csv` |

---

## 5. Pipeline artifacts

| 文件 | Path pattern | 含义 |
|------|----------------|------|
| PII sidecar | `data/clean/{platform}/{batch}/comment_pii_sidecar.csv` | `comment_id` + `user_id` + `location`；**非**发表/demo/gold 输入 |
| Stage summary | `data/clean/{platform}/{batch}/phase1_preprocess_stage_summary.csv` | 各过滤阶段行数 |
| QC markdown | 同目录 `phase1_*.md`（若生成） | 人类可读 QC |
| Filter report | `comment_content_filter_report.json` | 噪音规则命中统计 |
| Shared 规则 | [comment_quality_gate_rules.md](clean/comment_quality_gate_rules.md) | 门控版本 |
| Inventory | `data/corpus_inventory.csv` | 跨平台 clean 索引（`tools.build_corpus_inventory`） |

---

## 6. Gold & label runs

| 项 | 约定 |
|----|------|
| **Experiment 真源** | `human_label_llm/experiment/*.yaml` + `prompt/*.md`（见 [experiment/README.md](../human_label_llm/experiment/README.md)） |
| **Registry** | `human_label_llm/experiment/registry.csv` |
| **Output path** | `{output_root}/{run_id}/`；默认新任务 `output/label_runs/`；legacy `human_label_llm/output/` |
| **Input CSV** | gold 或抽样；须含 yaml `columns` 映射的列 |
| **Text for model** | xhs/douyin → `content`；tiktok/youtube → `content_en`（`labeling_paths.py`） |
| **Checkpoint** | jsonl by `comment_id`；`parse_ok=false` 不填默认类 |
| **Must not** | 预测写回 clean / gold |

---

## 7. Topic experiments

| 项 | 约定 |
|----|------|
| **Path** | `output/experiments/<run_id>/` |
| **Registry** | `output/experiments/registry.csv`（`status=current` 仅一行） |
| **Config** | `config.json` 含 input SHA、`n_shared` 等 |
| **Embeddings** | `embeddings.npy` 行序与当次 `shared_analyzable_corpus.csv` **严格对齐** |
| **Current frozen** | `2026-05-27_topic_merged_bge_hdbscan_sensitivity` @ N=26,811 — **不可**与现 XHS 30,762 混用 |
| **Written by** | `phase1.topic_modeling`, `run_topic_discovery` 等 |
| **Must not** | 覆盖 current 目录；用 demo/gold 作 encode 输入 |

---

## 8. Analysis outputs

| 项 | 约定 |
|----|------|
| **Path** | `output/analysis/<analysis_id>/` |
| **Input** | labels CSV + `data/clean/{platform}/{batch}/clean_comments_unified.csv` |
| **Join key** | `comment_id` |
| **Post strata** | `robot_status`, `human_role` from clean |
| **Tool** | `python -m tools.codebook_analysis` |

---

## 9. Cross-cutting rules

| 规则 | 说明 |
|------|------|
| Clean 真源 | 仅 `data/clean/{platform}/{batch}/`；根目录 symlink 指向 xhs/merged |
| Derived | `output/phase1/` 为 legacy/拷贝 QC，**非** canonical |
| Demo | `data/demo/` 仅供浏览/抽样，非 topic/label 主输入 |
| Post media | `data/clean/post_media.csv` 旁路视听元数据，非评论主表 |
| 帖子分类 loader | `phase1.post_category_labels.load_post_category_table` |
