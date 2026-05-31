# Topic Discovery 实习生 Runbook

> 面向接手 topic discovery 流程的人：在 **L1（一级评论）** 与 **L2（二级回复）** 两层独立跑完机器流程，再做人工编码、一致性检验、回填与敏感性。Pooled（全量 26,811）仅作敏感性附录。
>
> **代码**：[`phase1/topic_discovery.py`](../phase1/topic_discovery.py) · CLI [`phase1/run_topic_discovery.py`](../phase1/run_topic_discovery.py)
> **方法论总览**：[`topic_discovery_review.md`](topic_discovery_review.md)
> **实验目录**：`output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/`

---

## A. 环境与前置（一次性）

```bash
cd /Users/yilin/Desktop/project/robot_failure
# 已有 .venv；若需重建：
# python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/pip install gensim   # 若提示 No module named 'gensim'
```

确认本地有 BGE 模型缓存 `~/.cache/huggingface/hub/models--BAAI--bge-base-zh-v1.5/`；
否则首次 fit 会联网下载约 1.2 GB。

**必须用** `./.venv/bin/python`（系统 Python 会因 numpy/pandas ABI 报错）。所有命令从仓库根目录执行。M4 Mac `device=cpu` 即可，长任务请接电源。

### 父 run 前置（pooled HDBSCAN 与 embeddings）

L1/L2 复用父 run 的 `embeddings.npy`（按 row index 切片）与 `comment_content_filter.json`。
父 run **必须**已包含：

```
output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/
  config.json
  embeddings.npy
  shared_analyzable_corpus.csv
  comment_content_filter.json
  bert_hdbscan_mcs{30,50,80,100}/...   # 仅 pooled 用
```

若缺失，先跑：

```bash
PYTHONUNBUFFERED=1 ./.venv/bin/python -m phase1.topic_modeling \
  --run-id 2026-05-27_topic_merged_bge_hdbscan_sensitivity \
  --device cpu \
  --hdbscan-min-cluster-sizes 30 50 80 100
```

---

## B. 三条轨道：用哪张表、哪个目录

| 轨道 | 目录 | coder 表 | 状态 |
|------|------|----------|------|
| **L1 一级评论**（主分析） | `topic_discovery_l1/` | `coder*_sheet_final_nr90.csv` | 机器完成 ✅ |
| **L2 二级回复**（主分析） | `topic_discovery_l2/` | `coder*_sheet_final_nr45.csv` | 机器完成 ✅ |
| Pooled（敏感性附录） | `topic_discovery_review/` | `coder*_sheet_final_nr85.csv` | 已冻结；**不再作主标注** |

⚠️ **勿用**的旧产物：父 run 下的 `bert_hdbscan_mcs*/`（pooled 专用，不要直接拿去标注）、`hdbscan_mcs50_*` 原型表（流程探索遗留）。

---

## C. 机器全流程（每层独立）

每层固定顺序：`freeze` → `fit` → `select` → `review` → `codebook` → `sensitivity` → `validate` → `document`。
`--step all` 一次跑完（**L1/L2 会包含 fit；pooled 不会**，pooled 复用父 run）。

```bash
# 推荐：先 L1，后 L2（实现/调试阶段）
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 1 --base-mcs 30 --step all
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 2 --base-mcs 30 --step all

# 一键顺序（不传 --base-mcs 则用默认 50；务必先看 hdbscan_candidate_summary 再决定）
./.venv/bin/python -m phase1.run_topic_discovery --run-both-levels --base-mcs 30 --step all
```

### 各步成功标志

| 步 | 关键产物 | 怎么验 |
|----|----------|--------|
| freeze | `corpus_freeze.json` | 含 `comment_level`、`n_shared_comments`、SHA |
| fit | `bert_hdbscan_mcs{30,50,80,100}/{model,topics.csv,doc_topics.csv}` + `hdbscan_candidate_summary.csv` | 4 行（每个 mcs 一行） |
| select | `topic_number_cv_curve.{csv,png}` + `final_model_selection.json` + `topic_number_selection_notes.md` | 选定 nr 写在 selection.json；notes 解释为何拒绝 max-C_V |
| review | `topic_review_sheet_final_nr*.csv` + `coder{1,2}_sheet_final_nr*.csv` + `topic_comment_samples_final_nr*.csv` | `coder` 表行数 = 该层 topic 数（pandas `len()`；Excel 看会因换行虚高） |
| codebook | `topic_coding_codebook.md` | 注明 `nr` |
| sensitivity | `sensitivity/*.csv` | 4 张 |
| validate | `purity_validation_sample.csv` + `high_risk_topics_final_nr*.csv` | 含 risk_flags |
| document | `REPRO.md` + `output_manifest.csv` | manifest 关键文件 `exists=True` |

### 选 `base_mcs` 与 `nr` 的逻辑（**不要照搬 pooled**）

1. 看 `hdbscan_candidate_summary.csv` 的 `largest_share_valid` 与 `n_topics`。
2. 选 **largest_share ≤ ~12% 且 topic 数足够（>40）** 的 mcs 作为 base。
3. `select` 会扫描 nr=10–100，在结构 guard（largest≤12%、n_topics ∈ [40,100]）内挑 C_V 最高解；**拒绝 blind max-C_V**。
4. 若 guard 内无可选项，回退到 C_V 平台期上 largest_share 最小的解。

