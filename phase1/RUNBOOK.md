# Phase 1 RUNBOOK：探索性主题建模 + 关键词筛选

面向接手者：当前阶段以 **全量可分析评论（shared corpus）** 上的探索性主题建模为主，**不依赖 lexicon**、**不训练 judge 模型**、**不把关键词命中当类别标签**。

---

## 1. 当前阶段说明

- 任务定位：**Phase 1 数据处理 + 探索性主题建模**。目标是在清洗后的小红书评论上，比较 LDA / NMF / BERTopic 的主题结构，为后续 codebook、人工编码、理论抽样提供候选主题。
- **本阶段不做**：训练 judge、把 lexicon 当 ground truth、用关键词命中给评论打类别标签、用 POS 词性预过滤主题建模输入。
- 主入口：[`phase1/topic_modeling.py`](topic_modeling.py)。
- 探索工具：[`phase1/keyword_filter.py`](keyword_filter.py)，输出严格隔离到 `output/explore/`，不进 `output/experiments/`。

---

## 2. 目录速览（六个角色）

| 路径 | 角色 |
|------|------|
| `output/phase1/data/clean_comments_unified.csv` | 清洗后**主评论表**，唯一原始输入 |
| `config/topic_modeling/comment_content_filter.json` | 正文噪声/无意义评论规则（构造 shared corpus 用） |
| `config/post_category_by_post.csv` | 帖子 → `状态\|角色`，**`robot_status` / `human_role` 的唯一来源** |
| `output/phase1/` | 清洗流水线（[`pipeline.py`](pipeline.py)）的中间产物 |
| `output/experiments/<run_id>/` | **正式实验**目录：含 `comparison.md`、`config.json`、`run.log`、`review_round1.md`、`review_round2.md` 等 |
| `output/explore/<timestamp>_<name>/` | **关键词筛选**临时探索产物（不是正式分析） |

`output/experiments/registry.csv` 维护活跃实验列表，列含 `status` / `decision`。

---

## 3. 重跑命令（4 个步骤）

```bash
# 1) 清洗（默认不再产 lexicon 衍生表）
python run_phase1.py
# 仅当需要旧 lexicon 特征：
python run_phase1.py --legacy-lexicon-features

# 2) 全量主题建模（LDA + NMF + BERTopic）
PYTHONUNBUFFERED=1 ./.venv/bin/python -m phase1.topic_modeling --device cpu
# 或自定义 K 与 HDBSCAN 灵敏度：
./.venv/bin/python -m phase1.topic_modeling \
    --embedding-model BAAI/bge-base-zh-v1.5 \
    --lda-k 5 7 10 12 \
    --bert-kmeans-k 5 7 10 \
    --hdbscan-min-cluster-sizes 100 200 400

# 3) 两轮自检-修正循环（人工对照本 RUNBOOK §6 阅读，并写入 review_round{1,2}.md 到实验目录）

# 4) 关键词筛选探索（任意时刻）
./.venv/bin/python -m phase1.keyword_filter --out 替代焦虑 \
    --keywords "替代,失业,抢饭碗,被取代"
./.venv/bin/python -m phase1.keyword_filter --out lex_species \
    --lexicon config/relation_lexicon_v1.csv --category species_competition
```

---

## §0 错误清单（接手者必读）

> 每条都要在新流程里规避。

### §0.1 方法论错误

| # | 错误 | 现象 | 原因 | 避免方式 |
|---|---|---|---|---|
| **M1** | **lexicon 子集预过滤** | 把 31,245 → 8,421 条做主题建模 | 主题建模本质无监督，预过滤等于偷偷加了一个分类器 | 全量输入；lexicon 只能在事后做评估（且当前阶段也不做） |
| **M2** | **lexicon 当 ground truth** | 把 6 关系 + 4 指代当"标准答案"算混淆矩阵 | 这些是研究者的探索性词典，没有 IRR 验证 | 不把 lexicon 当 judge；要 judge 就先做 codebook + IRR |
| **M3** | **隐式短文档过滤** | `build_topic_documents` 默认 `min_tokens=3` 把 31,245 → 13,334（丢 56%） | 函数默认值不显眼 | 在脚本最开头打印过滤前后行数；过滤参数显式传值 |
| **M4** | **K 选择只看一个指标** | LDA perplexity 单调降；TF-IDF KMeans silhouette 只有 0.06 | 单指标在 BoW 短文本上不可靠 | 多指标（perplexity + topic coherence + 主题大小均衡 + 人工核读） |
| **M5** | **char_bigram 静默回退** | jieba 没装时 `_setup_tokenizer` 自动用 char_bigram，主题词全是 "机器/器人/拉松" 这种 2 字碎片 | fallback 没报错 | 启动期严格校验：缺 jieba 直接 raise；分词器选择写进 `config.json` |
| **M6** | **LDA 用 TF-IDF 输入** | 把 TF-IDF 矩阵喂给 LDA | LDA 假设输入是词频计数（count），TF-IDF 会破坏生成模型假设 | LDA 一律用 `CountVectorizer`；NMF 才用 `TfidfVectorizer` |
| **M7** | **不同模型看到不同语料** | LDA 因短文本过滤少看一半评论，BERTopic 看全量，二者差异混入语料差异 | 比较对象不一致 | 先构造一个 shared analyzable corpus；LDA/NMF/BERTopic 主比较都用同一批评论；另保留 full-input 计数只作为覆盖率报告 |
| **M8** | **把 post_category 当独立样本** | 爆款帖子评论量大，某一帖可能主导 category 结论 | 16 个 post 是理论抽样单元，不是 i.i.d. 评论池 | 输出 `topic × post_id`；先在每个 post 内算主题比例，再按 robot status/category 汇总；增加 leave-one-post-out sensitivity |

