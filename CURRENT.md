# 当前工作入口

> 人和 agent：**改数据或重跑实验前先读本文 + [docs/OPERATING.md](docs/OPERATING.md) + [docs/functions.md](docs/functions.md)**。  
> 字段含义：[data/canonical_comment_schema.md](data/canonical_comment_schema.md)。

## 人机合作规则

1. **清洗只写** `data/clean/`；**实验只写** `output/experiments/<run_id>/`（新 run 用新 `run_id`，勿覆盖 current）。
2. 新实验必须在 [output/experiments/registry.csv](output/experiments/registry.csv) 登记；`config.json` 记录 input SHA。
3. **不要**从 `output/experiments/_archived/` 或 notebook 默认路径当 canonical。
4. `embeddings.npy` 与 `shared_analyzable_corpus.csv` **按行序对齐**；改 shared 必须重跑 `phase1.topic_modeling` encode。
5. 功能细节（输入/输出/假设）以 [docs/functions.md](docs/functions.md) 为准。

## 当前数据真源

| 角色 | 路径 |
|------|------|
| **跨平台总表** | [data/corpus_inventory.csv](data/corpus_inventory.csv) |
| XHS 清洗主表 | [data/clean/xhs/merged/clean_comments_unified.csv](data/clean/xhs/merged/clean_comments_unified.csv)（N=41,251；根目录 symlink） |
| XHS shared | [data/clean/xhs/merged/shared_analyzable_corpus.csv](data/clean/xhs/merged/shared_analyzable_corpus.csv)（门控 v1：N=30,762；05-27 实验冻结在旧 N=26,811） |
| 评论纳入规则 | [data/clean/comment_quality_gate_rules.md](data/clean/comment_quality_gate_rules.md) |
| TikTok 2604-marathon | [data/clean/tiktok/2604-marathon/clean_comments_unified.csv](data/clean/tiktok/2604-marathon/clean_comments_unified.csv) |
| TikTok 2608-olympic | [data/clean/tiktok/2608-olympic/clean_comments_unified.csv](data/clean/tiktok/2608-olympic/clean_comments_unified.csv) |
| 抖音 2608-olympic | [data/clean/douyin/2608-olympic/clean_comments_unified.csv](data/clean/douyin/2608-olympic/clean_comments_unified.csv) |
| YouTube 2604-marathon | [data/clean/youtube/2604-marathon/clean_comments_unified.csv](data/clean/youtube/2604-marathon/clean_comments_unified.csv) |
| YouTube 2608-olympic | [data/clean/youtube/2608-olympic/clean_comments_unified.csv](data/clean/youtube/2608-olympic/clean_comments_unified.csv) |
| Raw 布局 | `data/rawdata/{xhs,tiktok,douyin,youtube}/` |
| 操作说明（同事） | [docs/OPERATING.md](docs/OPERATING.md) |
| Schema（全平台） | [data/canonical_comment_schema.md](data/canonical_comment_schema.md) |
| 人工金标 | [human_label_llm/label_data/GOLD_PROTOCOL.md](human_label_llm/label_data/GOLD_PROTOCOL.md) → `label_data/gold/` |
| 帖子标签 | XHS：[config/post_category_by_post.csv](config/post_category_by_post.csv)；其它源：`config/post_category/{platform}_{batch}.csv` |
| 噪音规则 | [config/topic_modeling/comment_content_filter.json](config/topic_modeling/comment_content_filter.json) |
| 英文停用词 | [config/topic_modeling/general_stopwords_en.txt](config/topic_modeling/general_stopwords_en.txt)（仅 LDA/NMF 主题词，不用于评论纳入） |
| 预处理说明 | [data/clean/data_preprocessing_protocol.md](data/clean/data_preprocessing_protocol.md) |
| **帖子视听元数据** | [data/clean/post_media.csv](data/clean/post_media.csv)（caption + ASR；旁路，非评论主表） |

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

## 新数据最短路径（统一管线）

```bash
# XHS merged
python run_preprocess.py --platform xhs --batch merged \
  --input data/rawdata/小红书帖子数据_merged.xlsx

# TikTok / 抖音（宽表 CSV；抖音 43 列自动映射）
python run_preprocess.py --platform tiktok --batch 2604-marathon \
  --input data/rawdata/tiktok/2604-marathon/<export>.csv
python run_preprocess.py --platform tiktok --batch 2608-olympic \
  --input data/rawdata/tiktok/2608-olympic/<export>.csv
python run_preprocess.py --platform douyin --batch 2608-olympic \
  --input data/rawdata/douyin/2608-olympic/<export>.csv

# YouTube（canonical 宽表；帖子分类 config/post_category/youtube_{batch}.csv）
python run_preprocess.py --platform youtube --batch 2604-marathon \
  --input data/rawdata/youtube/2604-marathon/canonical.csv
python run_preprocess.py --platform youtube --batch 2608-olympic \
  --input data/rawdata/youtube/2608-olympic/canonical.csv

# 评论语言 + 英译（写回 clean 长表；BGE/主题仍用原文 content）
python -m tools.comment_lang.run --platform youtube --batch 2604-marathon --detect-only
python -m tools.comment_lang.run --platform youtube --batch 2604-marathon

# 跨平台 inventory
python -m tools.build_corpus_inventory

# 主题建模（新平台/新源必须新 run_id；勿覆盖 current）
PYTHONUNBUFFERED=1 ./.venv/bin/python -m phase1.topic_modeling \
  --run-id YYYY-MM-DD_<platform>_<batch>_<方法要点> \
  --input-csv data/clean/<platform>/<batch>/clean_comments_unified.csv \
  --device cpu
```

新数据细节见 [docs/OPERATING.md](docs/OPERATING.md) §G。跑完后：**更新本文「当前实验真源」与 registry.csv**（除非只是探索 run，勿改 `status=current`）。
