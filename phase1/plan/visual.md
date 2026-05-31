
第一部分：先纠正我自己的那句话

我原话拆解

「L1/L2 共存且交错——pooled 并非完全失败；局部存在 L2/L1 主导簇，这种密度不对称正是 mcs 最优值随层变化的根本原因。」

我的说法
实际证据强度
问题
「共存且交错」
2D 图能看到
但 2D UMAP 本来就会强行铺开，"看着交错"不等于"5D 里也交错"
「pooled 并非完全失败」
不能从这张图得出
失败/成功要看 C_V + largest_share + 人工 κ，不是 2D 长相
「密度不对称是 mcs 不同的根本原因」
这是猜想，没验证
样本量差异（L1=15901, L2=10910, Pooled=26811）就能造成 mcs 最优值不同——这是机械效应，不是语义结论

更诚实的说法应该是：
「2D 图上 L1/L2 大量重叠且没有清晰的空间分层 → 这与「pooled 在 embedding 上不会被分成两半」的预期一致；至于 mcs 最优值差异，从样本量差异就能推出一部分，不能单凭 2D 图归因到「密度不对称」。」

把图当作 suggestive evidence，不要当 proof。这是关键差别。

---

第二部分：聚类结果的完整评估方法论

NLP 学界对无监督聚类的评估有共识：没有任何单一指标能定结果好坏。必须 五条证据链 同时看。

证据链 1：嵌入空间内的几何质量

聚类在哪个空间发生，就在哪个空间评估。我们 HDBSCAN 跑在 5D UMAP 上，所以这些指标都要在 5D 上算：

指标
含义
区间 / 经验
我们有没有
DBCV (Density-Based Cluster Validity)
专为 HDBSCAN 设计；考虑簇内密度 vs 簇间稀疏
[-1, 1]，>0.4 算可信
pooled 旧 run 算过；L1/L2 没算
Silhouette
簇内紧 vs 簇间远（cosine 不直接适用）
[-1, 1]，>0.2 算有结构
pooled 旧 run 算过；L1/L2 没算
Largest topic share
是否塌成 mega-cluster
<12% 是我们设的 guard
✅ 都有
Topic size 分布（median / p25 / p75 / min）
簇大小是否均衡
不希望 min<10 或 max/median>50
✅ 都有

陷阱：在 2D UMAP 上算 silhouette 是常见错误——你在评估的是「降维质量」而不是「聚类质量」。

证据链 2：主题词语义一致性（topic-level）

指标
含义
区间
我们有没有
C_V coherence
词共现 + NPMI + 余弦的复合一致性（gensim）
中文经验 0.4–0.7
✅ 都有
NPMI (UCI)
简单的成对互信息归一化
[-1, 1]
❌ 没算（但比 C_V 简单稳定，建议加）
Topic diversity
各 topic top-N 词的去重率
[0, 1]，>0.7 算多样
❌ 没算
UMass
基于条件概率，倾向于偏好少 topic
负值，越大越好
❌ 没算

陷阱：C_V 在短文本上不稳定（Röder et al. 2015 之后社区一直有批评）；最好同时报 C_V + NPMI + diversity 三个，互相校验。

证据链 3：稳定性（reproducibility）

测试
怎么做
我们有没有
Seed stability
同参数换 random_state 重 fit 5 次，算两两 ARI（Adjusted Rand Index）
pooled 旧 run 有；L1/L2 没做
Bootstrap 稳定性
随机抽 90% 数据重跑，看核心簇是否仍出现
❌ 没做
Leave-one-post-out
剔一帖重跑，看主题分布偏移
pooled LDA 做过；BERTopic 没做
mcs 敏感性
比较不同 mcs 的结果
✅ 都有（candidate_summary.csv）
nr 敏感性
邻近 nr 的对比
✅ 都有（sensitivity/adjacent_topic_number_comparison.csv）

经验：ARI > 0.7 算稳定；< 0.5 说明聚类几乎是随机的。

证据链 4：人工语义验证（最重要、最贵）

方法
做法
阈值
状态
Word intrusion (Chang et al. 2009)
给 top-5 词 + 1 个混入的不相关词，让标注者找出 intruder
60%+ 准确率算 topic 有效
❌ 没做（适合做）
Topic intrusion
给一个文档 + 它的真实 topic + 2 个假 topic，让标注者选对的
70%+ 算可信
❌ 没做
Cohen's κ on topic labeling
两 coder 独立标 domain/label，算一致性
≥0.6 substantial, ≥0.8 almost perfect
⏳ 待 coder 完成
Domain mapping coverage
多少 machine topic 能被人工归到有意义的 domain，多少是 "mixed/unclear"
<20% mixed 算可接受
⏳ 待 coder 完成

这是聚类评估的 gold standard。前面三条都是手段，目的是减少这一条的人工成本。

证据链 5：外部效度（external validity）

测试
做什么
我们有没有
Topic × 已知元数据 crosstab
看 topic 分布是否与 robot_status / post_category 有理论预期的关联
部分有（topic_modeling 早期产物）
Topic × 时间
关键事件后某 topic 是否爆发
❌ 没做
Topic 与下游任务的预测能力
用 topic 分布预测 like_count 之类的目标
❌ 没做（也不一定该做）

陷阱：外部效度高 ≠ 聚类好；可能只是模型学到了浅层信号（长度、emoji、@提及）。

---

第三部分：如何读 2D embedding 图（最容易翻车的部分）