### §0.2 工程错误

| # | 错误 | 现象 | 原因 | 避免方式 |
|---|---|---|---|---|
| **E1** | **CountVectorizer 在 BERTopic 翻车** | `ValueError: max_df corresponds to < documents than min_df` | BERTopic 的 c-TF-IDF 输入是「按主题拼成的 K 个长文档」，用 `min_df=5, max_df=0.6` 文档级阈值会矛盾 | BERTopic 的 vectorizer 用 `min_df=1, max_df=1.0`；token 频率限制放在 c-TF-IDF 之后再做 top-k 截取 |
| **E2** | **代理卡住下载** | pip 跑 16 分钟一个包没装上，连到 `localhost:7897` 代理 ESTABLISHED 但卡住 | 系统级代理被自动检测到 | 装包前 `env \| grep -i proxy`；必要时 `unset HTTPS_PROXY HTTP_PROXY ALL_PROXY` 后再 pip install |
| **E3** | **pip 进度被 tail 吞掉** | 用 `pip install ... \| tail -15` 看不到进度，只能干等 | tail 在 stdout 没刷新就不显示 | `pip install ... > /tmp/pip.log 2>&1 &` + 定期 `tail -f` |
| **E4** | **embedding 不缓存** | 每次重跑 BERTopic 都重编码 6000 条评论 | 没存中间产物 | encode 后立即 `np.save(run_dir/"embeddings.npy", embeddings)`，下次先查缓存 |
| **E5** | **模型大小拍脑袋** | 想用 large（1.3GB，45 min 下载），实际网速 150 KB/s 拖死流程 | 没量化下载预估 | 下载前 `du -sh ~/.cache/huggingface/hub/<model>`，按当前网速算 ETA；研究项目默认 base，small 仅做冒烟测试 |
| **E6** | **沙箱/无外网时 ST 阻塞** | `SentenceTransformer(...)` 长时间无输出 | HF Hub 解析远端 revision 阻塞 | 代码先尝试 `local_files_only=True`，命中缓存秒开；首次下载需联网 |
| **E7** | **`config.json` 写入失败** | `TypeError: PosixPath is not JSON serializable` | dataclass 字段含 `Path` / `tuple` | 提供 `_json_safe_cfg_value` 做转换 |

### §0.3 流程错误

