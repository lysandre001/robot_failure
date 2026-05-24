# 数据预处理流程说明（论文正文与附录）

> **版本**：与仓库合并语料实验 `2026-05-19_topic_full_corpus_merged_bge_base` 一致。  
> **canonical 产物**：`data/clean/clean_comments_unified.csv`（Phase 1 清洗）；`output/experiments/2026-05-19_topic_full_corpus_merged_bge_base/shared_analyzable_corpus.csv`（主题建模用 shared corpus）。  
> **复现入口**：`phase1/RUNBOOK.md` §2b–§3；实现代码 `phase1/preprocess.py`、`phase1/pipeline.py`、`phase1/comment_content_filter.py`、`phase1/topic_modeling.py`。

---

## 一、正文可用稿（Methods / Data — 预处理段落）

### 1.1 数据来源与抽样设计

本研究的小红书评论数据来自两批相互独立的抓取，在分析前合并为统一语料库。

**第一批（理论抽样帖，*N* = 16）** 依据研究设计的「机器人状态 × 人类角色」矩阵进行目的性抽样，每格 1–3 帖，覆盖失败、弱势、中性、成功、强势等状态下不同的观众位置（如抢救者、旁观者、被超越者等）。帖子级编码由研究者事先指定，存于 `config/post_category_by_post.csv`（格式：`状态|角色`），**非**算法推断标签。

**第二批（anchor 扩展帖，*N* = 17）** 为综合类营销账号下与高互动量相关的机器人议题帖子（评论量显著高于一般帖），用于在独立于第一批抽样框的语料上探索话语结构的广度。该批帖子**未**纳入上述理论矩阵编码，在分析中记为 anchor 语料；全量主题建模时不按帖子类型分层。

两批帖子 **无重叠**（帖子 ID 交集为 0）。合并后共 **33** 帖、**46,051** 条去重评论（一级 24,895；二级 21,156）。探索性主题建模在进一步筛选后的 **28,055** 条 shared analyzable corpus 上进行（见 §1.3）。

### 1.2 原始数据格式与合并

- **第一批**：平台导出的 Excel（`1-小红书帖子数据.xlsx`），含两个工作表——（1）宽表「小红书帖子数据」：每行同时携带帖子元数据与一、二级评论字段；（2）「导出计数_帖子id」：帖子 ID 与辅助类别字段。
- **第二批**：同结构的 CSV 导出（`2-小红书帖子数据.csv`）。因导出文件含 NUL 字节、字段错位行及非标准帖子 ID，在合并前经专用容错解析脚本处理（见附录 A.1），**不**直接送入主清洗流水线。

合并时，两批宽表按列对齐后纵向拼接（`phase1/build_merged_xlsx.py`），生成 `data/rawdata/小红书帖子数据_merged.xlsx`；帖子级链接与正文摘要见 `data/rawdata/posts.csv`。

### 1.3 评论级清洗（Phase 1）

在合并宽表上运行统一流水线（`run_phase1.py` → `phase1/pipeline.py`），**两批适用完全相同规则**，无按批次分支逻辑。主要步骤如下。

1. **帖子级元数据合并**：宽表左连接计数表；`post_category` 缺失填 `unknown`；再用研究编码表覆盖第一批 16 帖的类别。
2. **评论展开与去重**：自宽表拆出一级评论表（按 `一级评论id` 去重）与二级评论表（按 `二级评论id` 去重）；纵向合并为统一长表，字段包括 `comment_id`、`comment_level`（1/2）、`content`、`like_count` 等。
3. **文本规范化**：`content` 做首尾空白剔除；计算字符长度 `char_len`。
4. **有效性过滤**：删除空内容；并应用可配置噪音规则（`config/topic_modeling/comment_content_filter.json`）：纯 emoji、含 @ 提及、由短片段重复构成的无意义串（如「哈哈哈哈」类叠字，规则参数见附录表 A-3）。

输出主表 `clean_comments_unified.csv`（*N* = 46,051）。该表保留全部通过 Phase 1 的评论，供描述统计与人工标注抽样；**不**等同于主题建模输入集。

### 1.4 主题建模用语料（shared analyzable corpus）

为在 LDA、NMF 与 BERTopic 之间保持可比性（同一批文档），在 Phase 1 输出上施加第二层筛选（`phase1/topic_modeling.py` 中 `build_shared_analyzable_corpus`），标准包括：

- 规范化后长度 &lt; 4 字符；
- 与 Phase 1 相同的 JSON 噪音规则（在 shared 阶段再次应用）；
- 纯标点、纯 URL、长串纯数字；
- 经 jieba 分词并去除停用词后，有效词数 &lt; 2（**仅用于纳入判定**；句向量编码仍使用原文，见 §1.5）；
- **全库**正文归一化去重：对 `casefold()` 后的文本在全表范围内保留首次出现行（`duplicate_text`）。

最终 *N* = 28,055（占 Phase 1 输出的 60.9%）。其中第一批 19,088 条（保留率 65.3%），第二批 8,967 条（保留率 53.3%）；保留率差异主要来自第二批帖内重复评论更多及有效词数不足更多，而非两套不同的过滤函数（见附录 B.3）。

