# Drive 精简包说明（共 4 个文件）

| 文件 | 用途 |
|------|------|
| 本文件 | 为何选 **nr=35**、两层分工、扫描表 |
| `*_topics_topwords_original60_reduced34_nr35.csv` | 列 `analysis_tier`：`hdbscan_mcs80`（60 类）/ `reduce_topics_nr35`（34 类） |
| `*_topic_mapping_hdbscan60_to_reduced_nr35.csv` | 原 topic → 合并 topic（评论数） |
| `*_typical_comments_original_and_reduced_nr35.csv` | `layer` 区分两层；`comment_text` 全文；`subject_labels` 为标注列；`comment_excerpt` 短摘录 |

**两层：** 效度/主分析 = **60 类 + 41.5% outlier**；报告归纳 = **reduce_topics nr=35 → 34 类**。不用 keyword mega。

---

## 为何 `reduce_topics(nr=35)`

在已拟合 `bert_hdbscan_mcs80` 上，用 BERTopic **c-TF-IDF 余弦** 迭代 `reduce_topics`；**-1 不参与**，离群率各 nr 不变。

扫描 `nr ∈ {10,15,…,55}`，在 **12–35 报告档**内取 **C_V 最高** → **nr=35（34 类，C_V=0.526）**。  
英文热帖集中，**nr≤35 均不满足最大簇≤12%**；若强求扁平用 **nr=55**（54 类）作备选，但几乎未合并。

| nr | 实际 topic 数 | C_V | 最大簇占非离群比 |
|----|---------------|-----|------------------|
| 15 | 14 | 0.490 | 46.2% |
| 25 | 24 | 0.488 | 30.0% |
| 30 | 29 | 0.506 | 30.0% |
| **35** | **34** | **0.526** | **25.5%** |
| 55 | 54 | 0.516 | 8.8% |

完整曲线：`bert_hdbscan_mcs80/topic_reduce/topic_number_curve.csv`（仓库本地）。

**正文一句：** 60 类 HDBSCAN 上 `reduce_topics(nr=35)` 得 34 类报告层（12–35 档 C_V 最高）；60 类保留作主分析与效度；离群约 41.5% 不变。

*2026-11-19 · N=28096 · mcs=80*