# Phase 1 包

**入口**：[README.md](../README.md) · **Schema**：[data/canonical_comment_schema.md](../data/canonical_comment_schema.md)

| 命令 | 作用 |
|------|------|
| `python run_preprocess.py` | 清洗 → `data/clean/` |
| `python -m phase1.topic_modeling` | 主题实验网格 |
| `python -m phase1.run_topic_discovery` | L1/L2 discovery |
| `python -m phase1.keyword_filter` | → `output/explore/` |

主题方法论：[RUNBOOK.md](RUNBOOK.md)。辅助 CLI 见根 README Cookbook。
