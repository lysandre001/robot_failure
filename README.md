# robot_failure — 公共场景机器人评论研究管线

多平台评论清洗、主题探索、三层码本打标与论文分析。改数据或重跑实验前读本文 **Current snapshot** + [Data schema](data/canonical_comment_schema.md) + [Registry（协议/码本）](docs/registry.md)。

## Start here

| 文档 | 读什么 |
|------|--------|
| **本 README** | 目录、模块分层、Cookbook 命令、当前真源与下一步 |
| [data/canonical_comment_schema.md](data/canonical_comment_schema.md) | 字段定义、阶段路径、主键、禁止写回 |
| [docs/registry.md](docs/registry.md) | GOLD 协议、门控、各类码本、实验登记入口 |

**禁止**：LLM 预测写回 clean；gold 合并进 unified；混用 05-27 embeddings（N=26,811）与现 XHS shared（N=30,762）；从 notebook / `output/phase1/` 当 canonical。

**人机规则**

1. 清洗只写 `data/clean/{platform}/{batch}/`；主题只写 `output/experiments/<run_id>/`（新 run 新 id）。
2. 标签只写 `human_label_llm/label_data/gold/` 与 `output/label_runs/<run_id>/`。
3. 主题实验登记 [output/experiments/registry.csv](output/experiments/registry.csv)；LLM 实验登记 [human_label_llm/experiment/registry.csv](human_label_llm/experiment/registry.csv)。
4. `embeddings.npy` 与 shared **行序对齐**；改 shared 须重跑 encode。

---

## Layout

```
robot_failure/
├── README.md
├── run_preprocess.py
├── config/codebook/          # 评论三层码本
├── config/post_category/     # 帖子情境标签
├── data/rawdata/             # 原始导出（不改原件）
├── data/clean/{platform}/{batch}/   # 评论文本真源
├── human_label_llm/          # gold + experiment yaml + run_experiment.py
├── output/experiments/       # 主题实验
├── output/label_runs/        # LLM 打标产物
├── output/analysis/          # 码本 × 帖子分类表
├── phase1/                   # 清洗与 topic 代码
└── tools/                    # comment_lang、demo、附录脚本
```

**不入库**（见 [.gitignore](.gitignore)）：`data/rawdata/**` 大文件、`data/clean/**/*.csv`、`output/**` 产物、`notebooks/**`。

**批次**：`2604-marathon` / `2608-olympic`。 **平台**：`xhs` / `tiktok` / `douyin` / `youtube`。

`data/clean/` 根目录若干文件为 **symlink → xhs/merged**；勿读旧副本。

---

## Modules by tier

| 层级 | 入口 | 产物 |
|------|------|------|
| **mainline** | `run_preprocess.py` | `data/clean/{platform}/{batch}/` |
| **mainline** | `python -m tools.comment_lang.run` | clean 增 `language`, `content_en` |
| **mainline** | `python -m tools.refresh_clean_post_labels` | 刷新 `robot_status` / `human_role` |
| **mainline** | `python -m tools.build_corpus_inventory` | `data/corpus_inventory.csv` |
| **explore** | `python -m phase1.topic_modeling` | `output/experiments/<run_id>/` |
| **explore** | `python human_label_llm/run_experiment.py` | `output/label_runs/<run_id>/` 或 legacy `human_label_llm/output/` |
| **explore** | `python -m tools.codebook_analysis` | `output/analysis/<id>/` |
| **explore** | `python -m tools.post_category_appendix` | LaTeX/CSV 附录 |
| **explore** | `python -m tools.export_demo_*` | `data/demo/` |
| **once** | `tools.ingest_xhs_batch2_csv`, `merge_xhs_batches_xlsx` | raw / merged xlsx |
| **archived** | `tools.label_comments_llm`, `phase1/llm_stance/` | 勿开新跑 |

---

## Cookbook

### Import raw

1. `data/rawdata/{platform}/{batch}/` 原样放导出文件。
2. 写 `COLUMN_MAP.md`，列对齐 [Schema §1](data/canonical_comment_schema.md)。
3. 另存 `canonical.csv`，不覆盖原件。

