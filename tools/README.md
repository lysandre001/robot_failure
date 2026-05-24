# 脚本索引

本仓库脚本分为 **稳定管线**（可重复跑、有契约）与 **tools/**（一次性或辅助 CLI）。

---

## 一、稳定管线（Pipeline）

这些脚本构成研究主流程，产物路径与参数有文档约定（`phase1/RUNBOOK.md`、`writing/data_preprocessing_protocol.md`）。

### 入口

| 命令 | 作用 |
|------|------|
| `python run_preprocess.py` | **Phase 1 清洗**（推荐入口；`run_phase1.py` 为兼容别名） |
| `python -m phase1.topic_modeling` | **主题建模**（shared corpus + LDA/NMF/BERTopic） |
| `python -m phase1.topic_visualize` | BERTopic 可视化（reload 已存模型） |
| `python -m phase1.keyword_filter` | 关键词探索（输出到 `output/explore/`，非正式实验） |

### 库模块（被入口调用，一般不直接 CLI）

| 模块 | 作用 |
|------|------|
| `phase1/pipeline.py` | 清洗流水线编排 |
| `phase1/preprocess.py` | 读 Excel、去重、统一长表 |
| `phase1/comment_content_filter.py` | 噪音规则（`contains_mention` 等） |
| `phase1/topic_lda.py` | 分词、停用词（主题建模共用） |
| `phase1/config.py` | 路径常量 |
| `phase1/xhs_io.py` | 小红书导入/合并**库函数** |
| `phase1/post_links.py` | 帖子链接表读取 |
| `phase1/manual_label.py` | 人工标注抽样**库函数** |

### 可选 / 遗留（默认关闭）

| 模块 | 说明 |
|------|------|
| `phase1/features.py` | lexicon 特征（仅 `--legacy-lexicon-features`） |
| `phase1/analysis.py` | 旧统计图、主题聚类 |
| `phase1/reports.py` | 质量报告、codebook 草案 |
| `phase1/_archived/` | 已归档实验代码 |

---

## 二、tools/（一次性 & 辅助）

**何时跑**：新批次 raw 数据入库、清洗后导出统计、人工标注批次、实验后 ad-hoc 分析。  
**运行方式**（仓库根目录）：

```bash
python -m tools.<模块名> --help
```

| 模块 | 标签 | 作用 |
|------|------|------|
| `ingest_xhs_batch2_csv` | 一次性 | 第二批 CSV 容错 → `xhs_batch2_wide_sanitized.csv` |
| `merge_xhs_batches_xlsx` | 一次性 | 两批合并 → `小红书帖子数据_merged.xlsx` + `posts.csv` |
| `export_comments_per_post` | 辅助 | 每帖 L1/L2 计数 → `comments_per_post_L1_L2.csv` |
| `sample_manual_label` | 辅助 | 每帖 30 条 L1 → `manual_label_l1_30perpost.csv` |
| `label_comments_llm` | 辅助 | LLM 批量打标 |
| `audit_comment_content_filter` | 辅助 | 审计噪音规则命中（不调整条 pipeline） |
| `topic_post_dominance` | 分析 | 单实验：主题 post 集中度 |
| `topic_like_concentration` | 分析 | 单实验：主题内高赞集中度 |
| `notebook_one_click_legacy` | 已弃用 | 旧 Notebook 一键（含 relation_v1） |
| `weibo_build_post_comment_tree` | 外部 | 微博数据，与小红书主流程无关 |

`phase1/` 下同名旧路径保留 **DEPRECATED shim**，仍支持 `python -m phase1.ingest_xhs_csv` 等旧命令。

---

## 三、推荐执行顺序

### 新批次 raw 数据入库（仅做一次）

```bash
python -m tools.ingest_xhs_batch2_csv
python -m tools.merge_xhs_batches_xlsx
```

### 常规研究循环（可重复）

```bash
python run_preprocess.py --xlsx data/rawdata/小红书帖子数据_merged.xlsx
cp output/phase1/clean_comments_unified.csv data/clean/
python -m tools.export_comments_per_post
PYTHONUNBUFFERED=1 python -m phase1.topic_modeling --run-id <run_id> --input-csv data/clean/clean_comments_unified.csv --device cpu
```

### 人工标注（按需）

```bash
python -m tools.sample_manual_label
python -m tools.label_comments_llm --help
```

---

## 四、命名约定

| 前缀/位置 | 含义 |
|-----------|------|
| `run_*.py`（仓库根） | 稳定管线入口 |
| `phase1/pipeline.py`, `topic_*.py` | 可重复实验逻辑 |
| `tools/*` | 一次性导入、辅助导出、单实验分析 |
| `phase1/_archived/` | 不再维护的历史代码 |
| `DEPRECATED` shim | 旧 import 路径兼容，新代码勿依赖 |
