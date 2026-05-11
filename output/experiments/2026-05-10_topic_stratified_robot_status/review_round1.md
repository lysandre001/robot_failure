# 第一轮评估（完成度）— `2026-05-10_topic_stratified_robot_status`

评估时间：2026-05-10（跑通后立即记录）。

## 清单（对照 `idea/plan/plan_experiment_stratified_topic_by_robot_status.md` §5）

- [x] 父目录存在 `config_stratified_parent.json`，含 `merge_rule` 与四层 `strata`。
- [x] 四层均在 `strata/` 下，无空层 skip。
- [x] 每层有 `shared_analyzable_corpus.csv`、`run.log`、`config.json`、`comparison.md`。
- [x] 每层有 LDA/NMF 产物（`lda_k*` / `nmf_k*`）。
- [x] 各层 `n_comments ≥ 20`，均有 BERTopic 子目录与 `embeddings.npy`（或等价产物）。
- [x] `registry.csv`：已追加 `2026-05-10_topic_stratified_robot_status`（`topic_stratified_robot_status` / `stratified_4_groups`）。
- [x] 全量与分层计数：`n_shared`（18832）= 各层 `n_comments` 之和（16694）+ **未分层**（见下）。

## 发现的问题（须在第二轮或数据侧处理）

1. **`n_missing_robot_status_group` = 2138**  
   - 含义：在 **shared** 语料中，有 2138 条评论的 `robot_status_group` 为缺失（通常因 `帖子id` 未出现在 `config/post_category_by_post.csv`，或 `类别` 无法拆出合法 `robot_status`）。  
   - 影响：这些评论**未进入**任一层 LDA/NMF/BERTopic；分层实验覆盖的是 **16 694 / 18 832 ≈ 88.6%** 的 shared 评论，而非 100%。  
   - 建议：核对 `clean_comments_unified` 中帖子是否均已映射；或接受为「未编码帖」并写入论文方法段。

2. **小样本层（M8）**  
   - 失败 / 中性：`n_posts = 3`；弱势：`n_posts = 4`；强势成功：`n_posts = 5`。  
   - LOO 仅在 `n_posts ≥ 3` 时运行；解释上保持描述性，避免组间推断过度。

3. **日志中的 sklearn `RuntimeWarning`（matmul）**  
   - 与既有 RUNBOOK 说明一致：数值噪声，未中断运行。

## 命令与日志备份

- 父进程 tee 日志：`output/experiments/2026-05-10_topic_stratified_robot_status_parent.log`  
- 父 `run.log`：`output/experiments/2026-05-10_topic_stratified_robot_status/run.log`
