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

**分层动机**：一级评论（L1, *N*=15,901）通常自包含、发起话题或表态，而二级回复（L2, *N*=10,910）依赖父评 / 帖子上下文、长度更短、承担调侃与立场回响等互动功能。若 pooled（*N*=26,811）混跑，短回复易被打成 outlier 或并入长评论，形成难以人工归并的「杂物桶」。本研究因此 **按 `comment_level` 分层** 独立做候选发现与主题数选择：**L1 与 L2 各自为主分析层级**，pooled 仅作为敏感性与三层对照（见 `topic_discovery_review.md` §2 三层对照表）。

**编码与降维**：评论原文经 BGE 句向量编码（`BAAI/bge-base-zh-v1.5`，shared analyzable corpus 一次性 encode），按 `comment_level` 切片喂入每层独立的 UMAP（5 维，`random_state=42`）+ BERTopic。主题词提取使用 jieba 分词 + c-TF-IDF，并辅以 KeyBERTInspired / MMR 表示模型。每层产物冻结于 `output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/topic_discovery_l1/` 与 `topic_discovery_l2/`；pooled 旧产物保留在 `topic_discovery_review/`。

**HDBSCAN 候选选择（每层独立）**：在固定 embedding 与 UMAP 表示下，比较 `min_cluster_size`（mcs）= 30 / 50 / 80 / 100 候选解，报告 topic 数、raw outlier 比例与最大簇占比（每层 `hdbscan_candidate_summary.csv`）。L1 与 L2 均在 mcs∈{80,100} 出现 mega-cluster 塌缩（largest_share > 93%），mcs=50 时 L2 最大簇升至 15%；两层均选 **mcs=30** 作为基座（L1：95 raw topics，largest 7.6%；L2：50 raw topics，largest 10.0%）。pooled 早先选 mcs=50（88 raw topics，largest 7.6%）；与分层选择不同源自层内样本与密度结构差异，故 pooled 参数**不被照搬**到 L1/L2。

**Topic-number selection（每层独立）**：在该层 mcs=30 基座之上，对 BERTopic `reduce_topics(nr)` 系统扫描 *nr* ∈ {10, 15, …, 100}（步长 5），计算 **C_V 主题一致性**（gensim；语料为 jieba 分词文本）与结构诊断。**不机械取 C_V 最高解**：在满足「最大簇占比 ≤12%」且 topic 数可审阅（约 40–100）的候选中，取 C_V 最高项。结果：**L1 选 `reduce_topics(nr=90)`，得 89 topics，C_V≈0.605，largest 7.6%**；**L2 选 `reduce_topics(nr=45)`，得 44 topics，C_V≈0.505，largest 10.0%**。Pooled 历史选定为 `nr=85`，得 84 topics，C_V≈0.559。`reduce_topics` 仅做后验合并，outlier 比例保持不变（L1 raw outlier≈43.3%，L2≈47.8%，pooled≈44.4%）。

**Outlier 处理**：HDBSCAN 将低密度评论标为 `topic_raw = -1`，视为对语义长尾的保守处理而非失败。主分析与人工归并使用 **raw 非 outlier** 分配；`reduce_outliers` 后的 `topic_assigned` 仅作覆盖率敏感性对照。L2 outlier 略高于 L1/pooled，与短回复的语义稀疏相符；不进行强制再分配以避免污染主题边界。

**人工归并与验证（进行中，每层独立）**：在 topic-number selection 完成后，为每个 machine topic 生成增强审阅材料（关键词、代表文本、跨帖 / 高赞 / 随机三层 10 评论抽样、帖子支配度诊断），由两名 coder 独立填写 domain / label（允许 `mixed/unclear`），计算 Cohen's κ 后仲裁为 `final_topic_map.csv`，再回填至评论层并报告 domain 分布。L1（89 行）与 L2（44 行）各跑一套；pooled 84 行仅在 L1/L2 完成后作为对照。高风险 topic（如单帖占比过高）与相邻 *nr* 候选、alternate mcs 解一并纳入敏感性分析。复现命令与输出清单见每层 `REPRO.md`、`output_manifest.csv`，以及 [`writing/topic_discovery_intern_runbook.md`](topic_discovery_intern_runbook.md)。

