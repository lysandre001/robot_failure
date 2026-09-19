# 协议与码本索引（Registry）

操作步骤见 [README.md](../README.md)。**数据列与路径契约**见 [data/canonical_comment_schema.md](../data/canonical_comment_schema.md)。

本文件只登记 **分文档路径与适用场景**，不重复正文。

---

## 1. Protocols（流程协议）

| ID | 文档 | 适用 |
|----|------|------|
| gold | [human_label_llm/label_data/GOLD_PROTOCOL.md](../human_label_llm/label_data/GOLD_PROTOCOL.md) | 人工金标交回、禁止改列 |
| comment_gate | [data/clean/comment_quality_gate_rules.md](../data/clean/comment_quality_gate_rules.md) | shared 纳入规则（各 batch 目录可有副本） |
| preprocess_hist | [data/clean/data_preprocessing_protocol.md](../data/clean/data_preprocessing_protocol.md) | 2026-05 XHS 两批快照；**非** current N |
| video_caption | [writing/video_caption_protocol.md](../writing/video_caption_protocol.md) | `post_media` / caption 旁路 |
| llm_labeling_design | [writing/codebook_llm_labeling.md](../writing/codebook_llm_labeling.md) | 全量 LLM 推断、checkpoint、parse_ok |
| public_observation | [docs/protocols/public_observation_deidentify.md](protocols/public_observation_deidentify.md) | IRB 8a：@ 排除、PII 侧车、public clean 无 user_id/location |

---

## 2. Codebooks（测量码本）

| ID | 文档 | 测量层 |
|----|------|--------|
| comment_three_layer | [config/codebook/codebook.md](../config/codebook/codebook.md) · [label_map.yaml](../config/codebook/label_map.yaml) | 主体 / 观念 stance+d1–d4 / 情感（论文主） |
| figure_stance_d | [data/clean/label_codebook_llm.md](../data/clean/label_codebook_llm.md) | figure + stance + D（legacy `tools.label_comments_llm`） |
| post_category | [config/post_category/README.md](../config/post_category/README.md) · Schema §3 | 机器人状态 × 人的形象（RQ3，**非**评论码本） |
| topic_l1_l2 | [output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/topic_discovery_l1/topic_coding_codebook.md](../output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/topic_discovery_l1/topic_coding_codebook.md) 等 | 冻结 XHS 主题 discovery |

Prompt 正文（非码本枚举）：`human_label_llm/prompt/*.md`（frontmatter 含 `label_map`）。

---

## 3. LLM labeling experiments

- **字段契约与 workflow**：[human_label_llm/experiment/README.md](../human_label_llm/experiment/README.md)
- **登记索引**：[human_label_llm/experiment/registry.csv](../human_label_llm/experiment/registry.csv)
- **模板**：`_labeling_template.yaml` · **共享超参**：`_defaults.yaml`（勿改，旧 sample10 冻结）
- **入口**：`python human_label_llm/run_experiment.py dryrun|infer|compare -c human_label_llm/experiment/<yaml>`

---

## 4. Topic experiments

- **登记**：[output/experiments/registry.csv](../output/experiments/registry.csv)
- **Current run**（只读）：`2026-05-27_topic_merged_bge_hdbscan_sensitivity`（shared N=26,811；与现 30,762 不混用 embeddings）
- **Intern runbook**：[writing/topic_discovery_intern_runbook.md](../writing/topic_discovery_intern_runbook.md)

---

## 5. Analysis outputs（论文数字）

- **码本 × 帖子分类**：`python -m tools.codebook_analysis` → [output/analysis/](../output/analysis/)
- **YouTube 帖子分类附录**：`python -m tools.post_category_appendix`
