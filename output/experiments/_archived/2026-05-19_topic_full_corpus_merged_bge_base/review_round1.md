# Review round 1 — 2026-05-19_topic_full_corpus_merged_bge_base

## 数据

- 输入：`data/clean/clean_comments_unified.csv`（46,051 行 / 33 帖）
- shared corpus：28,055（coverage 60.9%）
- anchor 17 帖无 `post_category` 标签（`n_missing_robot_status_group` 11,127 属预期）
- 第二批 CSV 跳过 ~1,568 坏行 + 7 无效 `帖子id`（见 `data/rawdata/xhs_merge_qc.md`）

## KMeans k=7 主题词（可读）

| topic | 关键词摘要 |
|-------|------------|
| 0 | 机器人 / 人形 / 马拉松 |
| 1 | 可爱 / 好笑 / 有趣 |
| 2 | 跑不动 / 跑步 / 站不稳 |
| 3 | 遥控 / 操控 / 自主 |
| 4 | 意义 / 外卖 / 取代人类 |
| 5 | 降温 / 冰块 / 过热 |
| 6 | 去年今年 / 进步 |

## 质量指标（勿单看 silhouette）

- KMeans k=7：sil=0.37，mean_ari=0.99，largest_share=0.24
- HDBSCAN mcs=80：sil=0.44 但 outlier_rate=36%，largest_share=0.37

## post_dominance（k=7）

- 主题 5（降温）dominance=0.65 于帖 `69e481e8…` — 需对照是否帖效应
- 主题 3（遥控）dominance=0.46 于同帖

## 与 2026-05-09 全量实验对比

| | 05-09（16 帖） | 05-19（33 帖合并） |
|--|----------------|-------------------|
| n_raw | 31,245 | 46,051 |
| n_shared | 18,832 | 28,055 |
| k=7 主题 | 马拉松/可爱/遥控/轮子等 | 结构相似，新增「进步/意义」等 anchor 话语 |

## 结论

- 合并预处理与建模跑通，产物可用于 anchor schema 探索。
- 下一步：人工通读 `bert_kmeans_k7/samples.csv`；anchor 帖单独 residual 分析（见项目日记）。
