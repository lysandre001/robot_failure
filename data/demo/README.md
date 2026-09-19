# Demo：评论抽样（Top10 / Top20）

人工浏览 / 示範 / Drive 协作用。

## Top20 L1 + 1 L2（raw / clean → Drive）

每帖 **20 条** 实际 L2 子评论数最多的一级评论，每条 L1 附 **1 条**最高赞 L2。长表格式（`comment_level` 1/2），参考 Drive `xiaoyu_filtered_sample20_per_post_merged_聚焦一级分类.xlsx`。

```bash
python -m tools.export_demo_top20_l1_l2_raw
python -m tools.export_demo_top20_l1_l2_raw --platform tiktok --batch 2604-marathon
```

| 源 | 输入 | 语言/英译 |
|----|------|-----------|
| TikTok 2604-marathon | raw 宽表 | ✅ `language` / `is_mixed` / `content_en` |
| TikTok 2608-olympic | clean | ❌ |
| 抖音 2608-olympic | clean | ❌ |
| YouTube 2604-marathon | clean | ✅ |
| YouTube 2608-olympic | clean | ✅ |

**Drive 目录**：`robot_analysis 🤖/data/demo_comments/`

命名：`{event}__{batch}__{platform}__top20L1_1L2_by_l2count[_with_lang_en].xlsx`

---

## Top10 高 L2 回复一级评论（legacy）

从各平台 **clean** 主表中，按帖抽取 **实际二级子评论数最多** 的 10 条 **一级评论**。

## 排序规则

1. 在 `clean_comments_unified.csv` 内，用 `parent_comment_id` 统计每条 L1 的实际 L2 子节点数（`n_l2_children`）。
2. 每帖内按 `n_l2_children` 降序，再按 `like_count` 降序。
3. 取 Top 10；若该帖 L1 不足 10 条则全取。

**不用** raw 宽表里的 `reply_count`（与 clean 内实际 L2 数约 9% 不一致）。

## 生成

```bash
python -m tools.export_demo_top_l2_by_post
python -m tools.export_demo_top_l2_by_post --top-n 10 --out-dir data/demo
python -m tools.export_demo_top_l2_by_post --input data/clean/tiktok/2604-marathon/clean_comments_unified.csv --platform tiktok --batch 2604-marathon
```

## 产物

| 文件 | 说明 |
|------|------|
| `top10_l2_by_post_all.csv` | 四源合并总表 |
| `summary_by_source.csv` | 每源帖数、L1 数、导出行数 |
| `{platform}_{batch}/top10_l2_by_post.csv` | 单源子表 |

## 字段

| 列 | 说明 |
|----|------|
| `platform`, `source_batch` | 平台与批次 |
| `帖子id`, `帖子标题` | 帖子 |
| `post_category` | XHS 有编码；其余 `unknown` |
| `rank_in_post` | 该帖内排名 1–10 |
| `comment_id` | L1 评论 id |
| `n_l2_children` | clean 内实际 L2 数 |
| `content` | L1 正文 |
| `sample_l2_contents` | 该 L1 下最多 3 条 L2 正文（`\|` 分隔） |

## 当前规模（2026-09-09）

见 `summary_by_source.csv`。合计约 1,867 行（33 + 143 + 15 + 51 帖）。