**当前选择记录（2026-05-31）**：

| 层 | base_mcs | nr | 最终 topic 数 | largest_share | outlier | C_V |
|----|----------|----|---------------|---------------|---------|-----|
| L1 | 30 | 90 | 89 | 7.6% | 43.3% | 0.605 |
| L2 | 30 | 45 | 44 | 10.0% | 47.8% | 0.505 |
| Pooled | 50 | 85 | 84 | 7.6% | 44.4% | 0.559 |

L2 outlier 略高于 L1/pooled 但仍在合理区间；L2 mcs=80/100 会塌缩成 mega-cluster（>93%），故 L2 与 L1 同取 mcs=30。

---

## D. 人工标注 SOP（每层独立）

1. 打开 `topic_comment_samples_final_nr{K}.csv`（按 `topic_id` 筛选；推荐用 Excel/Numbers 或 pandas）+ 你的 coder 表 `coderN_sheet_final_nr{K}.csv`。
2. **只填** `domain` / `label` / `notes`；**不要改** `topic_id`、机器列。
3. 证据顺序：`top_terms` → `sample_comments_10` → `representative_docs`（辅助）。
4. 允许 `mixed/unclear`；notes 必填子类型说明。
5. 另存为 `coderN_sheet_final_nr{K}_done.csv`（**勿覆盖空白模板**）。
6. Coder 2 独立重复 → `coder2_sheet_final_nr{K}_done.csv`。
7. 一致性检验：
   ```bash
   ./.venv/bin/python -m phase1.run_topic_discovery --comment-level 1 --base-mcs 30 --step agreement
   ./.venv/bin/python -m phase1.run_topic_discovery --comment-level 2 --base-mcs 30 --step agreement
   ```
8. 仲裁：填 `final_topic_map.csv`（从 `final_topic_map_template.csv` 复制），写 `final_domain`/`final_label`/`adjudication_notes`。
9. 回填：
   ```bash
   ./.venv/bin/python -m phase1.run_topic_discovery --comment-level 1 --base-mcs 30 --step backfill
   ./.venv/bin/python -m phase1.run_topic_discovery --comment-level 2 --base-mcs 30 --step backfill
   ```

**domain vs label vs notes**：
- `domain` = 较高层话语域（开放命名 → 同义合并）；同一 coder 内尽量保持词表稳定。
- `label` = 该 machine topic 的具体主题名（不必跨 topic 唯一）。
- `notes` = 依据、边界、混杂点、与相邻 topic 的差异。

⚠️ **本任务与 `human_label_llm/` 的 emotion/object 标注是独立项目**：这里只给 topic-level domain/label，不打逐条评论的情感/对象。

---

## E. 验收清单（交付负责人）

- [ ] `topic_discovery_l1/output_manifest.csv` 关键文件全部 `exists=True`
- [ ] `topic_discovery_l2/output_manifest.csv` 同上
- [ ] 两层 `topic_number_selection_notes.md` 各自解释 **为何** 选该 mcs/nr（非复制 pooled）
- [ ] `final_model/doc_topics_final.csv` 行数 = 该层 N；含 `topic_reduced`
- [ ] `coder*_sheet_final_nr*.csv` 行数 = 该层 topic 数（用 pandas `len`）
- [ ] 未修改 `shared_analyzable_corpus.csv`、pooled 已冻结产物、plan 文件
- [ ] 三层指标已填入 [`topic_discovery_review.md`](topic_discovery_review.md) 的对照表

---

## F. 常见踩坑

| 现象 | 原因 | 处理 |
|------|------|------|
| `final_nr unknown` | 未先跑 `select` | 先 `--step select`（或 `--step all`） |
| `BERTopic base model missing` | L1/L2 未跑 fit | 先 `--step fit` |
| `ModuleNotFoundError: gensim` | 缺依赖 | `./.venv/bin/pip install gensim` |
| `embeddings rows != shared_corpus rows` | 父 run 重跑过部分但未刷新 embeddings | 重跑 `phase1.topic_modeling --run-id <same>` |
| `CoherenceModel` ValueError | gensim 词表问题 | 代码已过滤 OOV；确保用最新 `topic_discovery.py` |
| C_V scan 慢 | 19 次 load BERTopic | 正常 ~1min；勿中断 |
| Excel 打开 coder 表行数爆炸 | 单元格内有换行 | 用 pandas `len()` 验证；或只看 `topic_comment_samples` 长表 |
| L1/L2 选了 nr=85 | 抄了 pooled 参数 | **禁止**；读该层 `final_model_selection.json` 与 `topic_number_selection_notes.md` |
| 想跳过 fit 重跑 select | `--step all` 会重 fit | 改用 `--step select` 单步（base_mcs 必须传） |

---

## G. 目标态命令清单（一键复现）

```bash
# 机器全流程（两层独立）
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 1 --base-mcs 30 --step all
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 2 --base-mcs 30 --step all

# 人工标注完成后
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 1 --base-mcs 30 --step agreement
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 1 --base-mcs 30 --step backfill
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 2 --base-mcs 30 --step agreement
./.venv/bin/python -m phase1.run_topic_discovery --comment-level 2 --base-mcs 30 --step backfill
```

完整产物清单：每层 `output_manifest.csv`；总览见 [`topic_discovery_review.md`](topic_discovery_review.md)。
