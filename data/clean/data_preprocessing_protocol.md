# 数据预处理流程说明（论文正文与附录）

> **版本**：2026-05-29；帖子编码改为 `机器人状态` + `人的形象` 两列（config），clean 表输出 `post_category`（`状态|角色`）及独立列 `robot_status` / `human_role`。Phase 1 已启用 `contains_mention`（v2）。  
> **canonical 产物**：`data/clean/clean_comments_unified.csv`（Phase 1，*N* = 41,251）；`data/clean/shared_analyzable_corpus.csv`（主题建模输入，*N* = 26,811）。  
> **复现入口**：`phase1/RUNBOOK.md` §2b–§3；实现 `phase1/preprocess.py`、`phase1/pipeline.py`、`tools/refresh_clean_post_labels.py`、`tools/export_shared_analyzable_corpus.py`。

---

## 一、正文可用稿（Methods / Data — 预处理段落）

### 1.1 数据来源与抽样设计

本研究的小红书评论数据来自两批相互独立的抓取，在分析前合并为统一语料库。

**第一批（理论抽样帖，*N* = 16）** 依据研究设计的「机器人状态 × 人类角色」矩阵进行目的性抽样。帖子级编码由研究者事先指定，存于 `config/post_category_by_post.csv`，列为 **`机器人状态`**、**`人的形象`**（如 `失败` + `抢救者`）；流水线合并为 `post_category = 机器人状态|人的形象`，并保留独立列 `robot_status` / `human_role`。**非**算法推断标签。

**第二批（anchor 扩展帖，*N* = 17）** 为综合类营销账号下与高互动量相关的机器人议题帖子，用于在独立于第一批抽样框的语料上探索话语结构的广度。该批在 config 中亦有编码（多为 anchor 扩展后的状态/角色标注）；分析中仍记为 **batch2_anchor** 批次标识（见 `data/rawdata/posts.csv` 合并顺序：前 16 帖为 batch1）。

两批帖子 **无重叠**（帖子 ID 交集为 0）。合并后共 **33** 帖、**41,251** 条去重评论（一级 22,386；二级 18,865）。探索性主题建模在进一步筛选后的 **26,811** 条 shared analyzable corpus 上进行（见 §1.4）。

### 1.2 原始数据格式与合并

- **第一批**：平台导出的 Excel（`1-小红书帖子数据.xlsx`），含宽表「小红书帖子数据」与「导出计数_帖子id」。
- **第二批**：同结构 CSV（`2-小红书帖子数据.csv`），合并前经容错解析（附录 A.1）。

合并宽表：`data/rawdata/小红书帖子数据_merged.xlsx`（若本地已生成）；帖子链接见 `data/rawdata/posts.csv`。

### 1.3 评论级清洗（Phase 1）

在合并宽表上运行 `run_preprocess.py` → `phase1/pipeline.py`，**两批适用完全相同规则**。

1. **帖子级元数据**：宽表左连接计数表；再用 `config/post_category_by_post.csv` 覆盖 **`post_category` / `robot_status` / `human_role`**（`load_post_category_table`）。
2. **评论展开与去重**：一级按 `一级评论id`、二级按 `二级评论id` 去重；纵向合并为统一长表。
3. **文本规范化**：`content` 首尾空白剔除；`char_len`。
4. **有效性过滤**：空内容 + `config/topic_modeling/comment_content_filter.json`（v2：含 `@` 提及等）。

输出 `clean_comments_unified.csv`（*N* = 41,251）。列含：

| 列 | 说明 |
|----|------|
| `post_category` | 合并标签，格式 `机器人状态\|人的形象` |
| `robot_status` | 机器人状态（如 失败、弱势、常态、混合、强势） |
| `human_role` | 人类角色（如 观众、抢救者、被超越者） |

**仅刷新标签（不重跑 Excel 清洗）**：

```bash
.venv/bin/python -m tools.refresh_clean_post_labels
```

### 1.4 主题建模用语料（shared analyzable corpus）

在 Phase 1 输出上施加第二层筛选（`build_shared_analyzable_corpus`）：

- 规范化后长度 &lt; 4 字符；
- 相同 JSON 噪音规则（Phase 1 已剔 @ 后，shared 阶段主要再筛重复片段等残留）；
- 纯标点 / URL / 长串数字；
- jieba 分词去停用词后有效词数 &lt; 2（**仅纳入判定**；BGE 编码仍用原文）；
- **全库**正文归一化去重（`duplicate_text`）。

最终 *N* = **26,811**（占 Phase 1 **65.0%**）。batch1 **18,349** 条（70.4%）；batch2 **8,462** 条（55.7%）。

**导出（不跑 LDA/NMF/BERTopic）**：

```bash
.venv/bin/python -m tools.export_shared_analyzable_corpus
```

### 1.5 与主题建模相关的文本处理说明

- **语义向量（BGE）**：`BAAI/bge-base-zh-v1.5`，输入评论 **原文**。
- **主题词提取**：jieba + 停用词表，与向量空间分离。

### 1.6 人工标注抽样

从 `clean_comments_unified.csv` 按帖分层抽取一级评论（每帖最多 30 条）。见 `data/clean/manual_label_l1_30perpost.csv`（*N* = 945；**标签刷新后若未重抽，该表可能仍为旧 `post_category` 格式**）。

---

## 二、附录 A：流程、参数与阶段计数

### 附录 A.1 第二批 CSV 容错导入

**脚本**：`python -m tools.ingest_xhs_batch2_csv`

| 指标 | 数值 |
|------|------|
| 跳过坏行 | 1,568 |
| 保留宽表行 | 20,988 |
| 唯一帖子 | 17 |

