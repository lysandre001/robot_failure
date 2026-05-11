# 第一轮自检：分层跑通与完成度（2026-05-10）

对照计划：四层分别产出、M3/M6/M7、无 lexicon 预过滤。

## 完成度

- [x] 全量清洗后 `shared_analyzable_corpus_full.csv` 含列 `robot_status_group`；合并规则写入 `config_stratified_parent.json` 与各层 `config.json`（`stratified_merge_rule` / `faq_compliance`）。
- [x] 四层 `strata/{失败,弱势,中性,强势成功}/` 均有 `shared_analyzable_corpus.csv`、`comparison.md`、`a_lda_nmf_k_selection.csv`、BERTopic 子目录（HDBSCAN 多 mcs + KMeans）、`run.log`、`config.json`。
- [x] 每层内 LDA/NMF/BERTopic 共用该层同一份子表（**M7**）；每层独立 `embeddings.npy` / `umap_reduced.npy`。
- [x] 小样本自适应：`summary_corpus` 与各层 `config.json` 中记录 `adaptive_lda_k`、`adaptive_hdbscan_mcs` 等；UMAP `n_neighbors` 随 n 收缩。
- [x] **M6**：LDA 仍为 CountVectorizer 路径，NMF 为 TF-IDF（代码路径未改）。
- [x] 无 lexicon 子集预过滤（**M1**）。

## 数据备注（需知情）

- `summary_corpus_full.n_missing_robot_status_group`：**2138** 条 shared 评论因帖子缺少可解析的 `robot_status`（`post_category` 左段为空或整行缺失）未进入任一分层；分层合计评论数 = 16694，与四层之和一致。若需「分层=全 shared」，应补全 `config/post_category_by_post.csv` 后重跑。

## 遗漏修正

- 首轮无阻塞项；上述缺失标签为数据问题，非代码回退。
