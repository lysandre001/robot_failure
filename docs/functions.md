# 功能契约目录

每条命令固定字段：**做什么 · 输入 · 假设 · 产物 · 怎么跑 · 怎么读 · 不要做什么**。

全局约定见 [CURRENT.md](../CURRENT.md)。**同事操作步骤**见 [OPERATING.md](OPERATING.md)；**列含义**见 [data/canonical_comment_schema.md](../data/canonical_comment_schema.md)。

每条命令标注：**主线** = 导入/清洗真源；**探索** = 点名才跑，不写回 clean/gold/current。

---

## 1. Phase 1 清洗（主线）

**命令**：`python run_preprocess.py`（等价 `python -m phase1.pipeline`）

**做什么**：**统一 Phase1 管线**——宽表去重、评论过滤、shared corpus、阶段统计。平台差异仅在入库适配层（`wide_io` / `douyin_io`）。

**输入**

- `--platform`：`xhs` | `tiktok` | `douyin` | `youtube`
- `--input` / `--xlsx`：宽表路径；须符合 [canonical_comment_schema.md](../data/canonical_comment_schema.md)（抖音 43 列自动映射）
- `--batch`：事件批次名，如 `merged` / `2604-marathon` / `2608-olympic` → `data/clean/{platform}/{batch}/`
- XHS 专用：[config/post_category_by_post.csv](../config/post_category_by_post.csv)
- [config/topic_modeling/comment_content_filter.json](../config/topic_modeling/comment_content_filter.json)（含 `english_boilerplate`；保留 `contains_mention`）
- TikTok shared：[config/topic_modeling/general_stopwords_en.txt](../config/topic_modeling/general_stopwords_en.txt)（sklearn ENGLISH_STOP_WORDS）

**假设**

- 宽表含 sheet「小红书帖子数据」「导出计数_帖子id」
- 帖子标签来自 config，非模型推断
- 默认**不**跑 lexicon 特征（`--legacy-lexicon-features` 才启用）
- 默认**不**跑旧 sklearn `topic_clusters`（`--run-topics` 才启用）

**产物**（`data/clean/{platform}/{batch}/`）

- `clean_comments_unified.csv` — **主表**（含 `platform`、`source_batch` 列）
- `shared_analyzable_corpus.csv` / `excluded_meaningless.csv` / `shared_corpus_summary.json`
- `phase1_preprocess_stage_summary.csv` / `comments_per_post_L1_L2.csv`
- `comment_content_filter_report.json`

**怎么跑**

```bash
python run_preprocess.py --platform xhs --batch merged --input data/rawdata/小红书帖子数据_merged.xlsx
python run_preprocess.py --platform tiktok --batch 2604-marathon --input data/rawdata/tiktok/2604-marathon/<file>.csv
python run_preprocess.py --platform tiktok --batch 2608-olympic --input data/rawdata/tiktok/2608-olympic/<file>.csv
python run_preprocess.py --platform douyin --batch 2608-olympic --input data/rawdata/douyin/2608-olympic/<file>.csv
python run_preprocess.py --platform youtube --batch 2604-marathon --input data/rawdata/youtube/2604-marathon/canonical.csv
python run_preprocess.py --platform youtube --batch 2608-olympic --input data/rawdata/youtube/2608-olympic/canonical.csv
python -m tools.build_corpus_inventory   # → data/corpus_inventory.csv
```

**怎么读**：跨平台对比 [data/corpus_inventory.csv](../data/corpus_inventory.csv)；单源阶段计数见各目录下 `phase1_preprocess_stage_summary.csv`。

**不会自动触发**：英译、video clip、demo 导出、主题建模、LLM 打标。

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

- 评论纳入门控见 [data/clean/comment_quality_gate_rules.md](../data/clean/comment_quality_gate_rules.md) 与 `config/topic_modeling/comment_quality_gate.json`
- 中英分路：中文 jieba≥2 或汉字且 ≥8 字；英文字母词≥4 或去套话后≥2。**不用** sklearn 功能词表
- BGE 编码仍用评论原文；sklearn 英文停用词仅用于 LDA/NMF 主题词提取
- 与 `phase1.topic_modeling` 内 `build_shared_analyzable_corpus` 同一函数

**产物**

- `data/clean/shared_analyzable_corpus.csv`
- `data/clean/excluded_meaningless.csv`
- `data/clean/shared_corpus_summary.json`

---

## 5. 刷新帖子标签（不重跑 Excel）（主线·局部）

**命令**：`python -m tools.refresh_clean_post_labels`

**做什么**：config 变更后，在已有 clean 表上刷新 `post_category` / `robot_status` / `human_role`。

**怎么跑**

```bash
# 单源（推荐）
python -m tools.refresh_clean_post_labels --platform youtube --batch 2604-marathon
# 读 config/post_category/youtube_2604-marathon.csv（存在时）

#  legacy 根目录 symlink（XHS）
python -m tools.refresh_clean_post_labels
```

**不要**：以为刷新标签后 shared / embeddings 自动更新——需重导 shared 并重跑 topic_modeling。

**人的形象**：全局 schema 三档（服务照护 / 被超越者 / 观众）；`normalize_human_role` 兼容 legacy 五档读入。

---

## 5a. YouTube 帖子分类附录（探索）

**命令**：`python -m tools.post_category_appendix`

**做什么**：读 `config/post_category/youtube_*.csv`，生成论文附录用帖子分布与叉乘（人的形象用分析三档）。

**产物**：`output/experiments/appendix_postdist_0919/` — `table_a/b/c_*.csv`、`post_category_distribution.tex`；notebook `notebooks/post_category_distribution.ipynb` 同源逻辑，§6 另写 clean 评论 `table_d/e/f_*`。

