# 方法与数据（草稿）

数据下载与预处理的全文级说明见：

- **[data/clean/data_preprocessing_protocol.md](../data/clean/data_preprocessing_protocol.md)**（正文 Methods 段落 + 附录表稿，与代码一致）
- 阶段计数表：[data/clean/phase1_preprocess_stage_summary.csv](../data/clean/phase1_preprocess_stage_summary.csv)
- 视频 dense caption（跨平台匹配 + 理论抽样帖视觉描述）：**[writing/video_caption_protocol.md](video_caption_protocol.md)**

**摘要**：理论抽样 16 帖 + anchor 17 帖 → Phase 1 清洗 **46,051** 条评论 → 主题建模 shared corpus **26,811** 条（两批适用同一套清洗函数；第二批仅在 CSV 导入阶段额外容错）。

---

数据下载

数名研究员在一周的时间里，通过搜索机器人「马拉松」等关键词进行检索，并以目的性抽样选取帖子。合并语料共 **33** 帖（第一批理论抽样 **16** 帖，第二批 anchor **17** 帖）。预处理包括：宽表拆分为一、二级评论并按评论 ID 去重、空内容与可配置噪音规则过滤；主题建模前另设 shared corpus 筛选（最短长度、有效词数、全库正文去重等），详见上述 protocol 文档。

---

## 主题聚类（探索性话语结构发现）

**分析单元**为单条**评论**（`comment_id`），而非帖子、用户或讨论串。机器聚类只用于提出**候选话语结构**（dense recurring discourse patterns），不等同于社会科学意义上的最终主题；最终主题体系由人工开放归纳、归并与仲裁后冻结。

**语料**：在 shared analyzable corpus 上进行（本实验 *N* = 26,811；冻结快照见 `output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/topic_discovery_review/corpus_freeze.json`）。评论原文经 BGE 句向量编码（`BAAI/bge-base-zh-v1.5`），UMAP 降维（5 维，`random_state=42`），再经 BERTopic 框架聚类。主题词提取使用 jieba 分词 + c-TF-IDF，并辅以 KeyBERTInspired / MMR 表示模型。

**HDBSCAN 候选选择**：在固定 embedding 与 UMAP 表示下，比较 `min_cluster_size`（mcs）= 30 / 50 / 80 / 100 等候选解，报告 topic 数、raw outlier 比例与最大簇占比。本研究以 **mcs=50** 作为后续步骤的基座模型（88 个有效 topic；最大有效簇约占非 outlier 评论 7.6%），而未采用 mcs=80（37 个 topic，但最大簇接近 40%，易形成难以人工归并的「杂物桶」）。

**Topic-number selection**：在 mcs=50 基座之上，对 BERTopic `reduce_topics(nr)` 系统扫描 *nr* ∈ {10, 15, …, 100}（步长 5），对每个候选计算 **C_V 主题一致性**（gensim；语料为 jieba 分词文本）及结构诊断（topic 数、最大簇占比、覆盖率等；见 `topic_number_cv_curve.csv`）。**不机械取 C_V 最高解**：C_V 峰值出现在 *nr*=50（C_V≈0.68），但伴随最大簇约 20% 的结构风险；最终在满足「最大簇占比 ≤12%」且 topic 数可审阅（约 40–100）的候选中，选取 **`reduce_topics(nr=85)`** 作为进入人工编码的主解（84 个 topic，C_V≈0.56，最大簇占比 7.6%）。需强调：`reduce_topics` 是在 HDBSCAN 结果上的**后验合并**，不重新跑 embedding 或密度聚类；outlier 比例保持不变（raw outlier≈44.4%）。

**Outlier 处理**：HDBSCAN 将低密度评论标为 `topic_raw = -1`，视为对语义长尾的保守处理，而非失败。主分析与人工归并使用 **raw 非 outlier** 分配；经 `reduce_outliers` 后的 `topic_assigned`（outlier≈0.9%）仅作覆盖率敏感性对照。

**人工归并与验证（进行中）**：在 topic-number selection 完成后，为每个 machine topic 生成增强审阅材料（关键词、代表文本、跨帖样本、随机样本、高赞样本及帖子支配度诊断），由两名 coder 独立填写 domain / label（允许 `mixed/unclear`），计算 Cohen's κ 后仲裁为 `final_topic_map`，再回填至评论层并报告 domain 分布。高风险 topic（如单帖占比过高）与相邻 *nr* 候选、alternate mcs 解一并纳入敏感性分析。复现命令与输出清单见 `topic_discovery_review/REPRO.md`、`METHODS.md`。

