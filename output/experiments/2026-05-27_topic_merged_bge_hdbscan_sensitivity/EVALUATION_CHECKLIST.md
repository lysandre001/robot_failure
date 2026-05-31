# 三层 Topic Discovery 评估清单

> **机器指标来源**：[`layer_cluster_metrics.csv`](layer_cluster_metrics.csv)（2026-05-31，`python -m tools.compute_layer_cluster_metrics`）
> **方法论依据**：[`phase1/plan/visual.md`](../../../phase1/plan/visual.md)
> **2D 图**（[`topic_discovery_embedding_panels.png`](topic_discovery_embedding_panels.png)）**仅作 sanity check**，不作聚类质量判据。

---

## 1. 自动化指标

| 项 | L1 | L2 | Pooled | 阈值 | 判定 |
|----|----|----|--------|------|------|
| **C_V**（final nr） | 0.605 | 0.505 | 0.559 | 0.45–0.70 | L2 **warn**（偏低但 >0.45） |
| **NPMI**（final nr） | 0.014 | −0.125 | −0.063 | ≥ 0 | L1 pass；L2/Pooled **warn**（短文本 c_npmi 不稳定，与 C_V 交叉看） |
| **Topic diversity** | 0.999 | 0.999 | 0.999 | ≥ 0.65 | pass |
| **Silhouette**（5D，base HDBSCAN） | 0.659 | 0.619 | 0.656 | ≥ 0.15 | pass |
| **DBCV**（5D，base HDBSCAN） | 0.330 | 0.226 | 0.301 | ≥ 0.40 | **warn**（三层均未达；高 outlier 率下常见，需结合 silhouette + 人工 κ） |
| **largest_share** | 7.6% | 10.0% | 7.6% | ≤ 12% | pass |
| **raw outlier rate** | 43.3% | 47.8% | 44.4% | （报告，不设硬阈） | — |
| **min_topic_size**（base mcs） | 30 | 31 | 50 | ≥ 0.2%N（32/22/54） | L1/Pooled **warn**（borderline）；L2 pass |
| **Seed ARI** | — | — | 1.0（3 seeds，mcs=50） | ≥ 0.70 | Pooled pass；L1/L2 **未跑**（按需补） |

**参数**：L1 mcs=30 nr=90（89 topics）；L2 mcs=30 nr=45（44 topics）；Pooled mcs=50 nr=85（84 topics）。

---

## 2. 敏感性（已有，不重跑）

| 类型 | L1 | L2 | Pooled |
|------|----|----|--------|
| mcs 候选 | [`topic_discovery_l1/hdbscan_candidate_summary.csv`](topic_discovery_l1/hdbscan_candidate_summary.csv) | [`topic_discovery_l2/hdbscan_candidate_summary.csv`](topic_discovery_l2/hdbscan_candidate_summary.csv) | [`topic_discovery_review/hdbscan_candidate_summary.csv`](topic_discovery_review/hdbscan_candidate_summary.csv) + 根目录 `bert_hdbscan_mcs*` |
| nr 邻近 | [`topic_discovery_l1/sensitivity/adjacent_topic_number_comparison.csv`](topic_discovery_l1/sensitivity/adjacent_topic_number_comparison.csv) | [`topic_discovery_l2/sensitivity/`](topic_discovery_l2/sensitivity/) | [`topic_discovery_review/sensitivity/`](topic_discovery_review/sensitivity/) |

---

## 3. 人工验证

- [ ] **L1** coder κ（domain）≥ 0.6 — 标完 `coder*_sheet_final_nr90_done.csv` 后跑 `--step agreement`
- [ ] **L2** coder κ（domain）≥ 0.6 — 同上，`nr45`
- [ ] **mixed/unclear** 占比 < 20%（各层分别统计）
- [ ] **手读 10 topics**（从 `final_model/topics_final.csv` 随机抽 10 条，能否各写 1 句话主题）：
  - L1：__/10
  - L2：__/10
- [ ] **Word intrusion**：本轮跳过（可选 Excel 手工 10 题）
- [ ] **Topic × robot_status**：backfill 后见 `final_domain_by_robot_status.csv`；或一次性对 `doc_topics_final.csv` 做 crosstab

**标注入口**：L1 [`coder1_sheet_final_nr90.csv`](topic_discovery_l1/coder1_sheet_final_nr90.csv)（89 行）→ L2 [`coder1_sheet_final_nr45.csv`](topic_discovery_l2/coder1_sheet_final_nr45.csv)（44 行）。

---

## 4. 解读（必填）

1. **DBCV 未达 0.4**：三层 silhouette 均 >0.6，但 DBCV 0.23–0.33；与 ~44% HDBSCAN outlier 及短文本密度稀疏一致。不以 DBCV 单独否定模型，需结合 C_V、结构 guard 与人工 domain κ。
2. **L2 C_V=0.505**：二级回复更短、语用更偏反应词；在 12% guard 下为 structurally eligible 最优。与 L1 比绝对 C_V 意义有限。
3. **mcs 差异不宜过度归因「密度不对称」**：N/mcs 比 L1≈530、L2≈364、Pooled≈536，effective density 同量级；L1/L2 选 mcs=30 主因是 mcs≥50 时 outlier 升或 mega-cluster 风险。
4. **NPMI 为负**：gensim c_npmi 在中文短文本上常不稳定；topic diversity≈1.0 表明 top 词跨 topic 去重率高，与 C_V 结论不矛盾。
5. **2D embedding 图**：L1/L2 在 pooled 空间 salt-and-pepper 与「共享主题邻域、语用密度不同」一致；**不能**从 2D 分离度推断 5D 聚类质量。

---

## 5. 诊断图（figures 1–7）

目录：[`topic_diagnostics/`](topic_diagnostics/)（`python -m tools.plot_topic_diagnostics`）

| 图 | 文件 | 用途 |
|----|------|------|
| 1 | `01_outlier_rate_by_token.png` | outlier 率 vs 有效 token 分箱 |
| 2 | `02_token_ecdf_in_vs_out.png` | in-cluster vs outlier 长度 ECDF |
| 3 | `03_umap_outlier_overlay.png` | 2D UMAP 按 outlier 着色 |
| 4 | `04_topic_size_distribution.png` | topic 大小分布 |
| 5 | `05_pooled_level_x_outlier.png` | L1/L2 outlier 占比（pooled 标签） |
| 6 | `06_top15_topics.png` | 各层 top-15 topic |
| 7 | `07_mcs_sensitivity_panels.png` | mcs 敏感性 |

Notebook 浏览 outlier 帖子/评论：[`notebooks/topic_discovery_hdbscan_review.ipynb`](../../../notebooks/topic_discovery_hdbscan_review.ipynb) §5。

---

## 6. 维护说明

重算机器指标：

```bash
./.venv/bin/python -m tools.compute_layer_cluster_metrics \
  --run-id 2026-05-27_topic_merged_bge_hdbscan_sensitivity
```

更新本表 §1 数值与 §3 人工 checkbox；勿在别处 duplicate 全套表。
