# 脚本索引

**入口**：[CURRENT.md](../CURRENT.md) · **功能契约**：[docs/functions.md](../docs/functions.md)

本目录为 **一次性导入、辅助导出、单实验分析** CLI。稳定管线入口在仓库根 `run_preprocess.py` 与 `python -m phase1.*`。

```bash
python -m tools.<模块名> --help
```

| 模块 | 作用 |
|------|------|
| `ingest_xhs_batch2_csv` | 第二批 CSV 容错 |
| `merge_xhs_batches_xlsx` | 两批合并 xlsx |
| `export_shared_analyzable_corpus` | 导出 shared corpus |
| `refresh_clean_post_labels` | 仅刷新帖子标签 |
| `export_comments_per_post` | 每帖 L1/L2 计数 |
| `sample_manual_label` | 人工标注抽样 |
| `label_comments_llm` | LLM 批量打标 |
| `audit_comment_content_filter` | 审计噪音规则 |
| `topic_post_dominance` | 主题 post 集中度 |
| `topic_like_concentration` | 主题内高赞集中度 |
| `compute_layer_cluster_metrics` | L1/L2/pooled 聚类指标 |
| `plot_topic_diagnostics` / `plot_topic_embeddings` | 实验可视化 |
| `video_match/*` | 跨平台视频匹配（旁路） |
| `weibo_build_post_comment_tree` | 微博数据（与小红书主流程无关） |

## 推荐顺序（新数据）

```bash
python -m tools.ingest_xhs_batch2_csv      # 仅新批次脏 CSV
python -m tools.merge_xhs_batches_xlsx
python run_preprocess.py --xlsx data/rawdata/小红书帖子数据_merged.xlsx
python -m tools.export_shared_analyzable_corpus
PYTHONUNBUFFERED=1 python -m phase1.topic_modeling --run-id <新id> --device cpu
```