### Preprocess

```bash
python run_preprocess.py --platform youtube --batch 2604-marathon \
  --input data/rawdata/youtube/2604-marathon/canonical.csv
```

验收：`clean_comments_unified.csv`（**无** `user_id` / `location`）、`phase1_preprocess_stage_summary.csv`、L1/L2 合理。  
PII 侧车：`comment_pii_sidecar.csv`（仅本地质控，见 [docs/protocols/public_observation_deidentify.md](docs/protocols/public_observation_deidentify.md)）。含 `@` 评论在过滤阶段整句排除（`comment_content_filter.json`）。

### Language + post labels + inventory

```bash
python -m tools.comment_lang.run --platform youtube --batch 2604-marathon
python -m tools.refresh_clean_post_labels --platform youtube --batch 2604-marathon
python -m tools.build_corpus_inventory
```

### Post category（人填 config）

`config/post_category/{platform}_{batch}.csv` 或 XHS `config/post_category_by_post.csv` → 再跑 `refresh_clean_post_labels`。

### Gold + LLM labeling

1. 交回 gold：见 [GOLD_PROTOCOL](human_label_llm/label_data/GOLD_PROTOCOL.md)。
2. 复制 [human_label_llm/experiment/_labeling_template.yaml](human_label_llm/experiment/_labeling_template.yaml) → 新 yaml。
3. **登记** [human_label_llm/experiment/registry.csv](human_label_llm/experiment/registry.csv)。
4. xhs/douyin → `content` + 中文 prompt；tiktok/youtube → `content_en` + 英文 prompt。

```bash
python human_label_llm/run_experiment.py dryrun -c human_label_llm/experiment/<your>.yaml
python human_label_llm/run_experiment.py infer -c human_label_llm/experiment/<your>.yaml
python human_label_llm/run_experiment.py compare -c human_label_llm/experiment/<your>.yaml
```

字段说明：[human_label_llm/experiment/README.md](human_label_llm/experiment/README.md)。

### Codebook × post category（论文表）

```bash
python -m tools.codebook_analysis \
  --labels human_label_llm/label_data/gold/youtube_2604-marathon_YYYYMMDD.csv \
  --platform youtube --batch 2604-marathon
```

### New topic run

登记 `output/experiments/registry.csv`，新 `run_id`，勿覆盖 current：

```bash
PYTHONUNBUFFERED=1 python -m phase1.topic_modeling \
  --run-id 2026-09-19_youtube_2604-marathon_bge-m3 \
  --input-csv data/clean/youtube/2604-marathon/clean_comments_unified.csv \
  --device cpu
```

---

## Current snapshot

| 角色 | 路径 |
|------|------|
| 跨平台索引 | [data/corpus_inventory.csv](data/corpus_inventory.csv) |
| XHS clean / shared | [data/clean/xhs/merged/](data/clean/xhs/merged/)（shared **N≈30,762**，门控 v1） |
| 其它平台 | `data/clean/{platform}/{batch}/clean_comments_unified.csv` |
| 人工金标 | `human_label_llm/label_data/gold/` |
| LLM runs | `output/label_runs/<run_id>/`（见 [label registry](human_label_llm/experiment/registry.csv)） |

**主题 current（只读）**：`2026-05-27_topic_merged_bge_hdbscan_sensitivity` — 冻结 shared **N=26,811**；禁止与现 30,762 混用 `embeddings.npy`。

**下一步（标注优先）**

1. Gold 入库 `{platform}_{batch}_YYYYMMDD.csv`。
2. 新 yaml + registry 行 → dryrun / infer / compare。
3. `codebook_analysis` 出横切表。

Discovery coder：[writing/topic_discovery_intern_runbook.md](writing/topic_discovery_intern_runbook.md)（与评论码本并行）。

---

## Further reading

- [docs/registry.md](docs/registry.md) — 协议与码本索引
- [phase1/RUNBOOK.md](phase1/RUNBOOK.md) — 主题探索方法论
- [output/experiments/registry.csv](output/experiments/registry.csv) — 主题实验登记
