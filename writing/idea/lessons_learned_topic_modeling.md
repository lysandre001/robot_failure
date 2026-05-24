# 探索性主题建模：流程与 Lessons Learned

**维护范围**：从**清洗后统一评论表**到 `output/experiments/<run_id>/` 的 LDA / NMF / BERTopic 实验、对比报告与可视化；**不包含** Excel 解析与一级/二级去重合并（见预处理）。  
**上游契约**：`clean_comments_unified.csv`（路径以 [`phase1/RUNBOOK.md`](../phase1/RUNBOOK.md) §2 为准），及 [`config/post_category_by_post.csv`](../config/post_category_by_post.csv) 用于 `robot_status` / `human_role`。  
**姊妹文档**（另一负责人）：[`idea/lessons_learned_phase1_data_preprocessing.md`](lessons_learned_phase1_data_preprocessing.md)

> 依据：`phase1/topic_modeling.py`、`phase1/topic_visualize.py`、`phase1/keyword_filter.py`、`phase1/RUNBOOK.md`、计划 `.cursor/plans/clean_topic_modeling_pipeline_2f58b4ff.plan.md`、`idea/will.md`。  
> **命令、FAQ 表、当前 run 结论**以 [`phase1/RUNBOOK.md`](../phase1/RUNBOOK.md) 为单一操作事实源。

---

## 一、在项目里的位置（研究背景，极简）

- Phase 1 主题为**探索性、候选话语维度**，不是最终理论结论。  
- `post_category` / `robot_status` / `human_role` 来自抽样设计，**不是模型发现的类别**。  
- 详见 [`idea/will.md`](will.md) 与 `RUNBOOK` §1。

---

## 二、端到端流程

| 阶段 | 做什么 |
|------|--------|
| A | 读 `clean_comments_unified.csv`（或配置路径） |
| B | 构造 **shared analyzable corpus**：LDA / NMF / BERTopic **共用同一批评论**；逐步记录剔除量 |
| C | **LDA**：`CountVectorizer` + LDA，多 K |
| D | **NMF**：`TfidfVectorizer` + NMF，同 K |
| E | **BERTopic**：BGE → UMAP（固定种子）→ HDBSCAN（多 `mcs`）+ KMeans（多 K）；c-TF-IDF / 代表词按代码与 `RUNBOOK` §5 |
| F | 写入 `output/experiments/<run_id>/`：`comparison.md`、`config.json`、`run.log`、主题表、横切表等 |
| G | （可选）`topic_visualize.py`：reload 已存模型出 HTML |

**主入口**（示例）：

```bash
PYTHONUNBUFFERED=1 ./.venv/bin/python -m phase1.topic_modeling --device cpu
```

**与主流程隔离的探索工具**：`keyword_filter.py` → 仅 `output/explore/`，**不得**接入 LDA/BERTopic 输入或当标签（**M1/M2**）。

**按机器人帖子状态分层（4 档）**：在 `build_shared_analyzable_corpus` 中为每条评论生成 **`robot_status_group`**——**「强势」「成功」合并为 `强势成功`**，其余 `失败` / `弱势` / `中性` 各一层（实现见 [`phase1/topic_modeling.py`](../phase1/topic_modeling.py) 中 `robot_status_to_stratum_group`、`ROBOT_STATUS_STRATUM_ORDER`）。分层跑完整管线时使用：

```bash
./.venv/bin/python -m phase1.topic_modeling --stratify-robot-status --device cpu --run-id <你的run_id>
```

产物与说明见 [`phase1/RUNBOOK.md`](../phase1/RUNBOOK.md) §3「2b」与各层目录下 `comparison_stratified_overview.md`。

**完整实验计划（工作量、执行步骤、两轮自检清单）**：[分层主题建模实验计划](plan/plan_experiment_stratified_topic_by_robot_status.md)。

---

## 三、注意点（按类）

