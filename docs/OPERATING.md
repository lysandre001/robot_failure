# 操作说明（导入 · 清洗 · 分类 · 金标 · 新数据实验）

**To:** 同事（导入 / 标注 / 跑实验）  
**From:** 数据管线  

请先读本文 + [data/canonical_comment_schema.md](../data/canonical_comment_schema.md)。不要从 notebook 或 Drive 导出当主表。

## 三句话

1. 原始文件只放 `data/rawdata/{平台}/{批次}/`，不要改原文件。
2. 清洗只写 `data/clean/{平台}/{批次}/`，**一次只跑一个源**。
3. 现有主题结论 `2026-05-27_topic_merged_bge_hdbscan_sensitivity` **只读**。新数据要跑主题，必须新 `run_id`。

把文件丢进文件夹 **不会**自动英译、下视频、抽 demo、跑 BERTopic。要做哪步，自己敲哪条命令。

**批次名**（与赛事对齐）：马拉松 `2604-marathon`，运动会 `2608-olympic`。  
**平台名**（小写）：`xhs` / `tiktok` / `douyin` / `youtube`。

**真源速查**

| 角色 | 路径 |
|------|------|
| 原始抓取 | `data/rawdata/{platform}/{batch}/` |
| 评论主表 | `data/clean/{platform}/{batch}/clean_comments_unified.csv` |
| 帖子分类 | `config/post_category_by_post.csv` 或 `config/post_category/{platform}_{batch}.csv` |
| 人工金标 | `human_label_llm/label_data/gold/` |
| 主题实验 | `output/experiments/<run_id>/`（current 见 [CURRENT.md](../CURRENT.md)） |

---

## A. 导入：放表并对上 schema

**你做什么**

1. 建目录（示例 YouTube）：
   - `data/rawdata/youtube/2604-marathon/`
   - `data/rawdata/youtube/2608-olympic/`
2. 导出文件 **原样** 放入（csv/xlsx）。不要改列名、不要删行。
3. 打开 [data/canonical_comment_schema.md](../data/canonical_comment_schema.md) 宽表一节，在同目录写 `COLUMN_MAP.md`：左 = 导出列名，右 = canonical 中文列名。
4. 核对 **必填**：`帖子id`、`一级评论id`、`一级评论内容`；有二级时 `二级评论id`、`二级评论内容` 且能挂到 `一级评论id`。
5. 列对齐后：请工程同事写平台适配，或自行改列名后 **另存** `canonical.csv`（**不覆盖**原件）。

**宽表一行**：一行 = 一条一级；每个二级再占一行。YouTube 已有帖/一级/二级即可铺成此表。点赞、时间、作者、语言 **有就填，没有留空**。

**链接**：无 `帖子链接` 时 YouTube 可拼 `https://www.youtube.com/watch?v={帖子id}`。

**不要做**：翻译、抽 demo、改评论正文、把 raw 直接放进 `data/clean/`。

---

## B. 清洗：一条命令，验收三张表

在项目根目录（`.venv` 已激活）：

```bash
python run_preprocess.py --platform youtube --batch 2604-marathon \
  --input data/rawdata/youtube/2604-marathon/canonical.csv
```

运动会改 `2608-olympic` 与 `--input` 路径。  
TikTok / 抖音 / XHS 见 [CURRENT.md](../CURRENT.md) 或 [docs/functions.md](functions.md) §1。

**类型**：主线。  
**机器会做**：读宽表 → 去重展开长表 → Phase 1 过滤 → 写 clean → 写 `shared_analyzable_corpus.csv`。  
**不会**：跑 LDA/BERTopic、英译、demo、改 current 实验。

**验收**（打开 `data/clean/{platform}/{batch}/`）：

- `clean_comments_unified.csv`：`comment_level` 1/2，`platform`、`source_batch` 正确。
- `phase1_preprocess_stage_summary.csv`：各阶段行数。
- 帖数、L1 数、L2 数合理；**L2 突然为 0** → 查 `COLUMN_MAP` 的 parent/id，**不要**接着跑主题。

可选索引（不是实验）：

```bash
python -m tools.build_corpus_inventory
```

**不要做**：覆盖 `output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/`；不要把单源 clean 复制到 `data/clean/` 根目录当全库。

---

## C. 帖子内容分类：可先洗后标

分类是 **人填 config**，含义见 schema 第三节。  
小红书：[config/post_category_by_post.csv](../config/post_category_by_post.csv)。  
其他源建议：`config/post_category/youtube_2604-marathon.csv`（命名 `{platform}_{batch}.csv`）。

填 `帖子id`、`机器人状态`、`人的形象`（允许值见 schema）。未出现的帖在 clean 里仍是 `unknown`。

填完后 **不要重洗 raw**，只刷新标签：

```bash
python -m tools.refresh_clean_post_labels \
  --platform youtube --batch 2604-marathon
```

（等价于指定该目录下 `clean_comments_unified.csv` 与对应分类 csv。）

---

## D. Demo 抽样（探索，给人看/标）

`data/demo/` 不是主库。导出需指定源，见 [data/demo/README.md](../data/demo/README.md)。  
在 Google 表上 **只加标签列**，不要改 `comment_id` / `content` / `帖子id`。

---

## E. 人工金标入库

详见 [human_label_llm/label_data/GOLD_PROTOCOL.md](../human_label_llm/label_data/GOLD_PROTOCOL.md)。

摘要：交回 `human_label_llm/label_data/gold/{platform}_{batch}_YYYYMMDD.csv`，旁附 `NOTES.md`；gold 用 `comment_id` 与 clean 对齐，**不合并进** clean。

LLM 比对：复制 experiment yaml，改 `input_csv` 与 `run_id`，跑 `human_label_llm/run_experiment.py infer/compare。**不要**改 `_defaults.yaml`（旧 XHS sample10 入口）。

---

## G. 新数据跑主题 / 比较方法

YouTube（或其它源）洗完 **≠** 已做主题。current 仍是 XHS + 05-27 run。

1. 只用 **该源** `data/clean/{platform}/{batch}/clean_comments_unified.csv`。
2. 新 `run_id`，例如 `2026-09-19_youtube_2604-marathon_bge-m3`。
3. 在 [output/experiments/registry.csv](../output/experiments/registry.csv) 加一行；`status` 勿随意改成 `current`。
4. 探索命令：

```bash
PYTHONUNBUFFERED=1 ./.venv/bin/python -m phase1.topic_modeling \
  --run-id 2026-09-19_youtube_2604-marathon_bge-m3 \
  --input-csv data/clean/youtube/2604-marathon/clean_comments_unified.csv \
  --device cpu
```

5. 换编码器 / HDBSCAN / 停用词 → 再一个新 `run_id`，并排看各目录 `comparison.md`。
6. 英文为主勿默认 `bge-base-zh-v1.5`；模型写进该 run 的 `config.json`。
7. 输入用 clean/shared，**不用** demo、**不用** gold。

命令契约见 [docs/functions.md](functions.md) §7。
