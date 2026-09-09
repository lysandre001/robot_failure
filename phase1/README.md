# 第一阶段分析包 `phase1`

**入口**：[CURRENT.md](../CURRENT.md) · **功能契约**：[docs/functions.md](../docs/functions.md)

| 命令 | 作用 |
|------|------|
| `python run_preprocess.py` | Phase 1 清洗 → `data/clean/` |
| `python -m phase1.topic_modeling` | LDA / NMF / BERTopic 全网格 |
| `python -m phase1.run_topic_discovery` | L1/L2 topic discovery |
| `python -m phase1.topic_visualize` | BERTopic 可视化 |
| `python -m phase1.keyword_filter` | 关键词探索 → `output/explore/` |

- 操作手册（方法论/错误清单）：[RUNBOOK.md](RUNBOOK.md)
- 一次性/辅助 CLI：[tools/README.md](../tools/README.md)
- 分步 Notebook：`notebooks/phase1_structured.ipynb`

## 模块分层

| 类型 | 模块 |
|------|------|
| 编排 | `pipeline.py` |
| 清洗库 | `preprocess.py`, `comment_content_filter.py`, `xhs_io.py` |
| 主题建模 | `topic_modeling.py`, `topic_lda.py`, `topic_visualize.py`, `topic_discovery.py` |
| 探索 | `keyword_filter.py` |
| 标注库 | `manual_label.py`, `post_links.py` |
| 可选 legacy | `features.py`, `analysis.py`, `reports.py`（`--legacy-lexicon-features`） |
| 已归档代码 | `_archived/` |
