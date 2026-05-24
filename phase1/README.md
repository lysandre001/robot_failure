# 第一阶段分析包 `phase1`

**稳定管线**：清洗库 + 主题建模。一次性/辅助 CLI 见 [`../tools/README.md`](../tools/README.md)。

- 清洗入口：`python run_preprocess.py`（仓库根目录；`run_phase1.py` 为别名）
- 主题建模：`python -m phase1.topic_modeling`
- 分步 Notebook：`notebooks/phase1_structured.ipynb`
- 操作手册：[`RUNBOOK.md`](RUNBOOK.md)
- 结构总览：[`../STRUCTURE.md`](../STRUCTURE.md)

## 模块分层

| 类型 | 模块 |
|------|------|
| 编排 | `pipeline.py` |
| 清洗库 | `preprocess.py`, `comment_content_filter.py`, `xhs_io.py` |
| 主题建模 | `topic_modeling.py`, `topic_lda.py`, `topic_visualize.py` |
| 探索 | `keyword_filter.py` |
| 标注库 | `manual_label.py`, `post_links.py` |
| 遗留 | `features.py`, `analysis.py`, `reports.py`（`--legacy-lexicon-features`） |
| 兼容 shim | `ingest_xhs_csv.py`, `build_merged_xlsx.py`, `export_comments_per_post.py` 等 → 转发至 `tools/` |
