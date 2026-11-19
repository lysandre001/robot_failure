# 三视角典型主题：填写模板（论文 / 日记用）

**语料**：`analysis_corpus.csv` N=28,096；**主解**：`bert_hdbscan_mcs80`（离群 `-1` 不参与占比）。  
**视角**：码本门控 `has_robot` / `has_imagination` / `has_self`（inclusive；排他结果见 `overlap_exclusive_margins.csv`）。

每条「典型主题」= **共享 topic 空间上的过度表征叙事**，不是单独再聚类。自动化已筛候选；**科学客观的最后一步** = 你填 `human_verdict` + 引文。

---

## 使用顺序

1. 从下方 **预填候选** 起步（按「该视角 share ÷ 另两类最大 share」排序，且 `n_total_non_outlier ≥ 150`）。
2. 核对数字：`topic_prop_shares_by_perspective.csv`、`topic_prop_bootstrap_ci.csv`、`topic_prop_pairwise_diffs.csv`（BH-FDR）。
3. 用词差异：`fightin_words_by_topic.csv` + `fightin_words_examples.csv`。
4. 合并多 topic → 叙事：`REPORT.md` mega 分组 + `hierarchy_merge_candidates.csv`。
5. 定性：`manual_spotcheck_sample.csv` 增行；**正反例**各 1–2 条。
6. 跨事件：`topic_prop_by_event.csv` 同向否？

**正文限定语（建议照抄改数字）**：  
> Distributions are over non-outlier topic assignments on a single BERTopic solution (MCS=80). Perspective labels gate the corpus, not the clustering. Overlap metrics describe distributional intersection, not duplicate comments.

---

## 字段说明（每条叙事复制一块）

| 字段 | 填什么 |
|------|--------|
| `narrative_id` | 自定短名（英文或中文） |
| `topic_ids` | 合并的 BERTopic id |
| `mega_group` | 对照 `REPORT.md` 粗分组 |
| `elevated_perspective` | Robot / Imagination / Self |
| `stats_one_liner` | share、lift、FDR 显著对、bootstrap 95% CI（百分点） |
| `keywords` | `topics.csv` Representation |
| `how_they_talk` | Fightin’ Words 1–3 个词 + 方向 |
| `exemplar_comment_ids` | 2–3 个 `comment_id` + 一句摘 |
| `counterexample` | 另一视角在同 topic 的反驳例 |
| `event_robust` | 两 batch 是否同向（Y/N + 注） |
| `human_verdict` | accept / revise / reject |
| `writer_notes` | 理论挂钩、是否写进正文 |

---

## Robot — 5 个预填候选（赛场反应 / 操控 / 赞叹）

### R1 — 遥控与操控怀疑

| 字段 | 内容 |
|------|------|
| `narrative_id` | Remote_control_skepticism |
| `topic_ids` | **8** |
| `mega_group` | Control_Program_Surveillance |
| `elevated_perspective` | Robot |
| `stats_one_liner` | n=553；Robot share **7.0%**（Imagination **0.31%**, Self **0.34%**）；Robot share / max(other) ≈ **21×**；见 `topic_prop_pairwise_diffs` Robot–Imagination FDR≪0.05 |
| `keywords` | remote controlled, remote control, control robots |
| `how_they_talk` | （待填）`fightin_words` topic 8，pair Robot–Imagination |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | （待填）Imagination 在同 topic 的罕见反例 |
| `event_robust` | （待填）`topic_prop_by_event` |
| `human_verdict` | |
| `writer_notes` | 偏「当下赛事实况」技术质疑，少科幻外延 |

### R2 — 口语反应 / 秀场_commentary

| 字段 | 内容 |
|------|------|
| `narrative_id` | Bro_spectator_reaction |
| `topic_ids` | **19** |
| `mega_group` | Robot_General_Other |
| `elevated_perspective` | Robot |
| `stats_one_liner` | n=226；Robot **2.93%** vs Imagination **0.04%** vs Self **0.22%**；lift Robot/Imagination 极大（shortlist 行） |
| `keywords` | bro, dude, ass, guy |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | 高负向情感区（见 `REPORT` topic 19 neg）；注意俚语是否跨事件泛化 |

### R3 — 惊艳 / 赞叹

| 字段 | 内容 |
|------|------|
| `narrative_id` | Awe_impressive |
| `topic_ids` | **20** |
| `mega_group` | Awe_Reaction |
| `elevated_perspective` | Robot |
| `stats_one_liner` | n=204；Robot **2.54%** vs Imagination **0.08%**；topic 内 pos 比例高（REPORT ~75% pos） |
| `keywords` | impressive, amazing, remarkable |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | 可与 Self 的焦虑叙事对照，别和「恐惧」合并 |

