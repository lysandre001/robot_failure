# 功能契约目录

每条命令固定字段：**做什么 · 输入 · 假设 · 产物 · 怎么跑 · 怎么读 · 不要做什么**。

全局约定见 [CURRENT.md](../CURRENT.md)。

---

## 1. Phase 1 清洗

**命令**：`python run_preprocess.py`（等价 `python -m phase1.pipeline`）

**做什么**：读小红书宽表 Excel，去重、合并帖子标签、应用噪音规则，写出 canonical 清洗表。

**输入**

- Excel：`--xlsx` 或环境变量 `ROBOTIC_FAILURE_XLSX`，默认项目根 `小红书帖子数据.xlsx`
- [config/post_category_by_post.csv](../config/post_category_by_post.csv)
- [config/topic_modeling/comment_content_filter.json](../config/topic_modeling/comment_content_filter.json)

**假设**

- 宽表含 sheet「小红书帖子数据」「导出计数_帖子id」
- 帖子标签来自 config，非模型推断
- 默认**不**跑 lexicon 特征（`--legacy-lexicon-features` 才启用）
- 默认**不**跑旧 sklearn `topic_clusters`（`--run-topics` 才启用）

**产物**（`data/clean/`）

- `clean_comments_unified.csv` — **主表**
- `clean_comments_unified_before_filter.csv`
- `clean_l1_comments.csv` / `clean_l2_comments.csv`（未过滤）
- `clean_l1_comments_filtered.csv` / `clean_l2_comments_filtered.csv`
- `comment_content_filter_report.json`

**怎么跑**

```bash
python run_preprocess.py --xlsx data/rawdata/小红书帖子数据_merged.xlsx
```

**怎么读**：阶段计数见 [data/clean/phase1_preprocess_stage_summary.csv](../data/clean/phase1_preprocess_stage_summary.csv)；全文说明见 [data/clean/data_preprocessing_protocol.md](../data/clean/data_preprocessing_protocol.md)。

**不要**：把 `output/phase1/` 里的报告图当成清洗主表；不要手工 `cp` 到 `data/clean/`（pipeline 已直接写入）。

---

## 2. 第二批 CSV 入库（一次性）

**命令**：`python -m tools.ingest_xhs_batch2_csv`

**做什么**：容错解析 `2-小红书帖子数据.csv`（NUL、坏行）。

**产物**：`data/rawdata/xhs_batch2_wide_sanitized.csv`、`data/rawdata/xhs_merge_qc.md`

---

## 3. 两批合并 Excel

**命令**：`python -m tools.merge_xhs_batches_xlsx`

**做什么**：batch1 xlsx + batch2 sanitized CSV → merged 宽表。

**产物**：`data/rawdata/小红书帖子数据_merged.xlsx`、`data/rawdata/posts.csv`

---

## 4. 导出 shared analyzable corpus

**命令**：`python -m tools.export_shared_analyzable_corpus`

**做什么**：在 clean 表上第二层筛选（最短长度、有效词数、全库去重等），**不跑** LDA/NMF/BERTopic。

**输入**：`data/clean/clean_comments_unified.csv`（默认）

**假设**

- jieba 有效词数仅用于**纳入判定**；BGE 仍用原文（在 topic_modeling 中 encode）
- 与 `phase1.topic_modeling` 内 `build_shared_analyzable_corpus` 同一函数

**产物**

- `data/clean/shared_analyzable_corpus.csv`
- `data/clean/excluded_meaningless.csv`
- `data/clean/shared_corpus_summary.json`

---

## 5. 刷新帖子标签（不重跑 Excel）

**命令**：`python -m tools.refresh_clean_post_labels`

**做什么**：config 变更后，在已有 clean 表上刷新 `post_category` / `robot_status` / `human_role`。

**不要**：以为刷新标签后 shared / embeddings 自动更新——需重导 shared 并重跑 topic_modeling。

---

## 6. 每帖 L1/L2 计数

**命令**：`python -m tools.export_comments_per_post`

**产物**：`data/clean/comments_per_post_L1_L2.csv`

---

## 7. 全量主题建模（LDA + NMF + BERTopic 网格）

**命令**：`python -m phase1.topic_modeling`

**做什么**：构造 shared corpus，encode BGE，并行跑 LDA / NMF / BERTopic（KMeans + HDBSCAN 灵敏度），写实验目录。

**输入**

- `--input-csv`（默认 `data/clean/clean_comments_unified.csv`）
- `--run-id`（默认勿覆盖 current；新数据用新 id）
- 停用词/领域词：`config/topic_modeling/general_stopwords.txt`、`platform_noise_tokens.csv`、`corpus_noise_tokens.csv`、`domain_user_dict.txt`

**假设**

- **M7**：LDA / NMF / BERTopic 共用同一 shared corpus
- **M6**：LDA 用 CountVectorizer；NMF 用 TfidfVectorizer
- **C2**：BGE encode **原文**；停用词只在 c-TF-IDF / jieba 分词路径
- **C1**：中文必须 jieba CountVectorizer（缺 jieba 则 raise）
- `robot_status_group` 写入 shared 供横切；**不是**聚类标签

