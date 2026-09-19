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
| `post_category_appendix` | YouTube 帖子分类附录 CSV/LaTeX |
| `export_demo_top20_l1_l2_raw` | Top20 L1+1 L2 demo（含 YouTube clean+lang） |
| `export_comments_per_post` | 每帖 L1/L2 计数 |
| `export_demo_top_l2_by_post` | Demo：每帖 Top10 高 L2 一级评论 → `data/demo/` |
| `build_corpus_inventory` | 跨平台 clean 对比总表 |
| `sample_manual_label` | 人工标注抽样 |
| `label_comments_llm` | LLM 批量打标 |
| `audit_comment_content_filter` | 审计噪音规则 |
| `topic_post_dominance` | 主题 post 集中度 |
| `topic_like_concentration` | 主题内高赞集中度 |
| `compute_layer_cluster_metrics` | L1/L2/pooled 聚类指标 |
| `plot_topic_diagnostics` / `plot_topic_embeddings` | 实验可视化 |
| `video_match/run_post_media` | 帖子视听元数据：dense caption + ASR → `data/clean/post_media.csv` |
| `download_all_clips` | 按平台下载 30s clip 到 `data/rawdata/.../clips/` |
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
