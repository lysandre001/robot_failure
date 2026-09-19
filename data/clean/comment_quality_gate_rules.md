# 评论集纳入规则（shared analyzable corpus）

> **版本**：2026-09-09 v1  
> **机器可读**：[`config/topic_modeling/comment_quality_gate.json`](../../config/topic_modeling/comment_quality_gate.json)  
> **实现**：`phase1/comment_quality_gate.py`（由 `build_shared_analyzable_corpus` 调用）  
> **范围**：只决定评论是否进入分析库。主题词 / LDA 停用词是另一层，见文末。

本文件是评论级质量门槛的说明。BGE 与人工阅读仍用 **原文**；本规则只用于 **是否保留该行**。

---

## 两层不要混

| 层 | 产物 | 做什么 |
|----|------|--------|
| Phase 1 | `clean_comments_unified.csv` | 空内容、`@` 提及、纯 emoji、重复片段、英文套话整句 |
| Shared | `shared_analyzable_corpus.csv` | 在 clean 上再判「有没有可分析命题」 |
| 主题词 | LDA / NMF 词表 | 才使用 sklearn 英文功能词表 |

**不要**用 NLTK / sklearn 的 the / have / still 判断英文评论是否有信息。反例：`We might have a few years on them still. 😂` 在旧规则下有效词数 = 1，被误标 `effective_tokens_lt_min`。

---

## Phase 1（clean）

配置：[`config/topic_modeling/comment_content_filter.json`](../../config/topic_modeling/comment_content_filter.json)

| 规则 | 行为 |
|------|------|
| 空内容 | 去掉 |
| `pure_emoji` | 去空白后仅 emoji |
| `contains_mention` | 正文含 `@` / `＠` 即排除（保留此规则，跨平台一致） |
| `repeated_fragment` | 短片段重复 ≥3（哈哈哈哈、666、hahaha） |
| `english_boilerplate` | 整句精确匹配 lol / first / ok / nice 等 |
| 纯标点 / 纯 URL / ≥5 位纯数字 | shared 层 `_is_pure_noise_row` 再挡一次 |

描述性分析、demo Top10、人工读帖：用 **clean**，不必用 shared。

---

## Shared 门控（本文件主体）

规范化（仅用于计数，不改写入的 `content`）：

1. Unicode NFC
2. 去 URL、`@user`、数字 ID、emoji、小红书 `[赞R]` 类括号（`clean_text`）
3. 英文小写

然后 **中英分路，混合评论任一路径通过即可**。

### 中文

通过条件（或）：

- jieba 分词后，去掉中文停用词 + `platform_noise` + `corpus_noise`，剩余 **≥ 2** 词；或
- 正文含汉字，且规范化后 **字符数 ≥ 8**

不计 sklearn 英文停用词。单字除「人 / 机 / 狗」外丢掉（与既有 `tokenize_text` 一致）。

### 英文

通过条件（或）：

- `[a-z]{2,}` 词数 **≥ 4**；或
- 去掉平台套话词（与 `english_boilerplate` 词表对齐：lol、first、ok…）后 **≥ 2** 词

**不扣除** have / might / still / them 等功能词。

### 仍排除

- 规范化长度 **< 4**（`empty_or_too_short`）
- 全库 `casefold` 正文去重（`duplicate_text`，保留首次）

---

## 与旧标准的差

| 旧 | 新 |
|----|----|
| 去停用词后 ≥2 词；TikTok 曾把 sklearn 318 词并入门槛 | 英文按字母词 / 套话词计数；中文保留 jieba≥2，并增加「汉字且 ≥8 字」兜底 |
| 短英文整句易被杀 | 完整短句可进入 shared |

05-27 XHS discovery 实验仍冻结在当时的 shared 行序。若 XHS shared 行数变化，新主题 run 须新 `run_id` 并重 encode，勿覆盖 current。

---

## 主题词层（本次不做）

LDA / NMF 仍可用 `general_stopwords_en.txt`（sklearn ENGLISH_STOP_WORDS）+ `min_df`。那是词表规范化，不是评论集筛选。
