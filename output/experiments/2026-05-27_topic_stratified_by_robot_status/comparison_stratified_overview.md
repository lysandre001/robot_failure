# 分层主题建模总览（robot_status_group）

- 生成时间（UTC 本地）：2026-05-27T01:02:17
- 父 `run_id`：`2026-05-27_topic_stratified_by_robot_status`
- 合并规则：robot_status in {"强势","成功"} -> "强势成功"；失败/弱势/常态/中性各为一层；「混合」不进分层。（历史标签「成功|*」已废弃，表中应使用「强势」等现行取值。）

## 各层规模与输出

| stratum | n_comments | n_posts | BERTopic | output_dir |
|---------|------------|---------|----------|------------|
| 失败 | 2845 | 5 | ok | `/Users/yilin/Desktop/project/robot_failure/output/experiments/2026-05-27_topic_stratified_by_robot_status/strata/失败` |
| 弱势 | 3406 | 5 | ok | `/Users/yilin/Desktop/project/robot_failure/output/experiments/2026-05-27_topic_stratified_by_robot_status/strata/弱势` |
| 常态 | 1972 | 8 | ok | `/Users/yilin/Desktop/project/robot_failure/output/experiments/2026-05-27_topic_stratified_by_robot_status/strata/常态` |
| 中性 | 0 | 0 | skipped | `` |
| 强势成功 | 14832 | 11 | ok | `/Users/yilin/Desktop/project/robot_failure/output/experiments/2026-05-27_topic_stratified_by_robot_status/strata/强势成功` |

## 方法说明

- 每层内 LDA / NMF / BERTopic（若 n≥20）共用该层 `shared_analyzable_corpus.csv`（**M7**）。
- `robot_status_group` 来自研究设计，非模型聚类；**不可**将跨层 topic id 等同（第二轮自检）。
- 帖数极少层仅作描述性阅读（**M8**）。