### R4 — 人机速度 / 赛事类比（大体积）

| 字段 | 内容 |
|------|------|
| `narrative_id` | Performance_race_metaphor |
| `topic_ids` | **1, 4, 5, 12**（建议合并写；单 topic 见下） |
| `mega_group` | Performance_Race_Ability |
| `elevated_perspective` | Robot |
| `stats_one_liner` | **1** n=1003，Robot share **10.9%** vs Imagination **0.93%**（lift≈11.7）；**5** Robot **7.5%** vs Imag **0.7%**；bootstrap CI 见 `topic_prop_bootstrap_ci` |
| `keywords` | usain bolt / running like / cars faster / robots faster |
| `how_they_talk` | （待填）topics 1 & 5 优先 |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | Self 在 topic 1 占 **32%** 条内人数 — 分布仍有 Self，但**边际 share**仍偏低 |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | 核心 Robot 典型；写作时强调「赛事帧」非军武帧 |

### R5 — 开关 / 拔掉插头（操控、去人化幽默）

| 字段 | 内容 |
|------|------|
| `narrative_id` | Kill_switch_humor |
| `topic_ids` | **18** |
| `mega_group` | Control_Program_Surveillance |
| `elevated_perspective` | Robot |
| `stats_one_liner` | n=232；Robot **2.62%** vs Imag **0.51%** vs Self **0.36%** |
| `keywords` | switch, button, pull plug, shut |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | |

**Robot 备选**（体积或显著性上也值得看）：topic **8** 已列；**32** Titan 跑姿、**42** 跑步风格 — shares 较小，作二级附录。

---

## Imagination — 5 个预填候选（战争 / 科幻 / 军队）

### I1 — 枪武与武装化

| 字段 | 内容 |
|------|------|
| `narrative_id` | Weaponization_guns |
| `topic_ids` | **2** |
| `mega_group` | War_Military_Weapon |
| `elevated_perspective` | Imagination |
| `stats_one_liner` | n=953；Imagination share **11.4%** vs Robot **0.83%**（diff ≈ **−10.6 pp**，FDR≪0.05） |
| `keywords` | guns, rifles, weapons, machine guns |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | Robot 条内少数军事评论 |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | 最干净的 Imagination 过度表征之一 |

### I2 — Terminator / 科幻电影谱系

| 字段 | 内容 |
|------|------|
| `narrative_id` | Terminator_cinematic |
| `topic_ids` | **3, 31, 29** |
| `mega_group` | War_Military_Weapon + Future_Imagination |
| `elevated_perspective` | Imagination |
| `stats_one_liner` | **3** n=895，Imag **10.4%** vs Robot **1.39%**；**31** John Connor 线 Imag 主导 |
| `keywords` | terminator, skynet, john connor, t800 |
| `how_they_talk` | （待填）topic 3 |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | 可与 **9 Skynet** 合并叙述或分两段 |

### I3 — Skynet / AI 末日基础设施

| 字段 | 内容 |
|------|------|
| `narrative_id` | Skynet_dystopia |
| `topic_ids` | **9** |
| `mega_group` | War_Military_Weapon |
| `elevated_perspective` | Imagination |
| `stats_one_liner` | n=545；Imag **6.82%** vs Robot **0.32%**（lift≈22×） |
| `keywords` | skynet, sky, net, eye, data centers |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |

### I4 — 机器人军队 / 军事部署

| 字段 | 内容 |
|------|------|
| `narrative_id` | Robot_army |
| `topic_ids` | **15**（可含 **0** 之 army 词、见 I5） |
| `mega_group` | War_Military_Weapon |
| `elevated_perspective` | Imagination |
| `stats_one_liner` | n=285；Imag **3.50%** vs Robot **0.24%** |
| `keywords` | robot army, military robots, war robots |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |

### I5 — 科幻作品与未来科技想象（中等体积）

| 字段 | 内容 |
|------|------|
| `narrative_id` | Sci_fi_pop_culture |
| `topic_ids` | **22, 26, 24** |
| `mega_group` | Future_Imagination |
| `elevated_perspective` | Imagination |
| `stats_one_liner` | **22** iRobot Imag **2.19%** vs Robot **0.29%**；**26** robot movie Imag **1.76%** |
| `keywords` | irobot, robot movie, I Robot, watch robot |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |

**共享战场（勿写成单视角独占）**：topic **0** 中国/军队/地缘政治 — 三类 share 接近（~7–8.6%），适合写「公共议题」，再分视角 Fightin’ Words。

---

## Self — 5 个预填候选（体积、特异性并存）

