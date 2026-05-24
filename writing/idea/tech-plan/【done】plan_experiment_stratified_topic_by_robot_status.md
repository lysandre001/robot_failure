# 实验计划：按机器人帖子状态分层主题建模（4 档）

# done：发现分类型的建模还是挺makesense的

> 与 [`lessons_learned_topic_modeling.md`](lessons_learned_topic_modeling.md)、[`.cursor/plans/clean_topic_modeling_pipeline_2f58b4ff.plan.md`](../.cursor/plans/clean_topic_modeling_pipeline_2f58b4ff.plan.md) 对齐。  
> **合并规则**：`强势` + `成功` → **`强势成功`**；与 `失败` / `弱势` / `中性` 共四层（研究设计维度，**非**模型聚类结果）。

---

## 1. 目标

在**同一套清洗与 shared corpus 规则**下，对四层 `robot_status_group` **分别**跑 LDA / NMF / BERTopic，得到「每种机器人帖子语境下，评论里冒出哪些话语主题」，供近读与 codebook 迭代。**不**把跨层 topic id 当作可比较编号。

---

## 2. 工作量评估

| 类别 | 估计 | 说明 |
|------|------|------|
| **代码改动** | **低（≈0）** | [`phase1/topic_modeling.py`](../phase1/topic_modeling.py) 已实现 `robot_status_group`、`--stratify-robot-status`、`_adaptive_cfg_for_stratum`、各层子目录产物。 |
| **运行时间** | **中高** | 四层各跑一次 BERTopic（编码 + UMAP + 多 HDBSCAN + 多 KMeans）；若与全量同模型，总时长约为单层全量的约 **3～4 倍量级**（非严格线性，因小层更快）。建议 `--device cpu` 或本机 GPU，并确认 HF 缓存已就绪。 |
| **人工解读** | **中高** | 每层各读 `comparison.md`、`topics.csv`、`samples.csv`；**禁止**默认把「失败-主题3」等同于「成功-主题3」。 |
| **文档/登记** | **低** | 指定 `run_id`，跑完后检查 `registry.csv`、`comparison_stratified_overview.md`；按需补 `review_round1/2.md`（见 §6）。 |

若后续要**跨层主题对齐表**（人工 Jaccard / 关键词对照），属增量工作，**本计划第一轮不强制**。

---

## 3. 执行步骤（跑实验）

1. **输入就绪**：[`config/post_category_by_post.csv`](../config/post_category_by_post.csv) 与 [`clean_comments_unified.csv`](../phase1/RUNBOOK.md)（路径以 RUNBOOK 为准）；[`comment_content_filter.json`](../config/topic_modeling/comment_content_filter.json) 版本固定。  
2. **命令**（示例，见 [`phase1/RUNBOOK.md`](../phase1/RUNBOOK.md) §3「2b」）：

```bash
cd /Users/yilin/Desktop/project/robot_failure
PYTHONUNBUFFERED=1 ./.venv/bin/python -m phase1.topic_modeling \
  --stratify-robot-status \
  --device cpu \
  --embedding-model BAAI/bge-base-zh-v1.5 \
  --run-id YYYY-MM-DD_topic_stratified_robot_status
```

3. **产物结构**（父目录 `output/experiments/<run_id>/`）  
   - `shared_analyzable_corpus_full.csv`（全量，含 `robot_status_group`）  
   - `strata/<失败|弱势|中性|强势成功>/`：该层 `shared_analyzable_corpus.csv`、`comparison.md`、`config.json`、`run.log`、LDA/NMF/BERTopic 子目录等  
   - `comparison_stratified_overview.md`、`config_stratified_parent.json`  
4. **可选**：对各层 `bert_kmeans_k7`（或主推 K）跑 [`phase1/topic_visualize.py`](../phase1/topic_visualize.py)（每层单独 `--variant` 路径）。

---

## 4. 与历史错误的对照（本实验必须规避）

