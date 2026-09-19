# 帖子内容分类（按源）

文件名：`{platform}_{batch}.csv`（例 `youtube_2604-marathon.csv`）。

列与允许值见 [Schema §3](../../data/canonical_comment_schema.md)（码本索引 [docs/registry.md](../../docs/registry.md) → `post_category`）。

**人的形象**：schema 三档 **服务照护 / 被超越者 / 观众**（见 `data/canonical_comment_schema.md` §3）。再生附录表：

```bash
python -m tools.post_category_appendix
```

小红书沿用上级目录 [post_category_by_post.csv](../post_category_by_post.csv)。

填完后刷新 clean（不重洗 raw）：

```bash
python -m tools.refresh_clean_post_labels --platform youtube --batch 2604-marathon
```