| # | 错误 | 现象 | 原因 | 避免方式 |
|---|---|---|---|---|
| **P1** | **多个旧实验混在 output/experiments/** | 4 个 run_id 共存，新人不知道哪个是当前结论 | 没有"标记 active vs archived" | `output/experiments/registry.csv` 加 `status` 列；archived 移到子目录 `_archived/` |
| **P2** | **代码与产物不同步** | `topic_relation_v2.py` 还在但产物已应该删 | 删数据不删代码 | 同一次清理；保留代码也要在文件头标注 `# DEPRECATED 2026-05-09` |
| **P3** | **plan 与代码漂移** | will.md 提到 BERTopic，实际是 LDA char_bigram | 没有"这次实验跑了什么"的 single source of truth | 每个实验 run_id 必须含 `config.json`，will.md 决策日志引用 run_id |

### §0.4 BERTopic 官方注意事项（来自 [BERTopic FAQ](https://maartengr.github.io/BERTopic/faq.html)）

| # | FAQ 主题 | 要点（原文摘要） | 我们的处理 / 写进代码 |
|---|---|---|---|
| **C1** | **中文必须自定义 jieba CountVectorizer** | "CountVectorizer tokenizes text by splitting whitespace which does not work for Chinese. To get it to work, you will have to create a custom CountVectorizer with jieba." | `phase1/topic_modeling.py` 必须传 `vectorizer_model=CountVectorizer(analyzer=_jieba_tokenize, ...)`；`token_pattern=None` 否则 sklearn 会发警告并用默认 |
| **C2** | **停用词时机：先 embed 再去停用词**（反直觉） | "removing stop words as a preprocessing step is not advised as the transformer-based embedding models that we use need the full context to create accurate embeddings. Instead, we can use the CountVectorizer to preprocess our documents **after** having generated embeddings" | BGE encoder 输入用**原文**（带停用词、表情、emoji）；停用词只在 CountVectorizer 的 `analyzer` 里去；**严禁**对 docs 提前去停用词再喂给 BGE |
| **C3** | **结果不可重现（UMAP 随机）** | "Due to the stochastic nature of UMAP, the results from BERTopic might differ even if you run the same code multiple times. ... set a `random_state` in UMAP" | UMAP 必须传 `random_state=42`；`config.json` 同时记录 BERTopic、UMAP、HDBSCAN、KMeans 的 seed |
| **C4** | **calculate_probabilities 默认关闭** | "Calculating the probabilities is quite expensive ... only use it if you do not mind waiting a bit before the model is done running or if you have less than a couple of hundred thousand documents" | 我们 31k 文档**默认 False**；只在最终选定 K 后做一次 `topic_model.approximate_distribution(docs)` 替代 |
| **C5** | **内存（low_memory）** | "set `low_memory` to True when instantiating BERTopic. This may prevent blowing up the memory in UMAP" | `BERTopic(low_memory=True)`，避免后期评论增到几十万时改 |
| **C6** | **如何减少 outlier**（HDBSCAN） | 三种方法：1) `min_samples` 单设比 `min_cluster_size` 小；2) 训练完用 `topic_model.reduce_outliers(docs, topics)`；3) 直接换 KMeans（无 outlier） | 我们已用 KMeans K=5/7/10 作并行路线；HDBSCAN 路线**额外加一步** `reduce_outliers(strategy="c-tf-idf")` 把异常点重新指派；保留原始 outlier 标签为 `topic_raw`，重新指派后为 `topic_assigned` |
| **C7** | **主题数控制** | "set the `min_topic_size` ... higher (e.g., 300)" / "n_neighbors ... higher (e.g., 200)" / "nr_topics='auto'" | HDBSCAN 不只跑一个值：`min_cluster_size=100/200/400` 做 sensitivity；主报告默认解读 200；UMAP `n_neighbors=15`（默认）；最终若主题过多可用 `nr_topics="auto"` 让模型合并相似主题 |
| **C8** | **离线运行 / 网络** | "sentence-transformers ... it searches automatically for an embedding model locally. If it cannot find one, it will download" | 下载前先 `huggingface-cli download BAAI/bge-base-zh-v1.5` 全量到 `~/.cache/huggingface/hub/`；运行时优先 `local_files_only=True`（与 **E6** 联动） |
| **C9** | **Apple Silicon 已知坑** | "There are known issues with upstream dependencies for this architecture, for example numba" | 我们 mps 已能跑通；若未来 numba/hdbscan 报 arm64 错，fallback 是 VS Code Dev Container（见 §7 Troubleshooting） |
| **C10** | **是否需要预处理** | "No. By using document embeddings there is typically no need to preprocess ... if you have data that contains a lot of noise, for example, HTML-tags, then it would be best to remove them" | 小红书评论的 `[doge][笑哭R]` 等表情标记**保留给 BGE**（提供情感上下文），但在 jieba tokenizer 里去掉（c-TF-IDF 不让它们进主题词）；URL / @用户名 / 长数字 ID 在 `clean_text` 里仍然去掉（噪声不是上下文） |

**关键交叉引用**：

- **E1 + C2 共同含义**：BERTopic 的两个数据流要分清——`embedding_model.encode(docs)` 看到**原文**（C2、C10），`vectorizer_model` 内部的 `CountVectorizer` 看到**分词后版本**（C1）；二者不可互相污染。
- **C4 + C6 共同含义**：用 KMeans 时 `calculate_probabilities` 无效（仅 HDBSCAN/cuML HDBSCAN 才生效），要文档-主题分布得用 `approximate_distribution`。
- **M3 + C7 + C5 共同含义**：所有"过滤/限制/降维"参数都要显式列在 `config.json`，并打印过滤前后行数；后接手者一看就知道这次跑了什么。

更多背景见 [BERTopic 论文 arXiv:2203.05794](https://arxiv.org/abs/2203.05794)。

---

## 6. 如何读 `output/experiments/<run_id>/`

阅读顺序（从入口到细节）：

1. `review_round1.md` / `review_round2.md` — 两轮自检；任何疑问先看这两份。
2. `config.json` — 输入 SHA、随机种子、`faq_compliance.{C1..C10}`、`POS_main_pipeline=false`、shared corpus 覆盖率。
3. `run.log` — 完整 stdout（过滤统计、每个 K 的 perplexity / reconstruction_err、BERTopic 各路线 outlier rate）。
4. `comparison.md` — 方法 × K 主题词概览、横切表索引、HDBSCAN sensitivity、LDA↔BERTopic Jaccard 启发式配对。
5. 主题表：`lda_kK_topics.csv` / `nmf_kK_topics.csv` / `bert_*/topics.csv`；样本：`*_samples.csv`。
6. 横切：`*_by_post_id.csv` / `*_by_robot_status.csv` / `*_by_post_category.csv`（**post-level averaging**，避免爆款帖压倒）。
7. HDBSCAN：先看 `topic_raw`（含 -1 噪声），`topic_assigned` 仅辅助阅读。
8. 敏感度：`loo_post_sensitivity_lda_k7_robot_status.csv`（leave-one-post-out）。

### 6.1 如何读 `output/explore/<timestamp>_<name>/`

按下列顺序：

1. `summary.md`：命中规模 + post_category 分布。
2. `samples.md`：按关键词分组，最多 `sample_per_keyword` 条命中片段。
3. `hits.csv`：全量命中（`comment_id / 帖子id / post_category / comment / hit_keywords / match_source / matched_snippet`）。
4. `config.json`：输入文件、`match_mode`、关键词列表与来源。

**强调**：探索目录不是主题建模产物，**绝不能**把命中作为分类标签；不要把它接到 LDA / BERTopic 的输入做半监督，否则触发 **M1 / M2** 错误。

---

## 7. Troubleshooting

| 现象 | 处理 |
|------|------|
| `SentenceTransformer` 卡住数分钟且无新日志 | 检查网络；确认 HF 缓存是否存在；显式 `--device cpu`；保证代码已优先 `local_files_only=True`（**E6**） |
| `TypeError: PosixPath is not JSON serializable` | 使用最新 `topic_modeling.py`（**E7** 已修复，含 `_json_safe_cfg_value`） |
| `import hdbscan` / `from numba ...` 在 arm64 报错（**C9**） | 1) `pip install hdbscan --no-cache-dir --no-binary :all: --no-build-isolation`（FAQ "Numpy gives me an error"）；2) 仍不行用 VS Code Dev Container（FAQ "Apple Silicon"） |
| 模型下载卡住（**E2 / E5 / C8**） | `env \| grep -i proxy`；用 `huggingface-cli download BAAI/bge-base-zh-v1.5` 单独下载并写日志到 `/tmp/hf_dl.log` |
| BERTopic 主题数为 0 / 1 | **C7**：调小 `min_cluster_size` / `n_neighbors`；改用 KMeans |
| BERTopic 主题数 > 30 | **C7**：调大 `min_cluster_size`；用 `nr_topics="auto"` 让模型自动合并 |
| NMF `RuntimeWarning` matmul | 数值噪声，输出仍可用；记录但不必中断 |

---

## 8. 当前结论（**每次跑完更新这一段**）

- **当前 run_id**：`2026-05-09_topic_full_corpus_bge_base`（见 `output/experiments/2026-05-09_topic_full_corpus_bge_base/`）。
- shared corpus：`n_raw=31,245 → n_shared=18,832`，覆盖率 0.6027。
- 嵌入模型：`BAAI/bge-base-zh-v1.5`（CPU）。
- HDBSCAN 灵敏度（`mcs / ~主题数 / outlier_rate`）：`100 / 20 / 31.3%`、`200 / 2 / 3.6%`、`400 / 2 / 4.5%` —— 主题数对 `mcs` 极敏感，主解读以 `comparison.md` 多 K 对照 + KMeans K=5/7/10 + 手工核读为准。

---

## 9. 未来扩展（按需，非本阶段）

- 选定 K 后再用 `approximate_distribution` 计算文档-主题分布。
- BERTopic `nr_topics="auto"` 合并相似主题。
- 引入 topic coherence（gensim CV/UMass）作为 K 选择补充指标。
- Lexicon **重新接回**只能走「先 IRR + codebook → 单独 `topic_modeling_seeded.py` 模块」这条路；不在本流程内扩展。
