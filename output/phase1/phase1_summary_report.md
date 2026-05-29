# 第一阶段分析摘要报告

## 产物

- `clean_l1_comments.csv` / `clean_l2_comments.csv` / `clean_comments_unified.csv`
- `data_quality.md`
- `interaction_by_category.csv`, `top_high_reply_l1.csv`
- `role_scores_by_category_level.csv`, `personhood_by_category_level.csv`
- `boundary_by_category_level.csv`, `boundary_contrast_sample.csv`
- `meme_template_counts.csv`, `meme_heavy_highlike_sample.csv`, `char4grams_top_by_category_L1.csv`
- `cooccurrence_robot_pronouns.json`
- `topic_clusters_terms.csv`, `topic_cluster_by_category.csv`
- `figures/*.png`

## 进入第二阶段 codebook 的候选线索（机器生成，需人工核验）

（未启用 `--legacy-lexicon-features`，跳过词典/模板统计。）

## 高回复一级评论（玩梗/协商潜在热点）
见 `top_high_reply_l1.csv` 前 10 行摘取：
- [常态] replies=2405 likes=0 — 本人将严肃的在此评论，并在机器人统治地球之后当做投名状
- [强势] replies=1334 likes=4733 — 比跑步干嘛非要人形，轮子不是更快[笑哭R]
- [混合] replies=1178 likes=0 — 咋的？低血糖了？
- [混合] replies=1130 likes=0 — 其他的我都懂，这个120是打算救谁的？
- [混合] replies=1087 likes=0 — 笑死了，摄影届又多了一幅图
- [强势] replies=898 likes=4118 — 喷的那个是什么呀
- [强势] replies=843 likes=0 — 坐着跑伤膝盖，不建议呢
- [失败] replies=535 likes=0 — 大家不要笑，再过几年他们就可以跑得很溜，事物的发展都有个过程。
- [弱势] replies=484 likes=0 — 不管你考得怎么样，爸爸妈妈都爱你！
- [弱势] replies=436 likes=0 — 果然 什么东西小小的都很可爱