### 1.5 与主题建模相关的文本处理说明

- **语义向量（BGE）**：模型 `BAAI/bge-base-zh-v1.5`，输入为评论 **原文**，不在编码前删除停用词或分词。
- **主题词提取（c-TF-IDF 等）**：使用 jieba 中文分词与项目停用词表，与向量空间分离（双通道设计，符合 BERTopic 对中文处理的常规做法）。

### 1.6 人工标注抽样（可选报告）

人工开放编码的候选评论从 `clean_comments_unified.csv` 中抽取（**非**仅从 shared corpus），按帖分层：每帖一级评论最多 30 条（高赞与随机各半，不足 30 则全取）。样本表含帖子链接字段，见 `data/clean/manual_label_l1_30perpost.csv`（*N* = 945）。

---

## 二、附录 A：流程、参数与阶段计数

### 附录 A.1 第二批 CSV 容错导入（仅第二批）

**脚本**：`phase1/ingest_xhs_csv.py`

| 步骤 | 操作 | 标准 |
|------|------|------|
| 1 | 读入原始字节 | 删除 `\x00`（NUL） |
| 2 | 解码 | UTF-8（含 BOM），非法字节 `replace` |
| 3 | 解析 | 标准库 `csv.reader` |
| 4 | 行保留 | 字段数 = 30，且 `帖子id` 匹配 `^[0-9a-f]{24}$` |
| 5 | 输出 | `data/rawdata/xhs_batch2_wide_sanitized.csv` |

**第二批导入损失（本研究单次运行）**：

| 指标 | 数值 |
|------|------|
| 跳过行（字段错位等） | 1,568 |
| 保留宽表行 | 20,988 |
| 唯一帖子 | 17 |

详见 `data/rawdata/xhs_merge_qc.md`。

### 附录 A.2 合并与 Phase 1 阶段计数

**合并脚本**：`phase1/build_merged_xlsx.py`（`pd.concat([batch1, batch2])`，batch1 在前）

| 阶段代码 | 描述 | 行数 | 唯一帖子 |
|----------|------|------|----------|
| A0 | 合并后宽表 | 57,855 | 33 |
| A2 | 一级评论去重后 | 30,170 | 33 |
| A3 | 二级评论去重后 | 26,534 | 33 |
| A4 | 一二级合并后（过滤前） | 56,704 | 33 |
| **A5** | **Phase 1 过滤后（clean）** | **46,051** | **33** |

**A5 分层（按帖子归属）**：

| 子集 | 帖数 | 评论数 | 一级 | 二级 |
|------|------|--------|------|------|
| 第一批 | 16 | 29,215 | 13,789 | 11,590 |
| 第二批 anchor | 17 | 16,836 | 11,106 | 9,566 |

**Phase 1 过滤剔除（A4→A5，合计 10,653 条）**：空内容；`comment_content_filter.json` 命中（全库统计：`only_at_mentions` 8,841；`repeated_fragment` 1,479；`pure_emoji` 38）。规则定义见 `phase1/comment_content_filter.py` 中 `classify_comment_noise`。

### 附录 A.3 `comment_content_filter.json` 参数摘要

| 规则 | 启用 | 要点 |
|------|------|------|
| `pure_emoji` | 是 | 去空白后仅含 emoji/修饰符 |
| `contains_mention` | 是 | 正文含 `@`/`＠` 提及即排除 |
| `only_mentions` | 否 | （已由 `contains_mention` 覆盖）去掉 @ 后无实质字符 |
| `repeated_fragment` | 是 | 周期 ≤6 字，重复 ≥3 次，总长 ≥4 字 |

### 附录 A.4 shared corpus 筛选（A5→shared）

**输入 SHA256**（`clean_comments_unified.csv`）：  
`01a8cde50cc9d06f9e54f88a820fee0a3ef0e06cc5f99415cecc6a80653353ef`

| 剔除原因 | 全库条数 | 第一批 | 第二批 |
|----------|----------|--------|--------|
| `effective_tokens_lt_min` | 12,396 | 8,345 | 4,051 |
| `empty_or_too_short`（&lt;4 字符） | 2,193 | 1,450 | 743 |
| `duplicate_text`（全库首次保留） | 3,401 | 328 | 3,073 |
| `pure_punctuation` 等其它 | 6 | 4 | 2 |
| **合计剔除** | **17,996** | **10,127** | **7,869** |
| **保留（shared）** | **28,055** | **19,088** | **8,967** |

**配置默认值**（`TopicModelingConfig`）：`min_clean_chars=4`，`min_effective_tokens=2`。

**说明（`robot_status_group` 缺失）**：shared 中 11,127 条无机器人状态分层标签，对应第二批 anchor 及未匹配编码表的行；**仍参与**嵌入与聚类，仅影响按状态横切的汇总表。

### 附录 A.5 每帖评论规模与 shared 保留率

完整 per-post 表：`data/clean/shared_corpus_per_post.csv`（含帖子链接、clean/shared 计数、保留率）。

**极端例（说明帖内重复对 shared 的影响，非单独规则）**：

