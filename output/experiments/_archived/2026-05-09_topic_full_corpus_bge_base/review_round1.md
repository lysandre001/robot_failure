# 第一轮自检（方法严谨性 & 产物完整性）

**日期**：2026-05-10  
**实验**：`2026-05-09_topic_full_corpus_bge_base`

## 检查项

| 项目 | 结论 |
|------|------|
| shared corpus 定义一致 | ✅ LDA/NMF/BERTopic 均基于 `build_shared_analyzable_corpus` 输出；`n_shared=18832`，覆盖率见 `config.json` / `comparison.md`。 |
| 不把 lexicon 当输入过滤器 | ✅ `topic_modeling.py` 不引用 lexicon；lexicon 仅 `keyword_filter` 探索用。 |
| LDA 输入为词袋计数 | ✅ `CountVectorizer`。 |
| NMF 输入为 TF-IDF | ✅ `TfidfVectorizer`。 |
| BERTopic：原文 embed；jieba 仅 c-TF-IDF | ✅ `docs_raw` 直送 encoder；`CountVectorizer(analyzer=jieba…)`。 |
| UMAP `random_state` | ✅ `TopicModelingConfig.random_seed`。 |
| Post-level averaging | ✅ `_export_cross_tabs` 含按帖聚合再平均；见各 `by_robot_status.csv`。 |
| HDBSCAN 灵敏度 | ✅ `mcs ∈ {100,200,400}`；`doc_topics.csv` 含 `topic_raw` / `topic_assigned`。 |
| 输出文件齐全 | ✅ `comparison.md`、`config.json`、`run.log`、`loo_post_sensitivity_lda_k7_robot_status.csv`、`embeddings.npy`、`registry.csv` 行。 |

## 发现并修正的问题（本轮）

1. **`config.json` 写入失败**：dataclass 内 `Path` 无法 `json.dump` → 已增加 `_json_safe_cfg_value`。
2. **沙箱/离线 HF**：`SentenceTransformer` 无外网时长时间阻塞 → **优先 `local_files_only=True`**，失败再在线拉取。
3. **`comparison.md` Jaccard 全 0**：BERTopic `Representation` 为类列表字符串 → 已 `_bert_representation_to_csv_terms` 解析后再算 Jaccard。

## 待后续阅读注意

- NMF 存在 sklearn `RuntimeWarning`（matmul）；接受为探索性运行噪声，不阻断流程。
- HDBSCAN `mcs=200/400` 时主题数极少（数据驱动）；解读以 `comparison.md` + 多样本 CSV 为准。
