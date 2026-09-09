# 第二轮自检（可复现性 & 文档）

**日期**：2026-05-10  
**实验**：`2026-05-09_topic_full_corpus_bge_base`

## 可复现性

| 项目 | 结论 |
|------|------|
| 单一命令重跑 | ✅ `python -m phase1.topic_modeling --device cpu`（见 `RUNBOOK.md`）。 |
| 输入指纹 | ✅ `config.json` 内 `input_csv_sha256`。 |
| 随机种子 | ✅ `config.json.config.random_seed`；UMAP/KMeans/LDA 等均引用。 |
| 嵌入缓存 | ✅ `embeddings.npy` 存在则跳过编码，加速一致结果（模型与语料不变时）。 |

## 文档与边界

| 项目 | 结论 |
|------|------|
| `comparison.md` 解释边界 | ✅ 文首声明探索性、非分类器 GT；`post_category` 来源说明。 |
| `keyword_filter` 冒烟 | ✅ 模式 A `--keywords "替代,失业"`；模式 B `--category species_competition`；产物含 `hits.csv` / `samples.md` / `summary.md`。 |
| `RUNBOOK.md` | ✅ 含错误清单摘要、重跑命令、目录说明、troubleshooting。 |
| `idea/will.md` | ✅ 决策日志追加本次 run_id 与清理说明。 |

## 结论

当前流水线可移交：**方法底线**（同语料、不混 lexicon）、**产物链**（实验目录 + registry + 探索目录分离）与**已知工程坑**（HF 离线、JSON Path）均已记录。
