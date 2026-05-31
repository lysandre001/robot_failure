# Human vs LLM 标注比对（极简 MVP）

## 一个 prompt 文件 + 一个 experiment yaml

- `prompt/{id}.md` — frontmatter（版本/描述/label_map，**不发给模型**）+ 正文
- `experiment/*.yaml` — **`data.input_csv`**、填槽列名、scopes、模型

**不拷贝中间 gold.csv**；`infer` / `compare` / `dryrun` 都直接读你指定的 `input_csv`。

```bash
python human_label_llm/experiment/20260529_object_v1_comment_only_test.py dryrun
python human_label_llm/experiment/20260529_object_v1_comment_only_test.py infer
python human_label_llm/experiment/20260529_object_v1_comment_only_test.py compare
```

产物仅在 `output/{run_id}/`：`log.jsonl`、`comparison_wide.csv`、`eval_summary.csv`（含 macro_recall）、`eval_by_category.csv`、`eval_gap_pairs.csv`、`eval_gap_by_class.csv`、`run.yaml`。

## experiment yaml

```yaml
data:
  input_csv: human_label_llm/label_data/your_file.csv

columns:
  comment: content
  gold: 评估对象

gold_column: 评估对象
prompt: eval_object_v1
```

若配置了 `posts_csv` + `posts_join`，会在读取时 merge 帖子正文（仍不写中间文件）。
