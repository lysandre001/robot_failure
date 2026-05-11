# Phase 1 数据预处理：流程与 Lessons Learned

**维护范围**：从原始 Excel 到**清洗后统一评论表**及 Phase1 清洗产物；不包含 LDA / NMF / BERTopic。  
**对接人**：主题建模流程负责人 — 以本流程产出的 `clean_comments_unified.csv`（及 `data/` 下副本，见 `RUNBOOK`）为输入契约。  
**姊妹文档**（另一负责人）：[`idea/lessons_learned_topic_modeling.md`](lessons_learned_topic_modeling.md)

> 依据：`phase1/preprocess.py`、`phase1/pipeline.py`、`run_phase1.py`、`phase1/RUNBOOK.md`、`idea/will.md`。  
> **命令与路径细节**以 [`phase1/RUNBOOK.md`](../phase1/RUNBOOK.md) 为准。

---

## 一、在项目里的位置（研究背景，极简）

- 数据来自理论抽样帖；帖子级 **`状态|角色`** 与 [`config/post_category_by_post.csv`](../config/post_category_by_post.csv) 对齐，**不是模型推断的标签**。  
- 更完整的研究问题与矩阵定义见 [`idea/will.md`](will.md)。

---

## 二、端到端流程

| 步骤 | 做什么 | 代码 / 配置 |
|------|--------|-------------|
| 1 | 读 Excel（主表 + 导出计数/类别），合并 `post_category` | `load_raw_frames`、`merge_post_category` |
| 2 | 用 `post_category_by_post.csv` **覆盖**帖子级类别 | `apply_post_category_by_post` |
| 3 | 一级 / 二级评论按 `comment_id` 去重 | `build_level1`、`build_level2` |
| 4 | 纵向合并为统一长表；规范化 `content`；`char_len` | `unified_comments` |
| 5 | **过滤**：空内容、`min_chars`（可选）、[`comment_content_filter.json`](../config/topic_modeling/comment_content_filter.json)（可选） | `filter_valid_comments` |
| 6 | 默认**不**跑 lexicon 衍生特征；需要时 `--legacy-lexicon-features` | `phase1/pipeline.py` |
| 7 | 写 CSV、质量报告等 | `output/phase1/`、`output/phase1/data/` |

**入口**：`python run_phase1.py`（仓库根目录）。

**单独审计评论排除规则**（不跑整条 pipeline 时）：

```bash
python -m phase1.comment_content_filter
```

---

## 三、交付给下游的契约（主题建模负责人必读）

- **主表**：`clean_comments_unified.csv`（或 `output/phase1/data/` 下同名文件 — 以 `RUNBOOK` §2 与 `resolve_clean_comments_unified_csv` 逻辑为准）。  
- **列**：至少含 `content`、`comment_id`、`帖子id`、`post_category` 等统一表字段；下游会再构造 shared corpus，**不在此阶段做 lexicon 预过滤**。  
- **噪音规则变更**：改 `comment_content_filter.json` 会改变行数；重大变更建议在实验 `config.json` 或团队记录里标注日期与版本。

---

## 四、注意点（本流程专属）

1. **`comment_content_filter.json`**  
   纯 emoji / 仅 @ / 重复短片段等；调参后应用 `comment_content_filter` 模块看全量 `comment_content_filter_dropped.csv` 与 `comment_content_filter_report.json`。

2. **Pipeline 参数**  
   若启用 `content_rules_path`，与 `drop_repeated_single_char` 的语义以 **JSON 规则为准**（旧开关可能被忽略）。

3. **`post_category_by_post.csv`**  
   与 `will.md`「当前生效」矩阵一致；类别字符串格式 `状态|角色`，下游会拆成 `robot_status` / `human_role`。**帖是抽样单元**，评论不是来自同一「大类」的 i.i.d. 池子（避免下游误用，参见姊妹文档 **M8**）。

4. **默认关闭 lexicon 流水线**  
   避免探索性词典特征混入「默认清洗」；需要旧版报表时再开 `--legacy-lexicon-features`。误把词典当标签或预筛语料是**下游主题建模**的典型错误（**M1/M2**），但预处理侧应避免重新引入「默认全量打 lexicon 列」造成协作误解。

5. **产物路径**  
   `output/phase1/` 与 `output/phase1/data/` 可能并存；接手者以 `RUNBOOK` 与 `notebook_one_click` 的解析顺序为准。

---

## 五、Lessons Learned（预处理视角）

| 编号 | 标题 | 对本流程的含义 |
|------|------|----------------|
| **P2** | 删数据不删代码 | 改输出目录或过滤逻辑时，同步更新 `RUNBOOK`/脚本入口，过时代码标 `DEPRECATED`。 |
| **P3** | 文档与实现漂移 | 清洗规则以代码 + `comment_content_filter.json` 为准；口头「我们滤了什么」要对齐配置。 |
| **协作** | M1/M2 不在此实现，但要防回归 | 不要在默认 `run_phase1.py` 里重新引入「只保留词典命中评论」之类步骤；那是主题建模方法论错误。 |
| **标签** | 二维框架（`will.md` 2025-05-08） | `post_category` 承载研究设计；预处理负责与 CSV 对齐，不负责解释统计上的 i.i.d. 假设。 |

---

## 六、推荐阅读顺序（本负责人）

1. [`idea/will.md`](will.md) — 抽样与类别含义。  
2. [`phase1/RUNBOOK.md`](../phase1/RUNBOOK.md) §2 目录、§3 清洗命令。  
3. [`config/topic_modeling/comment_content_filter.json`](../config/topic_modeling/comment_content_filter.json) — 当前噪音规则。