| 教训 | 在本分层实验中的落实方式 |
|------|---------------------------|
| **M1** | 分层依据是 **`post_category_by_post` + 合并规则**，不是 lexicon 命中子集。 |
| **M2** | 不把词典当标准答案；主题仍为探索性。 |
| **M3** | 每层 `run.log` / `config.json` 含 **n_shared_stratum**、自适应 `lda_k` / `mcs`；父级 summary 含全量剔除统计。 |
| **M4** | 小层 **自适应 K / mcs**（`_adaptive_cfg_for_stratum`）；解读不依赖单一指标。 |
| **M5** | 环境需有 **jieba**；缺则直接报错（现有逻辑）。 |
| **M6** | 每层内仍为 LDA=Count、NMF=TF-IDF（同一套函数）。 |
| **M7** | **每层内部** LDA/NMF/BERTopic 共用该层 `shared_analyzable_corpus.csv`，不混语料。 |
| **M8** | 层内帖数可能极少：**仅描述性**读主题；LOO 仅在 `n_posts≥3` 时跑；警惕单层内爆款帖（可沿用 `topic_post_dominance` / `topic_like_concentration` 脚本做诊断）。 |
| **E1/C1/C2** | BERTopic 向量器与双通道保持与全量实验一致（代码复用）。 |

---

## 5. 第一轮评估（完成度 / 是否按计划跑通）

**目的**：确认「计划里的工程项都落地」，而非评价主题好坏。

- [ ] 父目录存在 `config_stratified_parent.json`，且 `merge_rule`、四层 `strata` 列表与 `n_comments` / `n_posts` 合理。  
- [ ] 四层目录均在 `strata/` 下（若某层 **n_comments=0** 可 skip，须在 overview 表中标出）。  
- [ ] 每层有 `shared_analyzable_corpus.csv`、`run.log`、`config.json`、`comparison.md`。  
- [ ] 每层 LDA/NMF 产物存在（`lda_k*` / `nmf_k*`）。  
- [ ] `n≥20` 的层有 BERTopic 子目录与 `embeddings.npy`（或日志说明跳过原因）；`n<20` 的层允许仅 LDA/NMF（与 `_run_topic_pipeline_steps` 一致）。  
- [ ] `registry.csv` 已追加本 `run_id`（或手工补登记）。  
- [ ] 全量清洗与分层一致：父级 `shared_analyzable_corpus_full.csv` 行数 = 各层 `n_comments` 之和（允许空层为 0）。

**第一轮发现问题**：记录到 `<run_id>/review_round1.md`（或 issue 列表），逐项改配置/重跑/补脚本后进入第二轮。

---

## 6. 第二轮评估（遗漏与解释边界）

**目的**：补第一轮遗漏 + 明确**写论文/报告时不能越界的表述**。

- [ ] 人工速读每层 `comparison.md` 与 `samples.csv`：主题是否可读、是否明显被单帖/高赞评论绑架（必要时跑 `topic_post_dominance` / `topic_like_concentration`）。  
- [ ] 极小层：是否需在文中标注「样本量限制、不做组间显著性」？  
- [ ] **跨层比较**：是否已避免「topic 编号对齐」的表述？是否区分 `robot_status`（细）与 `robot_status_group`（粗）？  
- [ ] 与全量实验 `2026-05-09_topic_full_corpus_bge_base` 的关系是否写清（互补而非替代）？  
- [ ] `phase1/topic_visualize.py` 是否覆盖需要展示的一层或多层？

**第二轮发现问题**：写入 `review_round2.md`，修改文档或小范围重跑后，**再快速扫一遍第一轮清单**，确认无回归。

---

## 7. 与 lessons 文档的同步

- 分层入口与合并规则已摘要至 [`lessons_learned_topic_modeling.md`](lessons_learned_topic_modeling.md) §二。  
- **本文件**为可执行的实验计划 + 两轮自检；跑新 `run_id` 后更新其中的日期与路径示例即可。
