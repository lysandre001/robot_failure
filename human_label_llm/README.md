# Human vs LLM 标注比对（极简 MVP）

## 统一启动

```bash
# 评估对象（object）
python human_label_llm/run_experiment.py dryrun object
python human_label_llm/run_experiment.py infer object
python human_label_llm/run_experiment.py compare object

# 情感（emotion）
python human_label_llm/run_experiment.py infer emotion
python human_label_llm/run_experiment.py all emotion

# 评论 + 视频 dense caption（object_caption / emotion_caption）
python human_label_llm/run_experiment.py dryrun object_caption
python human_label_llm/run_experiment.py infer emotion_caption

# 或指定 yaml
python human_label_llm/run_experiment.py infer -c human_label_llm/experiment/20260530_emotion_v1_comment_only_test.yaml
```

**模型 / 并发 / 数据路径** 在 `experiment/_defaults.yaml` 统一配置；各 experiment yaml 只写 `run_id`、`prompt`、`gold_column` 等任务差异。

加多模型：在 `_defaults.yaml` 的 `model_catalog` 里注册，再改 `model_keys` 列表。单个 experiment 也可覆盖 `model_keys`：

```yaml
extends: _defaults.yaml
run_id: my_run
model_keys:
  - deepseek_v4_pro
  - gpt_5_5
prompt: eval_emotion_v1
...
```

## 结构

- `prompt/` — 与 experiment 同名的两套 prompt（`*_comment_only` / `*_comment_caption`），互不混用
- `experiment/_defaults.yaml` — 共享 data、models、runtime
- `experiment/*.yaml` — 任务配置（`extends: _defaults.yaml`），`prompt:` 字段指向对应 md

| 别名 | prompt | 输入 |
|------|--------|------|
| `object` | `eval_object_v1_comment_only` | 仅评论 |
| `object_caption` | `eval_object_v1_comment_caption` | 评论 + `config_captions.jsonl` |
| `emotion` | `eval_emotion_v1_comment_only` | 仅评论 |
| `emotion_caption` | `eval_emotion_v1_comment_caption` | 评论 + caption |

产物在 `output/{run_id}/`：`log.jsonl`、`comparison_wide.csv`、`eval_summary.csv`、`eval_by_category.csv`、`eval_gap_pairs.csv`、`eval_gap_by_class.csv`、`run.yaml`。

## 新建 experiment

```yaml
extends: _defaults.yaml
run_id: 20260531_my_task
columns:
  gold: 金标列名
gold_column: 金标列名
prompt: eval_object_v1_comment_only
```

若配置了 `posts_csv` + `posts_join`，会在读取时 merge 帖子正文（仍不写中间文件）。