> Self 语料 n=5,891，**强特异性主题少于 Robot/Imagination**；务必报告 **bootstrap CI** 与是否跨事件，避免只靠 Fisher。

### S1 — 人类终结 / 存在焦虑

| 字段 | 内容 |
|------|------|
| `narrative_id` | Humanity_end_anxiety |
| `topic_ids` | **6** |
| `mega_group` | War_Military_Weapon（终结叙事） |
| `elevated_perspective` | Self |
| `stats_one_liner` | n=637；Self **12.4%** vs Imag **3.90%** vs Robot **0.74%**；shortlist Robot–Self diff ≈ **−11.7 pp**；topic neg ~77% |
| `keywords` | end humanity, end world, human race |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | Imagination 在同 topic 仍占 305 条 — **条内混合、边际 Self 更高** |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | **最稳的 Self 典型**；写作用「边际 over-representation」语言 |

### S2 — 笑与否： us vs them 时间线

| 字段 | 内容 |
|------|------|
| `narrative_id` | Laughter_turnabout |
| `topic_ids` | **14** |
| `mega_group` | Self_Personal_Stance |
| `elevated_perspective` | Self（弱于 S1，需人工裁定） |
| `stats_one_liner` | n=331；Self share **3.16%** ≈ Imag **3.26%** > Robot **0.70%** |
| `keywords` | laugh, laughing, laugh at you, future |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | 理论链：自我—他者时间 inversion |

### S3 — 私人身体 / 身份（小体积高 lift 时再用）

| 字段 | 内容 |
|------|------|
| `narrative_id` | Body_identity_probe |
| `topic_ids` | **37, 33, 40, 41** |
| `mega_group` | Gender_Body_Identity |
| `elevated_perspective` | Self |
| `stats_one_liner` | **33** n=142 Self share **3.55%** vs Robot **0.20%**（但 n 小）；见 shortlist FDR |
| `keywords` | （查 `topics.csv`） |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | 建议附录或案例节，不作唯一 Self 支柱 |

### S4 — 速度比较中的「人」的位置

| 字段 | 内容 |
|------|------|
| `narrative_id` | Human_in_speed_comparison |
| `topic_ids` | **4** |
| `mega_group` | Performance_Race_Ability |
| `elevated_perspective` | Self（与 Robot 共享 topic） |
| `stats_one_liner` | n=686；Self **8.42%** > Robot **6.91%** > Imag **0.91%** — **共享帧、Self 边际略高** |
| `keywords` | faster human, cars faster, machine faster |
| `how_they_talk` | （待填）Robot–Self |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | Robot 仍大量 — 写「对照视角」不写「独占」 |
| `event_robust` | |
| `human_verdict` | |

### S5 — 技术进步的双刃剑（弱特异性）

| 字段 | 内容 |
|------|------|
| `narrative_id` | Tech_ambivalence |
| `topic_ids` | **24, 13** |
| `mega_group` | Jobs_Labor / Future |
| `elevated_perspective` | Self / 混合 |
| `stats_one_liner` | shares 接近 — 优先 Fightin’ Words + 情感 crosstab |
| `keywords` | technology, ai, ai robots |
| `how_they_talk` | （待填） |
| `exemplar_comment_ids` | （待填） |
| `counterexample` | |
| `event_robust` | |
| `human_verdict` | |
| `writer_notes` | 若 `human_verdict=reject`，改练 S1+S4 即可 |

---

## 论证检查清单（交稿前打勾）

- [ ] 每个正文典型主题至少 1 个 **FDR 显著**比例差或 **CI 不跨 0** 的 bootstrap
- [ ] 引文绑定 `comment_id`，并与 `subject_labels` 一致
- [ ] 说明 **41% 离群** 与 Robot 更高离群率
- [ ] 报 **inclusive**；附录可选 **exclusive** 边际
- [ ] 稳定性一句：MCS/ UMAP 敏感性见 `stability_summary.md`
- [ ] STM：`STM_NOTES.md` 作方向性，不映射 topic id
- [ ] 1−TV 称作分布相交，非重复评论

---

## 相关文件索引

| 用途 | 路径 |
|------|------|
| 自动 shortlist | `narratives_worth_followup.md` |
| 占比 | `topic_prop_shares_by_perspective.csv` |
| 显著性 | `topic_prop_pairwise_diffs.csv` |
| CI | `topic_prop_bootstrap_ci.csv` |
| 重叠 | `overlap_js_tv.csv` |
| 用词 | `fightin_words_by_topic.csv` |
| 人工表 | `manual_spotcheck_sample.csv` |
| 汇总 REPORT | `../REPORT.md` |

*生成说明：候选序基于 `share_elevated / max(share_other)` 与 shortlist；**未**替代人工 `human_verdict`。*