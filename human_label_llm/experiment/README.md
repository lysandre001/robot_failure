# LLM 打标实验（yaml 真源 + registry 索引）

导航：[README.md](../../README.md) · 协议/码本：[docs/registry.md](../../docs/registry.md) · 数据契约：Schema §4–§6。

## 原则

- **可复现真源**：本目录下 `*.yaml` + `../prompt/*.md` + `_defaults.yaml`。
- **索引**：每开新 run，在 [registry.csv](registry.csv) 加一行（论文引用 run_id 以此为准）。
- **禁止**：改 `_defaults.yaml`（冻结旧 XHS sample10）；LLM 预测写回 `data/clean/`。

## 新建实验

1. 复制 [`_labeling_template.yaml`](_labeling_template.yaml) → `YYYY-MM-DD_{platform}_{batch}_{layer}_v1.yaml`
2. 填写 `run_id`（与 yaml 文件名建议一致）、`platform`、`layer`、`gold_column`、`data.input_csv`
3. 登记 [registry.csv](registry.csv)
4. 跑通：

```bash
python human_label_llm/run_experiment.py dryrun -c human_label_llm/experiment/<your>.yaml
python human_label_llm/run_experiment.py infer -c human_label_llm/experiment/<your>.yaml
python human_label_llm/run_experiment.py compare -c human_label_llm/experiment/<your>.yaml
```

## Yaml 字段契约

### 继承

| 键 | 说明 |
|----|------|
| `extends` | 固定 `_defaults.yaml` |
| `run_id` | 产物子目录名 |

### 任务与数据

| 键 | 说明 |
|----|------|
| `platform` | `xhs` \| `douyin` \| `tiktok` \| `youtube` → 文本列与 prompt 语言（见 `labeling_paths.py`） |
| `layer` | `subject` \| `emotion` \| `stance` → 默认 prompt `{layer}_{zh\|en}.md` |
| `prompt_lang` | 可省略，由 platform 推断 |
| `prompt` | 显式 prompt id（对应 `prompt/{id}.md`）；省略则用 layer+语言 |
| `gold_column` | κ 比对列（如 `主体`、`情感`、`stance`） |
| `data.input_csv` | gold 或带金标的抽样 CSV |
| `data.text_column` | 通常省略；tiktok/youtube → `content_en` |
| `columns` | 槽位映射：`comment_id`, `comment`, `title`, `caption`, `gold` |
| `scopes` / `scope_slots` | 填 prompt 模板槽（如 `scope_comment_only: [comment]`） |
| `output_root` | 新任务建议 `output/label_runs`；省略则 `human_label_llm/output/` |

### Prompt 文件

`human_label_llm/prompt/*.md`：YAML frontmatter（`id`, `version`, `label_map`, `output.json_field`）+ 正文模板。  
解析与填槽：`human_label_llm/prompts.py`。

### 超参（默认在 `_defaults.yaml`，experiment 可覆盖）

| 键 | 含义 |
|----|------|
| `model_catalog` | 模型池定义 |
| `model_keys` | 本 run 使用的 catalog 键列表 |
| `temperature` | 默认 0.0 |
| `max_tokens` | 默认 2048 |
| `concurrency` | 并行请求数 |
| `timeout` | 秒 |
| `limit` | 冒烟条数；全量 `null` |

### 输出（Schema §6）

`{output_root}/{run_id}/`：推断宽表、compare 指标、checkpoint jsonl（按 `comment_id` resume）。  
`parse_ok=false` 时不填默认类（见 registry → `llm_labeling_design`）。

## Legacy yaml

20260529–20260531 实验见 [registry.csv](registry.csv)，`status=frozen`，产物在 `human_label_llm/output/<run_id>/`。