**怎么跑**

```bash
python -m tools.post_category_appendix
python -m tools.post_category_appendix --out-dir output/experiments/appendix_postdist_0919
```

---

## 5b. 评论语言检测 + 英译（主线·局部）

**命令**：`python -m tools.comment_lang.run`

**做什么**：对评论文本做 lingua 语言检测；非纯英文经 SiliconFlow 译为英文。写回 **`language` / `is_mixed` / `content_en`**。

**输入**

- `--platform` / `--batch`（或 `--all`）
- XHS/TikTok/抖音：对应 **raw 宽表**（增列 `一级评论语言` 等）
- YouTube：`data/clean/youtube/{batch}/clean_comments_unified.csv`（`kind=clean`，同步 filtered / shared）
- 环境：`SILICONFLOW_API_KEY`（项目根 `.env`）；配置 [config/comment_lang.json](../config/comment_lang.json)

**假设**

- 断点：`output/comment_lang/{platform}_{batch}.jsonl`
- 纯 `en` 且 `is_mixed=0` 复制原文，不调翻译 API
- **主题建模 / BGE 仍用原文 `content`**

**怎么跑**

```bash
python -m tools.comment_lang.run --platform youtube --batch 2604-marathon --detect-only --limit 50  # 冒烟
python -m tools.comment_lang.run --platform youtube --batch 2604-marathon --detect-only
python -m tools.comment_lang.run --platform youtube --batch 2604-marathon
```

**不要**：把英译当主题建模输入；重跑 Phase 1 会冲掉 clean 语言列（需再跑 comment_lang）。

---

## 6. 每帖 L1/L2 计数

**命令**：`python -m tools.export_comments_per_post`

**产物**：`data/clean/comments_per_post_L1_L2.csv`

---

## 6b. Demo：每帖 Top10 高 L2 一级评论

**命令**：`python -m tools.export_demo_top_l2_by_post`

**做什么**：从各平台 `clean_comments_unified.csv` 按帖抽取 **实际 L2 子数最多** 的 Top 10 一级评论（按 `parent_comment_id` 计数，非 raw `reply_count`）。

**输入**：默认读 [data/corpus_inventory.csv](../data/corpus_inventory.csv) 中的 4 份 clean；或 `--input` 单源。

**产物**（[data/demo/](../data/demo/)）

- `top10_l2_by_post_all.csv` — 合并总表
- `summary_by_source.csv` — 每源统计
- `{platform}_{batch}/top10_l2_by_post.csv` — 单源

**怎么读**：见 [data/demo/README.md](../data/demo/README.md)。

---

## 7. 全量主题建模（LDA + NMF + BERTopic 网格）（探索）

**命令**：`python -m phase1.topic_modeling`

**做什么**：构造 shared corpus，encode BGE，并行跑 LDA / NMF / BERTopic（KMeans + HDBSCAN 灵敏度），写实验目录。

**新数据（YouTube / 新批次）**：必须用 **该源** `--input-csv`；新 `--run-id`；登记 [registry.csv](../output/experiments/registry.csv)；勿覆盖 `2026-05-27_topic_merged_bge_hdbscan_sensitivity`。英文语料勿默认 `bge-base-zh-v1.5`。步骤见 [OPERATING.md](OPERATING.md) §G。

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

**不会自动触发**：discovery coder 表更新、current 实验切换。

**不要**：用 lexicon 预过滤输入；不要混用不同 N 的 shared 与 embeddings；不要用 demo/gold 作 input。

---

## 7b. 人工金标与 LLM 比对（探索）

**协议**：[human_label_llm/label_data/GOLD_PROTOCOL.md](../human_label_llm/label_data/GOLD_PROTOCOL.md)

**命令**：`python human_label_llm/run_experiment.py infer|compare`（yaml 指向 `label_data/gold/` 中新文件 + 新 `run_id`）

**不会自动触发**：清洗、主题建模；**不要**改 `experiment/_defaults.yaml` 或写回 gold/clean。

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

## 15. 帖子视听元数据（caption + ASR，可选旁路）

**命令**：`python -m tools.video_match.run_post_media`

**做什么**：对已下载 30s clip 跑 dense VLM caption + SenseVoice ASR，组装帖子级 CSV。

**输入**

- clips：`data/rawdata/{platform}/{batch}/clips/*.mp4`（由 `python -m tools.download_all_clips` 下载）
- 帖子元数据：各平台 raw 宽表（见 `tools/video_match/post_media_jobs.py` 的 `JOBS`）
- 环境：`SILICONFLOW_API_KEY`（项目根 `.env` 或 export）

**产物**

- `output/video_match/{platform}_{batch}_captions.jsonl`
- `output/video_match/{platform}_{batch}_asr.jsonl`
- `data/clean/{platform}/{batch}/post_media.csv`
- `data/clean/post_media.csv`（跨平台总表）

**怎么跑**

```bash
python -m tools.download_all_clips          # 若 clips 尚未下载
python -m tools.video_match.run_post_media  # 全平台
python -m tools.video_match.run_post_media --platform xhs --batch merged
python -m tools.video_match.run_post_media --assemble-only
python -m tools.video_match.run_post_media --skip-caption   # 只补 ASR
```

**不要**：把 `post_media.csv` 当作评论清洗主表；不要与 `shared_analyzable_corpus.csv` 混用。

**跨平台匹配（早期 pilot）**：`tools/video_match/match.py` 等；见 [tools/video_match/README.md](../tools/video_match/README.md)、[writing/video_caption_protocol.md](../writing/video_caption_protocol.md)

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
