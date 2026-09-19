# 人工金标（gold）交回协议

Gold 是 **评论标签真源**；评论文本真源仍是 `data/clean/{platform}/{batch}/clean_comments_unified.csv`。二者用 **`comment_id`** 对齐，禁止用 Excel 行号。

码本三层定义：[config/codebook/codebook.md](../../config/codebook/codebook.md)（索引 [docs/registry.md](../../docs/registry.md)）。操作见 [README.md](../../README.md) Cookbook · 数据契约 Schema §4。

## 目录与命名

- 交回：`human_label_llm/label_data/gold/{platform}_{batch}_YYYYMMDD.csv`
- 说明：`NOTES.md`（标记者、基于哪份 demo/表、拿不准的规则）
- 可选：工程生成 `{同名}_canonical.csv`，**不覆盖**原件

## 禁止修改的列

- `comment_id`, `content`, `帖子id`（以及 `content_en` 若存在）

只 **新增或填写** 标签列。

## 三层标签（论文主测量）

### 主体

列名 **`主体`**（兼容 **`评估对象`**）。七类中文封闭标签见 codebook §1。

### 观念

- **`stance`**：`支持` | `反对` | `中立`
- **`d1`–`d4`**：各 `Pos` | `Neg` | `N/A`
- 可选 **`figure_code`**：见 [data/clean/label_codebook_llm.md](../../data/clean/label_codebook_llm.md)

### 情感

列名 **`情感`**（兼容 `情感(p/neg/n/m)`）：`Positive` / `Negative` / `Neutral` / `Mixed`。

可只交部分层（例如先主体+情感）；未标列留空。

## 语言与抽样

- **xhs / douyin**：人工对照 **`content`**
- **tiktok / youtube**：人工可对照 **`content`**；LLM 跑 **`content_en`**（需先 `tools.comment_lang`）

抽样可从 demo 浏览，但 gold 文件必须含 `comment_id` 且与 clean 一致。

## 与 LLM 比对

1. 复制 [experiment/_labeling_template.yaml](../experiment/_labeling_template.yaml) → 新 `run_id`，设 `platform`、`data.input_csv`、``gold_column`。
2. `python human_label_llm/run_experiment.py dryrun …` → `infer` → `compare`
3. 产物：`output/label_runs/<run_id>/`（κ、gap 表）
4. **不要**改 `experiment/_defaults.yaml`；**不要**把 LLM 预测写回 gold/clean

## 不要做什么

- 不要把 gold merge 进 `clean_comments_unified.csv`
- 不要用 demo/gold 作为 `phase1.topic_modeling` 的 `--input-csv`
- 不要覆盖他人 gold 文件名；新版本用新日期后缀