**A. 语料一致性**  
先固定 **shared corpus** 再比模型（**M7**）。`min_tokens` 等过滤必须**打印前后行数**并写入日志/`config.json`（**M3**）。

**B. 模型假设**  
LDA ← 计数；NMF ← TF-IDF（**M6**）。选 K 勿依赖单一指标（**M4**）。分词勿静默退回劣质 fallback（**M5**）。

**C. BERTopic 双通道**  
Encoder 用**原文**；停用词等在 c-TF-IDF / jieba 侧（**C2/C10**）。中文 `CountVectorizer` + jieba，`token_pattern=None`（**C1**）。BERTopic 内 `min_df/max_df` 避免 **E1**。UMAP `random_state`（**C3**）。概率与 KMeans/HDBSCAN 见 **C4/C6**。

**D. 工程与复现**  
`embeddings.npy` 缓存（**E4**）；模型存档与 UMAP 复用（`RUNBOOK` §5 B1/B2）；HF/代理（**E2/E5/E6/C8**）；`config.json` 序列化（**E7**）；`registry.csv`（**P1/P3**）。

**E. 解释与横切**  
爆款帖主导聚合评论；用 **post-level** 或 **leave-one-post-out**（**M8**）。

---

## 四、Lessons Learned（方法论 M / 工程 E / 流程 P / BERTopic C·B）

### 4.1 方法论（`RUNBOOK` §0.1）

| 编号 | 标题 | 核心教训 |
|------|------|----------|
| M1 | lexicon 子集预过滤 | 无监督主题建模前用语义子集 = 隐含监督。 |
| M2 | lexicon 当 ground truth | 无 IRR 的词典不能当 judge。 |
| M3 | 隐式短文档过滤 | 默认值可悄悄丢大半数据；必须显式记录。 |
| M4 | 单指标选 K | 多证据 + 人工核读。 |
| M5 | char_bigram 静默回退 | 缺依赖应失败可见。 |
| M6 | LDA + TF-IDF | 破坏 LDA 假设。 |
| M7 | 模型间语料不一致 | 先 shared corpus，再比模型。 |
| M8 | post_category 当 i.i.d. | 帖为抽样单元；注意 post-level / LOO。 |

### 4.2 工程（§0.2）

E1 CountVectorizer 与 BERTopic 文档结构；E2–E3 代理与 pip；E4 缓存；E5 模型体量；E6–E7 离线加载与 JSON。

### 4.3 流程（§0.3）

P1 实验目录与 registry；P2 代码与产物同步；P3 以 `config.json` + `run_id` 为锚。

### 4.4 BERTopic FAQ + 第二轮工程（§0.4 + §5）

C1–C10 见 `RUNBOOK` 表；B1–B6（存档、UMAP 单次、KeyBERT+MMR、质量指标、mcs 粒度、`topic_visualize`）。

### 4.5 研究决策（`will.md` 摘要）

- **2026-05-09/10**：主入口 `topic_modeling.py`；去 lexicon 依赖主比较；`keyword_filter` 隔离 `output/explore/`；正式实验登记 `run_id`（如 `2026-05-09_topic_full_corpus_bge_base`）。

---

## 五、本流程明确不做

- 不训练 judge；不把 lexicon / 关键词命中当类别；不把主题当最终结论。  
- POS **不**进主建模输入过滤（可事后诊断）。  
- Lexicon 若重新接入主分析，走 **codebook + IRR** 另开路径（`RUNBOOK` §9）。

---

## 六、推荐阅读顺序（本负责人）

1. [`phase1/RUNBOOK.md`](../phase1/RUNBOOK.md) 全文。  
2. `output/experiments/<run_id>/review_round*.md` → `config.json` → `run.log` → `comparison.md`。  
3. [`idea/will.md`](will.md) — 标签含义与抽样。  
4. 计划文档 — 设计动机；与代码冲突时以代码与 `config.json` 为准。