| 帖子 ID（缩写） | 批次 | clean | shared | 保留率 |
|-----------------|------|-------|--------|--------|
| …e46032 | anchor | 4,351 | 679 | 15.6% |
| …e481e8 | 第一批 | 9,829 | 7,611 | 77.4% |

---

## 三、附录 B：方法学说明与局限

### B.1 两批处理是否同规？

- **Phase 1**（`build_level1/2`、`filter_valid_comments`）：**同一函数、同一 JSON**，无 `if batch2` 分支。
- **shared**：**同一函数、同一阈值**；第二批额外损失仅发生在 **CSV 导入阶段**（附录 A.1）及 **内容分布差异**（更短、更重复），而非另一套阈值表。

### B.2 `duplicate_text` 的操作性定义

当前实现为 **全库**归一化文本去重，保留 **DataFrame 遍历顺序** 中的首次出现。因合并宽表将第一批置于第二批之前，**跨批完全相同正文**时第一批优先保留。此设计降低刷屏重复对聚类的权重，但可能略微压低第二批在跨帖流行语上的计数。敏感性分析可考虑改为 **帖内去重**（`seen_norm` 按 `帖子id` 分桶）；本研究主分析未改，因帖内去重仅约增加第二批 37 条（全库 +73 条），对总量影响有限。

### B.3 与历史单批产物的关系

仓库中 `output/phase1/data/clean_comments_unified.csv`（31,245 行，仅 16 帖）为 **早期单次清洗** 产物。本研究对 **同一第一批 Excel 单独重跑** 当前流水线得 29,215 行，与合并语料中第一批子集 **完全一致**；差异来自流水线与噪音规则迭代，**非**合并引入。

### B.4 软件环境（复现）

| 组件 | 版本/说明 |
|------|-----------|
| Python | 3.9+（项目 `.venv`） |
| pandas | ≥2.0 |
| jieba | ≥0.42.1（分词与有效词计数） |
| 主题建模 | BERTopic ≥0.16，sentence-transformers ≥2.2 |

### B.5 复现命令（合并语料）

```bash
# 1) 第二批 CSV 容错
python -m phase1.ingest_xhs_csv

# 2) 合并 xlsx + posts.csv
python -m phase1.build_merged_xlsx

# 3) Phase 1 清洗
python run_phase1.py --xlsx data/rawdata/小红书帖子数据_merged.xlsx
cp output/phase1/clean_comments_unified.csv data/clean/

# 4) 主题建模（shared 在此步生成）
PYTHONUNBUFFERED=1 python -m phase1.topic_modeling \
  --run-id 2026-05-19_topic_full_corpus_merged_bge_base \
  --input-csv data/clean/clean_comments_unified.csv \
  --device cpu
```

---

## 四、附录 C：产物文件清单

| 路径 | 用途 |
|------|------|
| `data/rawdata/小红书帖子数据_merged.xlsx` | 合并原始宽表 |
| `data/rawdata/posts.csv` | 33 帖 ID、链接、正文 |
| `data/rawdata/xhs_batch2_wide_sanitized.csv` | 第二批容错 CSV |
| `data/rawdata/xhs_merge_qc.md` | 第二批导入 QC |
| `data/clean/clean_comments_unified.csv` | Phase 1 主输出（46,051） |
| `data/clean/comments_per_post_L1_L2.csv` | 每帖一/二级评论数 + 链接 |
| `data/clean/shared_corpus_per_post.csv` | 每帖 clean/shared + 保留率 |
| `data/clean/manual_label_l1_30perpost.csv` | 人工标注候选样本 |
| `data/clean/phase1_preprocess_qc_notes.md` | 合并 QC 备忘 |
| `output/experiments/2026-05-19_…/shared_analyzable_corpus.csv` | 主题建模输入（28,055） |
| `output/experiments/2026-05-19_…/excluded_meaningless.csv` | shared 剔除行及原因 |
| `output/experiments/2026-05-19_…/config.json` | 参数、SHA、剔除统计 |

---

## 五、附录 D：表稿示例（可直接排进 Word/LaTeX）

**表 D-1 数据预处理各阶段评论条数**

| 阶段 | 说明 | *N* |
|------|------|-----|
| 原始合并宽表 | 两批拼接，行级记录 | 57,855 |
| 评论去重合并 | 一、二级 ID 去重后长表 | 56,704 |
| Phase 1 清洗后 | 空内容与噪音规则 | **46,051** |
| shared analyzable corpus | 主题建模统一语料 | **28,055** |

**表 D-2 两批数据在清洗与 shared 阶段的规模**

| 子集 | 帖子数 | Phase 1 后 | shared | shared 保留率 |
|------|--------|------------|--------|---------------|
| 理论抽样（第一批） | 16 | 29,215 | 19,088 | 65.3% |
| anchor（第二批） | 17 | 16,836 | 8,967 | 53.3% |
| **合计** | **33** | **46,051** | **28,055** | **60.9%** |

---

*文档生成说明：阶段计数由 `phase1/preprocess.py` 与合并 xlsx 在 2026-05-19 实验配置下复现；shared 剔除分层自 `excluded_meaningless.csv` 与帖子 ID 归属交叉汇总。*