详见 `data/rawdata/xhs_merge_qc.md`。

### 附录 A.2 合并与 Phase 1 阶段计数

| 阶段 | 描述 | 行数 | 唯一帖子 |
|------|------|------|----------|
| A4 | 一二级合并（过滤前） | 56,704 | 33 |
| **A5** | **Phase 1 过滤后（clean）** | **41,251** | **33** |

**A5 分层**：

| 子集 | 帖数 | 评论数 | 一级 | 二级 |
|------|------|--------|------|------|
| batch1 | 16 | 26,047 | 14,259 | 11,788 |
| batch2 anchor | 17 | 15,204 | 8,127 | 7,077 |

**A4→A5 剔除（15,453 条）**：空内容 295；噪音规则 15,158（`contains_mention` 13,630；`repeated_fragment` 1,490；`pure_emoji` 38）。

完整阶段表：`data/clean/phase1_preprocess_stage_summary.csv`。

### 附录 A.3 `comment_content_filter.json`（v2）

| 规则 | 要点 |
|------|------|
| `pure_emoji` | 去空白后仅 emoji |
| `contains_mention` | 含 `@`/`＠` 即排除 |
| `repeated_fragment` | 短片段重复 ≥3 次 |

### 附录 A.4 shared corpus 筛选（A5→shared）

**输入 SHA256**（`clean_comments_unified.csv`，2026-05-29 标签刷新后）：  
`6149c1cf84964a7576413cc8fda31187fc12ee9ae0cbf9d68743b38e607f6dfc`

| 剔除原因 | 条数 |
|----------|------|
| `effective_tokens_lt_min` | 8,783 |
| `duplicate_text` | 3,388 |
| `empty_or_too_short` | 2,262 |
| 其它（纯标点等） | 7 |
| **保留（shared）** | **26,811** |

统计摘要：`data/clean/shared_corpus_summary.json`；剔除行：`data/clean/excluded_meaningless.csv`。

**分层映射（`robot_status_group`）**：`强势`/`成功` → `强势成功`；`常态`/`混合` → `中性`；其余 `失败`/`弱势`/`中性` 各一层。全部 26,811 条均有分层标签（含 batch2）。

### 附录 A.5 每帖规模与 shared 保留率

`data/clean/shared_corpus_per_post.csv`（含 `robot_status`、`human_role`、clean/shared 计数、保留率、帖子链接）。

---

## 三、附录 B：方法学说明

### B.1 标签 schema 变更（2026-05-29）

| 时期 | config 格式 | clean 表 |
|------|-------------|----------|
| 早期 | 单列 `类别` 或 `状态\|角色` | 仅 `post_category` |
| **当前** | **`机器人状态` + `人的形象`** | `post_category` + `robot_status` + `human_role` |

下游 `topic_modeling.py`、人工标注、per-post 汇总均通过 `load_post_category_table()` 读取，保证与 config 一致。

### B.2 两批处理同规

Phase 1 与 shared 均为同一函数、同一 JSON/阈值；batch2 额外损失来自 CSV 导入与内容分布（更短、更重复），非另一套规则。

### B.3 `duplicate_text`

全库 `casefold()` 去重，保留遍历顺序首次出现；合并宽表 batch1 在前，跨批相同正文时 batch1 优先。

---

## 四、附录 C：产物文件清单

| 路径 | 用途 |
|------|------|
| `config/post_category_by_post.csv` | 帖子编码源（`机器人状态`、`人的形象`） |
| `data/clean/clean_comments_unified.csv` | Phase 1 主输出（41,251） |
| `data/clean/clean_comments_unified_before_filter.csv` | 过滤前统一长表（56,704） |
| `data/clean/shared_analyzable_corpus.csv` | 主题建模/聚类输入（26,811） |
| `data/clean/excluded_meaningless.csv` | shared 剔除行及原因 |
| `data/clean/shared_corpus_summary.json` | shared 筛选统计 |
| `data/clean/shared_corpus_per_post.csv` | 每帖 clean/shared + 标签 |
| `data/clean/comments_per_post_L1_L2.csv` | 每帖一/二级计数 |
| `data/clean/phase1_preprocess_stage_summary.csv` | 阶段计数 |
| `data/clean/manual_label_l1_30perpost.csv` | 人工标注候选 |

---

## 五、附录 D：表稿示例

**表 D-1 各阶段评论条数**

| 阶段 | *N* |
|------|-----|
| 评论去重合并（A4） | 56,704 |
| Phase 1 清洗后（A5） | **41,251** |
| shared analyzable corpus | **26,811** |

**表 D-2 两批在 clean 与 shared 的规模**

| 子集 | 帖数 | Phase 1 | shared | 保留率 |
|------|------|---------|--------|--------|
| batch1 | 16 | 26,047 | 18,349 | 70.4% |
| batch2 anchor | 17 | 15,204 | 8,462 | 55.7% |
| **合计** | **33** | **41,251** | **26,811** | **65.0%** |

---

## 六、复现命令（当前仓库）

```bash
# 若已有 merged xlsx：全量 Phase 1 清洗（直接写入 data/clean/）
python run_preprocess.py --xlsx data/rawdata/小红书帖子数据_merged.xlsx

# 仅刷新帖子标签（config 变更后）
.venv/bin/python -m tools.refresh_clean_post_labels

# 导出 shared corpus（不跑主题建模）
.venv/bin/python -m tools.export_shared_analyzable_corpus

# 每帖计数
.venv/bin/python -m tools.export_comments_per_post
```

---

*文档生成说明：阶段计数与 shared 统计由 2026-05-29 标签刷新后产物复现；filter 剔除分层见 `comment_content_filter_report.json`（全库 Phase 1 规则命中）。*