**产物**（`output/experiments/<run_id>/`）

- `shared_analyzable_corpus.csv`、`embeddings.npy`、`config.json`、`run.log`
- `comparison.md`、`lda_k*/`、`nmf_k*/`、`bert_kmeans_k*/`、`bert_hdbscan_mcs*/`
- `a_bertopic_quality.csv`

**怎么跑**

```bash
PYTHONUNBUFFERED=1 ./.venv/bin/python -m phase1.topic_modeling \
  --run-id YYYY-MM-DD_<描述> \
  --input-csv data/clean/clean_comments_unified.csv \
  --device cpu \
  --lda-k 5 7 10 12 \
  --bert-kmeans-k 5 7 10 \
  --hdbscan-min-cluster-sizes 30 50 80 100 200
```

**怎么读**：`config.json` → `run.log` → `comparison.md` → 各 variant 下 `topics.csv` / `*_samples.csv`。

**不要**：用 lexicon 预过滤输入；不要混用不同 N 的 shared 与 embeddings。

---

## 8. BERTopic 可视化

**命令**：`python -m phase1.topic_visualize`

**做什么**：reload 已存 BERTopic 模型，出 HTML 图（不再 fit）。

**输入**：`--run-id`、`--variant`（如 `bert_kmeans_k7`）

**产物**：`<run_dir>/<variant>/figs/*.html`

---

## 9. Topic Discovery（L1/L2 分层）

**命令**：`python -m phase1.run_topic_discovery`

**做什么**：在父 run 的 embeddings 上，按 `comment_level` 分层做 HDBSCAN 候选、C_V 选 nr、生成 coder 表。

**输入**：父 run 须已有 `embeddings.npy`、`shared_analyzable_corpus.csv`、`comment_content_filter.json`

**假设**

- L1/L2 **各自**选 mcs/nr，禁止照搬 pooled 参数
- `embeddings.npy` 按 **行 index** 切片，非 comment_id join

**产物**（每层 `topic_discovery_l{1,2}/`）

- `corpus_freeze.json`、`hdbscan_candidate_summary.csv`
- `topic_number_selection_notes.md`、`coder*_sheet_final_nr*.csv`
- `topic_comment_samples_final_nr*.csv`

**怎么跑**

```bash
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 1 --base-mcs 30 --step all
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 2 --base-mcs 30 --step all
```

**SOP**：[writing/topic_discovery_intern_runbook.md](../writing/topic_discovery_intern_runbook.md)

---

## 10. 关键词探索

**命令**：`python -m phase1.keyword_filter`

**做什么**：按关键词或 lexicon 命中抽样，供人工阅读。

**产物**：`output/explore/<timestamp>_<name>/`（**不是**正式实验）

**不要**：把命中当分类标签或主题建模输入过滤器（M1/M2）。

---

## 11. 实验后诊断（单 run）

| 命令 | 产物 |
|------|------|
| `python -m tools.topic_post_dominance` | 单帖是否主导某 topic |
| `python -m tools.topic_like_concentration` | topic 内高赞集中度 |
| `python -m tools.compute_layer_cluster_metrics` | L1/L2/pooled 聚类指标 |
| `python -m tools.audit_comment_content_filter` | 噪音规则命中审计 |

---

## 12. 人工标注抽样

**命令**：`python -m tools.sample_manual_label`

**产物**：`data/clean/manual_label_l1_30perpost.csv`

---

## 13. Human vs LLM 标注（可选旁路）

**命令**：`python human_label_llm/run_experiment.py infer object`

**配置**：`human_label_llm/experiment/_defaults.yaml` + 各 experiment yaml

**产物**：`human_label_llm/output/<run_id>/`

**说明**：与 topic discovery 的 domain/label 编码是**独立任务**。

---

## 14. LLM Stance 三模型（可选旁路）

**命令**：`python -m phase1.llm_stance.annotate` / `aggregate`

**说明**：OpenRouter  stance 标注；见 [phase1/llm_stance/README.md](../phase1/llm_stance/README.md)

---

## 15. 视频 dense caption / 跨平台匹配（可选旁路）

**命令**：`tools/video_match/*`

**说明**：与评论主题管线独立；见 [tools/video_match/README.md](../tools/video_match/README.md)、[writing/video_caption_protocol.md](../writing/video_caption_protocol.md)

---

## 16. Notebooks（诊断/对照，非管线入口）

| Notebook | 用途 |
|----------|------|
| `notebooks/phase1_structured.ipynb` | 分步调用 pipeline 库函数 |
| `notebooks/topic_k57_compare.ipynb` | LDA/NMF/BERTopic K 对照 |
| `notebooks/topic_discovery_hdbscan_review.ipynb` | Discovery 审阅 |
| `notebooks/tokenization_baseline_audit.ipynb` | 改词典前的 jieba 基线（不写 canonical） |

---

## 17. Legacy lexicon 特征（默认关）

**命令**：`python run_preprocess.py --legacy-lexicon-features`

**做什么**：旧版 `features.py` / `analysis.py` 词典统计与图，输出到 `output/phase1/`。

**不要**：把 lexicon 命中当 ground truth 或主题建模预过滤。
