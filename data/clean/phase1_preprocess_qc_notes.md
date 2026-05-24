# 合并预处理 QC（2026-05-19）

## 规模

| 指标 | 值 |
|------|-----|
| 合并过滤后评论 | 46,051 |
| 唯一帖子 | 33（batch1: 16 + batch2 anchor: 17） |
| batch1 子集 | 29,215 |
| batch2 anchor 子集 | 16,836 |

## 与历史 baseline 对照

- `output/phase1/data/clean_comments_unified.csv`（31,245 行）为**旧次**清洗产物。
- 本次对 `1-小红书帖子数据.xlsx` **单独重跑** pipeline 得 29,215 行，与合并结果中 batch1 子集**完全一致**。
- 差异来自 pipeline/规则迭代，**非**两批合并引入。

## 第二批 CSV

- 跳过坏行约 1,568（字段数错位 + 无效 `帖子id`）
- 详见 `data/rawdata/xhs_merge_qc.md`