2D UMAP 的 5 条「不要」

1. 不要从 2D 距离推 5D 距离。UMAP 优化的是局部邻居关系，全局距离严重失真。两个看着远的簇在 5D 里可能是邻居。
2. 不要从 2D 簇形状推语义。UMAP 会把任何稠密区域拉成「岛屿」，包括纯噪音。
3. 不要从 2D 分离度判断聚类质量。HDBSCAN 在 5D 决策；2D 只是「事后投影」。
4. 不要在不同 dataset 间比较 2D 形状。L1 和 L2 的 UMAP 是各自独立 fit 的，坐标系不同源；只看簇的相对结构，不看绝对位置。
5. 不要把 random_state 不同的两张图当作「不同视角」。它们可能只是数值噪音。

2D UMAP 的 3 条「可以」

1. ✅ 看 sanity check：高分簇里词义是不是一致的、混在一起的两个簇是不是该合并。
2. ✅ 看 outlier 分布：outlier 是均匀散在所有簇周围（语义长尾），还是聚成一团（可能漏掉了一个 topic）？
3. ✅ 看相对密度结构：哪些 topic 紧密、哪些松散、哪些细长——这对人工 coder 的工作量预估有帮助。

用这套眼光重看我们的图

我之前说
严谨说法
「L1 簇分得开」
L1 在 2D 里看着分得开。真正的判据是 L1 的 DBCV 和 C_V，前者我没算，后者 0.605 算中等偏好。
「L2 簇更紧凑」
L2 在 2D 里看着更紧。也可能是 L2 样本少 + UMAP n_neighbors=15 相对更大造成的视觉效应。需要看 L2 在 5D 上的 silhouette/DBCV 才算。
「Pooled by level salt-and-pepper → 共享主题邻域」
2D 上看着是。也可能是 L1/L2 在 5D 里也共邻域（最可能）；也可能是它们在 5D 里分开但 UMAP 2D 把它们投到了同区域（不太可能但需排除）。
「密度不对称是 mcs 不同的根本原因」
过度归因。mcs 最优值不同可被三种因素解释，无法从这张图区分：① 样本量差异（机械效应）② 真实密度差异 ③ 语义内容差异。

---

第四部分：一个可执行的评估清单

写论文/向审稿人陈述时，按这个顺序给证据：

对每一层 (L1, L2, Pooled)：

1. 几何质量（5D 上）
   □ DBCV ≥ 0.4
   □ silhouette ≥ 0.15
   □ largest_share ≤ 12%
   □ min_topic_size ≥ 该层 N 的 0.2%

2. 主题词语义（topic-level）
   □ C_V ∈ [0.45, 0.70]
   □ NPMI ≥ 0
   □ Topic diversity ≥ 0.65
   □ 抽 10 个 random topic 自己手读 top-10 词，是否能 ≥ 7 个写出 1 句话主题

3. 稳定性
   □ Seed ARI ≥ 0.7（5 个 seed 两两均值）
   □ mcs 邻近候选（mcs±10）仍通过 guard
   □ nr 邻近候选（nr±5）largest_share 不超

4. 人工验证
   □ Coder κ ≥ 0.6 on domain
   □ mixed/unclear < 20%
   □ word intrusion accuracy ≥ 60%（抽 20 topic）

5. 外部效度（次要）
   □ topic × robot_status 有理论预期的差异（χ² test，但 effect size 比 p value 重要）
   □ 至少一个 topic 能被定性追溯到一个真实事件

我们当前对各层的填表（诚实版）——**完整数值与判定见** [`output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/EVALUATION_CHECKLIST.md`](../output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/EVALUATION_CHECKLIST.md)（2026-05-31 更新；机器指标来自 `layer_cluster_metrics.csv`）。

| 项 | L1 | L2 | Pooled |
|----|----|----|--------|
| DBCV (5D) | 0.330 warn | 0.226 warn | 0.301 warn |
| Silhouette (5D) | 0.659 ✅ | 0.619 ✅ | 0.656 ✅ |
| largest_share | ✅ 7.6% | ✅ 10.0% | ✅ 7.6% |
| C_V | ✅ 0.605 | ⚠️ 0.505 | ✅ 0.559 |
| NPMI / Diversity | 0.014 / 0.999 | −0.125 / 0.999 warn | −0.063 / 0.999 |
| Seed ARI | 未跑 | 未跑 | ✅ 1.0（pooled base mcs） |
| mcs 敏感性 | ✅ 表 | ✅ 表 | ✅ 表 |
| Coder κ | ⏳ 待标 | ⏳ 待标 | pooled 不主标 |
| Word intrusion | 本轮跳过 | 同上 | 同上 |
| Topic × robot_status | ⏳ backfill 后 | 同上 | 部分 |

---

第五部分：建议下一步（按收益/成本排序）

1. ~~补 DBCV / silhouette / NPMI / topic diversity~~ → 已完成：`tools/compute_layer_cluster_metrics.py` + `EVALUATION_CHECKLIST.md`
2. 补 seed ARI 稳定性（L1/L2，按需）—— pooled 已有
3. 人工 word intrusion（可选，Excel 手工）
4. 正式 coder 标注 → κ → backfill（贵但必须，已在流程中）
5. Topic × robot_status 关联（等 backfill 后自动产出）
6. 不追加更花哨的可视化（intertopic distance map、3D 等）。已经够了。

---