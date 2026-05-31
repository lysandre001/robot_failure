# 合并预处理 QC（2026-05-29）

## 规模

| 指标 | 值 |
|------|-----|
| Phase 1 过滤后评论 | 41,251 |
| shared analyzable corpus | 26,811 |
| 唯一帖子 | 33（batch1: 16 + batch2 anchor: 17） |
| batch1 子集（clean） | 26,047 |
| batch2 anchor 子集（clean） | 15,204 |

## 标签 schema（2026-05-29）

- **config**：`config/post_category_by_post.csv` 使用 **`机器人状态`** + **`人的形象`** 两列。
- **clean 表**：`post_category = 机器人状态|人的形象`，并写入独立列 `robot_status`、`human_role`。
- 刷新命令：`.venv/bin/python -m tools.refresh_clean_post_labels`

## 产物同步

| 文件 | 说明 |
|------|------|
| `data/clean/clean_comments_unified.csv` | 已刷新标签 |
| `data/clean/shared_analyzable_corpus.csv` | 已重导（26,811） |
| `data/clean/shared_corpus_per_post.csv` | 已更新 per-post 统计 |
| `output/phase1/clean_comments_unified.csv` | 与 data/clean 同步 |

## 备注

- 仓库内暂无 `data/rawdata/小红书帖子数据_merged.xlsx`；本次未从原始 Excel 重跑 Phase 1，仅在现有 clean 表上刷新标签并重导 shared。
- `manual_label_l1_30perpost.csv` 尚未重抽；若用于分析请注意 `post_category` 可能仍为旧格式。
