# 实验输出

**当前结论**：先看 [README.md](../../README.md) § Current snapshot，再打开 `registry.csv` 中 `status=current` 的行。

## 目录约定

| 路径 | 含义 |
|------|------|
| `output/experiments/<run_id>/` | 当前或新实验（勿覆盖 current run） |
| `output/experiments/_archived/` | 历史 run（方法比较、分层敏感性等；**不可**当当前结论） |

## 进入某个 run 后怎么读

1. `config.json` — 输入 SHA、参数、FAQ 合规项
2. `run.log` — 完整 stdout
3. `comparison.md` — LDA / NMF / BERTopic 横切概览
4. Topic discovery（若已跑）：`topic_discovery_l1/`、`topic_discovery_l2/`

数据契约见 [data/canonical_comment_schema.md](../../data/canonical_comment_schema.md) §7；命令见 [README.md](../../README.md)。
