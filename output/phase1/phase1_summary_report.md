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

### all
- 套话模板命中率(您是…它是…风格): 0.000%
- 角色词典均值 Top3: failure_comedy=0.345, baby_cute=0.053, athlete=0.039
- 拟人线索 Top3: mind_volition=0.027, pronoun_ta_m=0.019, pronoun_ta_obj=0.013

### humane,nohuman
- 套话模板命中率(您是…它是…风格): 0.000%
- 角色词典均值 Top3: athlete=0.061, failure_comedy=0.050, hero_progress=0.031
- 拟人线索 Top3: pronoun_ta_m=0.037, mind_volition=0.028, pronoun_ta_obj=0.024

### lovely,nohuman
- 套话模板命中率(您是…它是…风格): 0.000%
- 角色词典均值 Top3: baby_cute=0.195, failure_comedy=0.193, athlete=0.025
- 拟人线索 Top3: kin_terms=0.047, pronoun_ta_m=0.032, pronoun_ta_obj=0.031

### strong,human
- 套话模板命中率(您是…它是…风格): 0.098%
- 角色词典均值 Top3: failure_comedy=0.295, athlete=0.054, threat_compete=0.026
- 拟人线索 Top3: pronoun_ta_m=0.043, pronoun_ta_obj=0.041, mind_volition=0.033

### strong,nohuman
- 套话模板命中率(您是…它是…风格): 0.000%
- 角色词典均值 Top3: failure_comedy=0.134, athlete=0.058, nation_tech=0.023
- 拟人线索 Top3: pronoun_ta_m=0.043, mind_volition=0.039, pronoun_ta_obj=0.028

### unknown
- 套话模板命中率(您是…它是…风格): 0.000%
- 角色词典均值 Top3: product_tech=0.091, hero_progress=0.045, failure_comedy=0.045
- 拟人线索 Top3: body_pain=0.045, pronoun_ta_obj=0.000, pronoun_ta_m=0.000

### weak,human
- 套话模板命中率(您是…它是…风格): 0.000%
- 角色词典均值 Top3: failure_comedy=0.311, baby_cute=0.031, athlete=0.011
- 拟人线索 Top3: mind_volition=0.024, kin_terms=0.024, pronoun_ta_m=0.014

### weak,nohuman
- 套话模板命中率(您是…它是…风格): 0.000%
- 角色词典均值 Top3: failure_comedy=0.362, baby_cute=0.035, athlete=0.018
- 拟人线索 Top3: body_pain=0.028, mind_volition=0.021, pronoun_ta_m=0.011

## 高回复一级评论（玩梗/协商潜在热点）
见 `top_high_reply_l1.csv` 前 10 行摘取：
- [humane,nohuman] replies=1334 likes=4733 — 比跑步干嘛非要人形，轮子不是更快[笑哭R]
- [weak,nohuman] replies=1178 likes=0 — 咋的？低血糖了？
- [all] replies=1130 likes=0 — 其他的我都懂，这个120是打算救谁的？
- [weak,nohuman] replies=1087 likes=0 — 笑死了，摄影届又多了一幅图
- [humane,nohuman] replies=898 likes=4118 — 喷的那个是什么呀
- [strong,nohuman] replies=843 likes=0 — 坐着跑伤膝盖，不建议呢
- [weak,human] replies=484 likes=0 — 不管你考得怎么样，爸爸妈妈都爱你！
- [lovely,nohuman] replies=436 likes=0 — 果然 什么东西小小的都很可爱
- [all] replies=357 likes=6640 — 怎么不拍豆脚，她也参赛了。
- [weak,nohuman] replies=347 likes=0 — 世界名画[大笑R]