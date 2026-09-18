# 人工金标（gold）交回协议

Gold 是 **评论标签真源**；评论文本真源仍是 `data/clean/{platform}/{batch}/clean_comments_unified.csv`。二者用 **`comment_id`** 对齐，禁止用 Excel 行号。

操作总览见 [docs/OPERATING.md](../../docs/OPERATING.md) §E。

## 目录与命名

- 交回文件：`human_label_llm/label_data/gold/{platform}_{batch}_YYYYMMDD.csv`  
  例：`tiktok_2604-marathon_20260919.csv`、`youtube_2604-marathon_20260920.csv`
- 同目录短说明：`NOTES.md`（标记者、基于哪份 demo/表、拿不准的规则）
- 可选：工程规范化后生成 `{同名}_canonical.csv`，**不覆盖**你交回的原件

## 禁止修改的列

交回前不要改：

- `comment_id`
- `content`
- `帖子id`

只 **新增或填写** 标签列。

## 评估对象 + 情感（当前主轨）

与 [human_label_llm](../README.md) 实验一致。

| 列 | 要求 |
|----|------|
| `评估对象` | 七类之一（中文）：机器人本身 / 自身经验 / 符号 / 事件 / 其他人 / 无主体 / 其他 |
| `情感` | `Positive` / `Negative` / `Neutral` / `Mixed`（**首字母大写**） |

若表头是 `情感(p/neg/n/m)`，入库规范化时改为 `情感`。

建议保留 demo 带来的上下文列（便于核对）：`post_category`、`human_category`、`combo`、`comment_level`、`parent_comment_id`、`帖子标题` 等。

## Codebook 4D（可选，可空）

同一 gold 表可预留列，供日后与 [tools/label_comments_llm.py](../../tools/label_comments_llm.py) 对照：`figure_code`、`stance`、`emotion_valence`、`d1`–`d4`。未标可不填，不挡对象/情感轨。

## 与 LLM 比对

1. 复制 `human_label_llm/experiment/` 下某 yaml，设 `data.input_csv` 指向本 gold 文件，新 `run_id`。
2. `python human_label_llm/run_experiment.py infer` → `compare`。
3. 产物在 `human_label_llm/output/<run_id>/`（κ、gap 表等）。
4. **不要**改 `experiment/_defaults.yaml`（保留旧 sample10 可复现）。
5. **不要**把 LLM 预测写回 gold 或 clean。

## 不要做什么

- 不要把 gold merge 进 `clean_comments_unified.csv`
- 不要用 demo 或 gold 作为 `phase1.topic_modeling` 的 `--input-csv`
- 不要覆盖他人已交回的 gold 文件名；新版本用新日期后缀
