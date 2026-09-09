# 当前工作入口

> 人和 agent：**改数据或重跑实验前先读本文 + [docs/functions.md](docs/functions.md)**。

## 人机合作规则

1. **清洗只写** `data/clean/`；**实验只写** `output/experiments/<run_id>/`（新 run 用新 `run_id`，勿覆盖 current）。
2. 新实验必须在 [output/experiments/registry.csv](output/experiments/registry.csv) 登记；`config.json` 记录 input SHA。
3. **不要**从 `output/experiments/_archived/` 或 notebook 默认路径当 canonical。
4. `embeddings.npy` 与 `shared_analyzable_corpus.csv` **按行序对齐**；改 shared 必须重跑 `phase1.topic_modeling` encode。
5. 功能细节（输入/输出/假设）以 [docs/functions.md](docs/functions.md) 为准。

## 当前数据真源

| 角色 | 路径 |
|------|------|
| 清洗主表 | [data/clean/clean_comments_unified.csv](data/clean/clean_comments_unified.csv)（N=41,251） |
| shared corpus | [data/clean/shared_analyzable_corpus.csv](data/clean/shared_analyzable_corpus.csv)（N=26,811） |
| 帖子标签 | [config/post_category_by_post.csv](config/post_category_by_post.csv) |
| 噪音规则 | [config/topic_modeling/comment_content_filter.json](config/topic_modeling/comment_content_filter.json) |
| 预处理说明 | [data/clean/data_preprocessing_protocol.md](data/clean/data_preprocessing_protocol.md) |

## 当前实验真源

| 字段 | 值 |
|------|-----|
| **run_id** | `2026-05-27_topic_merged_bge_hdbscan_sensitivity` |
| **目录** | [output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/](output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/) |
| **registry** | `status=current` |
| **L1 discovery** | `topic_discovery_l1/`（89 topics，nr=90，mcs=30） |
| **L2 discovery** | `topic_discovery_l2/`（44 topics，nr=45，mcs=30） |
| **历史 run** | [output/experiments/_archived/](output/experiments/_archived/)（只作对照，非当前结论） |

## 下一步（人工）

1. 标注 L1：`topic_discovery_l1/coder1_sheet_final_nr90.csv`
2. 标注 L2：`topic_discovery_l2/coder1_sheet_final_nr45.csv`
3. 完成后：`phase1.run_topic_discovery --step agreement` → 仲裁 → `--step backfill`

SOP：[writing/topic_discovery_intern_runbook.md](writing/topic_discovery_intern_runbook.md)

## 新数据最短路径

```bash
# 若为新批次脏 CSV，先入库（一次性）
python -m tools.ingest_xhs_batch2_csv
python -m tools.merge_xhs_batches_xlsx

# 清洗 → shared → 主题建模（新 run_id）
python run_preprocess.py --xlsx data/rawdata/小红书帖子数据_merged.xlsx
python -m tools.export_shared_analyzable_corpus
PYTHONUNBUFFERED=1 ./.venv/bin/python -m phase1.topic_modeling \
  --run-id YYYY-MM-DD_<描述> \
  --input-csv data/clean/clean_comments_unified.csv \
  --device cpu
```

跑完后：**更新本文「当前实验真源」与 registry.csv**。
