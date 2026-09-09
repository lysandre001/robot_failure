# 第二轮自检：解释口径与文档（2026-05-10）

## 解释口径

- [x] **不可**将不同 `strata/` 下的 topic 编号视为同一理论维度；跨层仅可做代表词 Jaccard 等启发式对照（见 `comparison.md` 各层独立叙述）。
- [x] `robot_status_group` 来自研究设计（`强势`+`成功`→`强势成功`），非无监督聚类标签。
- [x] 失败/弱势/中性层仅 **3～4 帖**（**M8**）：主题分布仅作描述性阅读，不做与「强势成功」层的强比较推论。

## 文档

- [x] `phase1/RUNBOOK.md` 已增加 `--stratify-robot-status` 命令与产物说明（§3）。
- [x] `comparison_stratified_overview.md` 汇总各层 n_comments / n_posts 与输出路径。
- [x] `idea/lessons_learned_topic_modeling.md` 补充与全量流水线并列说明（分层用于状态内话语结构，全量用于总体对照）。

## 遗漏修正

- 若论文需要「分层覆盖全 shared」，请补帖子类别映射并重跑；代码层无需改合并逻辑。
