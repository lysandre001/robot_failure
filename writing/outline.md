# 2. 背景、文献综述与标注策略：大纲版

> 目的：把现有文献笔记整理成可直接扩写的论文章节结构。  
> 当前定位：为 RoboStance 论文的 Introduction、Related Work、Dataset Annotation Schema 与 Appendix Guideline 提供理论骨架。

---

## 一、章节核心论点

本研究关注的是公众如何在真实社交媒体场景中理解、接纳、怀疑或拒斥人形机器人。机器人马拉松这类公共事件不同于实验室 HRI 研究中的受控互动，它把机器人置于 “robot in the wild” 的观看场景中，使公众的立场、情绪、幽默、拟人化投射、技术评价与社会想象同时浮现。

现有研究已经分别讨论了机器人意识形态、机器人社会感知量表、社交媒体中的机器人评论，以及 NLP 中的 stance detection 数据集。但这些工作之间仍存在一个空白：缺少一个面向人形机器人公共话语的、同时标注 stance 与 stance rationale / discourse domain 的中文社交媒体数据集。

因此，本章节需要完成三件事：

1. 说明为什么公众对人形机器人的态度值得研究。
2. 说明为什么现有 HRI 量表、机器人社会感知研究和 stance detection 数据集不足以回答本文问题。
3. 说明本文的标注体系如何从 Firth、Bartneck、Spatola、Cappuccio 等文献中抽取理论维度，并转化为可操作的 codebook。

---

## 二、背景：机器人马拉松作为公共话语事件

### 2.1 现象入口

可写作要点：

- 北京机器人马拉松让人形机器人以公开竞技者、媒体奇观和技术展示物的身份进入公众视野。
- 观众不是在实验室中与机器人一对一互动，而是在短视频/图文平台中观看机器人成功、失败、摔倒、坚持、被扶起等片段。
- 这类评论不仅是对赛事表现的即时反应，也是公众对人形机器人未来角色的想象与评判。

建议论证句：

> Public discourse around humanoid robots does not merely record whether people like or dislike a particular machine; it reveals how people imagine the social, emotional, and moral place of robots in everyday life.

### 2.2 研究问题

与 [config/codebook/codebook.md](../config/codebook/codebook.md) 对齐的研究问题：

1. **情感 / 立场（RQ1）**：`情感` 四类 + `stance` 支持/反对/中立。
2. **观念理由域（RQ2）**：`d1`–`d4` 极性；可选 `figure_code` 附录。
3. **情境横切（RQ3）**：帖子 `robot_status` × `human_role`（非评论码本字段）× 上述码本 → `tools/codebook_analysis` → `output/analysis/`。

历史表述（仍可用作引言）：

1. **立场层面**：公众对人形机器人总体上是支持、反对还是中立？
2. **理由层面**：公众为什么支持或反对？这些理由来自技术评价、社会进步叙事、拟人化情感、安全治理，还是人类身份与劳动焦虑？
3. **情境层面**：机器人处于成功、失败或中性表现时，公众立场和理由分布是否发生变化？

可形成正式研究问题：

- RQ1: What stance do Chinese social media users express toward humanoid robots in public event discourse?
- RQ2: What discourse domains or rationales underlie these stances?
- RQ3: How does the robot's visible state, such as success or failure, condition stance expression and discourse domain distribution?

---

## 三、文献综述 Part I：机器人意识形态与社会想象

### 3.1 Robotic ideology 的作用

现有笔记中的核心文献：

- Firth (2020), Robotic Ideology

可整理为两个理论轴：

| 理论轴                                                      | 主要区分                                 | 对本文的启发                          |
| -------------------------------------------------------- | ------------------------------------ | ------------------------------- |
| Humanist vs. Assemblage                                  | 人类是否具有需要被机器人威胁或保护的本质；人类是否本来就处在技术组装体中 | 帮助解释 “人何以为人”“机器人是否越界”“人机边界” 等评论 |
| Techno-optimism / Tactical-process / Techno-dystopianism | 技术被想象为解放力量、条件性工具，或压迫/异化/灾难来源         | 帮助解释支持与反对背后的宏观意识形态              |

### 3.2 可扩写的论述结构

第一段：介绍公众对机器人的态度不只是个人偏好，而嵌入更大的技术意识形态中。技术乐观主义把机器人视为解决劳动力短缺、老龄化、危险作业等问题的工具；技术悲观主义则强调替代、控制、异化和人类独特性的丧失。

第二段：引入 Firth 的二维框架。Humanist 视角倾向于把机器人看作对人类创造性、劳动和主体性的威胁；Assemblage 视角则拒绝人类例外论，认为人类与技术始终共同构成社会实践。

第三段：将该框架连接到本文的标注体系。公众评论中关于 “中国科技进步”“人还有什么用”“机器人太像人了”“以后会不会控制人类” 等表达，实际上是这些意识形态在日常语言中的碎片化呈现。

### 3.3 对 codebook 的映射

- Firth 的 techno-optimism / techno-dystopianism → `D1 Society & Nation`
- Firth 的 humanist concern → `D3 Human Identity & Labor`
- Firth 的 assemblage / human-machine boundary → `D3 Human Identity & Labor`
- Firth 的 tactical/process 立场 → `D5 Technology & Product`

---

## 四、文献综述 Part II：机器人社会感知与 HRI 量表

### 4.1 Godspeed 与经典 HRI 量表

现有笔记中的核心文献：

- Bartneck et al. (2009), Godspeed Questionnaire

Godspeed 提供了 HRI 中最经典的机器人感知维度：

- Anthropomorphism
- Animacy
- Likeability
- Perceived Intelligence
- Perceived Safety

可写作功能：

- 用来说明 HRI 研究已经发展出成熟的机器人感知维度。
- 但这些维度通常用于受控实验或问卷场景，不一定能捕捉社交媒体评论中的幽默、反讽、社会叙事和长期意识形态。

### 4.2 RoSAS 与社会感知框架

现有笔记中的核心信息：

- RoSAS 将机器人社会感知简化为温暖、能力、干扰等维度。
- 它借用了社会心理学中对人/群体的感知框架。
- 局限在于早期验证多基于机器人图片，而不是实体机器人或真实公共事件。

可写作角度：

> These scales provide useful perceptual dimensions, but they are not designed to annotate naturally occurring public discourse, where stance is often implicit, humorous, and entangled with broader social narratives.

### 4.3 Spatola (2021) 的四维量表

现有笔记中的维度：

| 维度 | 内容 | 对本文的启发 |
| --- | --- | --- |
| Sociability | warm, friendly, trustworthy, likeable | 支持类评论中的亲近、喜爱、共情 |
| Agency | rational, self-reliant, intelligent, intentional | 评论中对机器人自主性和智能的判断 |
| Animacy | human-like, real, alive, natural | 拟人化、生命感、恐怖谷反应 |
| Disturbance | scary, creepy, weird, uncanny | 排斥、诡异、不适和风险想象 |

### 4.4 对 codebook 的映射

- Godspeed 的 Anthropomorphism / Animacy / Likeability → `D2 Affect & Anthropomorphism`
- Godspeed 的 Perceived Intelligence → `D5 Technology & Product`
- Godspeed 的 Perceived Safety → `D4 Safety & Governance`
- Spatola 的 Sociability / Animacy → `D2 Affect & Anthropomorphism`
- Spatola 的 Disturbance → 可落入 `D2`，若转向具体风险或监管诉求则落入 `D4`
- Spatola 的 Agency → 视语境落入 `D3` 或 `D5`

---

## 五、文献综述 Part III：机器人接受、信任与容忍

### 5.1 从 trust / acceptance 到 tolerance

现有笔记中的核心文献：

- Cappuccio (2024), Tolerance toward autonomous agents / autonomy estrangement

可整理的对比：

| 概念 | 评估对象 | 时间尺度 | 理论重点 |
| --- | --- | --- | --- |
| Acceptance | 某个系统是否有用、易用、值得采用 | 相对短期，常与具体使用任务相关 | TAM、HRI 用户体验 |
| Trust | 用户是否相信机器人能可靠、安全地完成任务 | 中短期，常与交互表现相关 | 能力、可靠性、风险 |
| Tolerance | 用户是否能容忍自主系统成为社会生活的一部分 | 长期，常在使用前已形成 | 规范性信念、世界观、自主性疏离 |

### 5.2 Autonomy estrangement

关键概念：

- 人类因为相信机器人可能颠覆、替代或控制自己的生活，而产生诡异的孤立感、流离失所感和挫败感。
- 这解释了为什么一些评论并非针对某个机器人的性能，而是在表达对 “自主技术作为一类存在” 的不适。

### 5.3 Cappuccio 框架对本文的贡献

Cappuccio 区分的两类 concern 可以转化为标注维度：

- Concerns over disruptive societal changes → `D1 Society & Nation`, `D3 Human Identity & Labor`
- Concerns over agents' dominance → `D3 Human Identity & Labor`, `D4 Safety & Governance`

这一部分可以支撑本文为什么不只标注 Support / Oppose / Neutral，而要进一步标注 discourse domain：因为立场背后的 “为什么” 往往决定了公众对机器人长期共处的容忍度。

---

## 六、文献综述 Part IV：社交媒体中的机器人公众感知

### 6.1 Robot in the wild 与自然语料的价值

可写作要点：

- 社交媒体评论能够捕捉未经研究者引导的 spontaneous perception。
- 它保留了实验问卷难以捕捉的幽默、梗、讽刺、情绪混合与集体叙事。
- 对人形机器人而言，公众评论常常把技术表现、国家想象、就业焦虑、拟人化共情和安全疑虑混合在同一句话中。

### 6.2 Chung-En Yu (2020) 的酒店机器人 YouTube 评论研究

现有笔记中的核心信息：

- 基于 Godspeed 维度开发预编码方案。
- 分析酒店机器人相关 YouTube 评论。
- 发现人们谈论 humanlike robots 时倾向负面，尤其围绕拟人化带来的害怕、不适和怪异感。

可作为本文的承接：

- 该研究说明社交媒体评论可用于分析公众对机器人的自然反应。
- 但它更接近小规模内容分析，未形成面向 NLP 任务的大规模 stance detection benchmark。
- 其编码仍主要继承 HRI 感知维度，而本文进一步引入 stance 与 discourse domain 的双层标注。

---

## 七、文献综述 Part V：Stance Detection 数据集与任务

### 7.1 Stance detection 的基本定义

当前笔记中的定义可保留：

给定文本 `s` 和目标 `t`，预测作者对目标 `t` 的立场标签：

`y ∈ {Favor / Against / None}`

本文可对应调整为：

`y ∈ {Support / Oppose / Neutral}`

目标定义为：

`t = humanoid robots`

注意：如果使用 codebook v0.2，应避免把 target 写成 “humanoid robot development”，因为当前 codebook 已修订为 “humanoid robots”。

### 7.2 现有任务类型

| 任务类型 | 定义 | 代表数据集 | 与本文关系 |
| --- | --- | --- | --- |
| In-target | 训练集和测试集共享目标 | SemEval-2016, P-Stance | 本文可作为特定目标数据集 |
| Cross-target | 测试目标与训练目标相关但不同 | WT-WT, MT-CSD | 后续可测试跨机器人事件泛化 |
| Zero-shot | 测试目标训练阶段未见 | VAST, EZ-STANCE, C-STANCE | 可作为 LLM baseline 的理论背景 |
| Conversational / multimodal | 多轮语境或多模态信息参与立场判断 | MT-CSD, MmMtCSD | 本文若使用图像/视频状态，可称 context-conditioned；若不直接用图像特征，需谨慎称 multimodal |

### 7.3 现有 stance 数据集的局限

可归纳为三个 gap：

1. **Domain gap**：现有数据集集中于政治、公共政策、选举、COVID 等领域。高科技产品虽有 Tesla、BMW、Bitcoin 等样本，但缺少人形机器人这一 embodied technology。
2. **Rationale gap**：多数 stance 数据集只标注 favor/against/none，不标注支持或反对背后的理由。
3. **Context gap**：公众对机器人立场可能受可见表现影响，例如成功、失败、摔倒、被扶起等情境会改变评论者的情感和立场表达。

### 7.4 LLM 与 stance detection

现有笔记中的核心文献：

- Pangtey (2025), Large Language Models Meet Stance Detection

可写作角度：

- LLM 为 stance detection 提供了 zero-shot / few-shot 分类能力。
- 但 stance 常常是隐含的、反讽的、依赖目标定义的，尤其在中文社交媒体语境中更容易被幽默和梗遮蔽。
- 因此本文的 benchmark 可以测试 LLM 是否能识别机器人公众话语中的 implicit stance 与 discourse domain。

---

## 八、本文标注策略：从文献维度到可操作 codebook

### 8.1 标注目标

本文不只回答 “公众是否支持机器人”，还回答 “公众通过什么话语框架来支持、质疑或拒绝机器人”。

因此标注分为两个正交维度：

1. `Stance`: Support / Oppose / Neutral
2. `Discourse Domain`: D1-D5 / D0

### 8.2 Stance 标注

Target：

> humanoid robots

判定逻辑：

- Support：评论直接或间接表达接纳、欢迎、期待、喜爱、认可。
- Oppose：评论直接或间接表达排斥、恐惧、质疑、抵触。
- Neutral：仅描述、提问、转述、玩梗，或态度无法判断。

关键边界：

- 要区分 stance 与 sentiment。觉得机器人摔倒好笑，不必然等于反对机器人。
- 要区分对事件的评价与对机器人的评价。批评赛事组织不必然等于反对机器人。
- 反讽和幽默按可推断真实意图标注；无法判断时标 Neutral。
- 复合态度按主导态度标注；势均力敌时标 Neutral。

### 8.3 Discourse Domain 标注

| 标签 | 名称 | 文献来源 | 典型问题 |
| --- | --- | --- | --- |
| D1 | Society & Nation | Firth, Cappuccio | 机器人是否代表国家进步、社会变迁或文明方向？ |
| D2 | Affect & Anthropomorphism | Bartneck, RoSAS, Spatola, Eyssel & Kuchenbrandt | 人们是否把机器人视作可爱、可怜、诡异、像人或可共情的对象？ |
| D3 | Human Identity & Labor | Firth, Cappuccio | 机器人是否威胁人类独特性、主体性、劳动和就业？ |
| D4 | Safety & Governance | Bartneck, Spatola, Cappuccio | 机器人是否带来安全、伦理、隐私、监管问题？ |
| D5 | Technology & Product | Bartneck, Firth | 评论是否主要评价性能、算法、续航、工程成熟度和商业化？ |
| D0 | None | 标注需要 | 评论无明确话语域或过短过模糊 |

### 8.4 为什么 discourse domain 要与 stance 独立

这一点是当前 codebook 的关键改动：话语域不是 stance rationale 的同义词，而是中性的主题领域。

例如：

- `D1 Society & Nation + Support`: “中国科技真的越来越强了。”
- `D1 Society & Nation + Oppose`: “说是科技进步，其实就是面子工程。”
- `D1 Society & Nation + Neutral`: “不知道这对社会意味着什么。”

这种设计可以避免把 “某类理由” 预设为必然支持或必然反对，也能允许后续做 stance × discourse domain 的交叉分布分析。

---

## 九、建议写作结构

### 9.1 Background

推荐段落顺序：

1. 机器人马拉松作为公共事件：人形机器人进入大众视野。
2. 社交媒体评论作为自然语料：捕捉真实、非引导、情绪和立场混合的公众反应。
3. 本文关注的问题：stance、discourse domain、visual/context-conditioned variation。

### 9.2 Related Work

推荐分成四小节：

#### 9.2.1 Public Perception of Robots

覆盖：

- Godspeed
- RoSAS
- Spatola
- Eyssel & Kuchenbrandt 的机器人群体身份与拟人化

核心结论：

> Existing HRI scales offer useful perceptual dimensions, but they are not designed as annotation schemas for large-scale, naturally occurring social media discourse.

#### 9.2.2 Robotic Ideology and Tolerance

覆盖：

- Firth (2020)
- Cappuccio (2024)

核心结论：

> Public reactions to robots are shaped not only by perceived usability or safety, but also by normative beliefs about autonomy, human identity, labor, and social order.

#### 9.2.3 Social Media Studies of Robots

覆盖：

- Chung-En Yu (2020)
- robot in the wild / 酒店机器人 YouTube 评论

核心结论：

> Prior social media studies show that online comments reveal rich reactions to robots, but they have not produced a large-scale stance detection benchmark with theoretically grounded rationale labels.

#### 9.2.4 Stance Detection Datasets

覆盖：

- SemEval-2016
- P-Stance
- VAST
- WT-WT / MT-CSD
- MmMtCSD
- Pangtey (2025) LLM stance detection survey

核心结论：

> Existing stance datasets focus heavily on politics, public issues, and a limited set of commercial or technological entities. Humanoid robots remain underrepresented, and stance rationales are rarely annotated.

### 9.3 Annotation Strategy

推荐分成三小节：

1. Target and stance labels
2. Discourse domain taxonomy
3. Annotation procedure and quality control

---

## 十、可直接使用的论文贡献表述

### 10.1 数据集贡献

RoboStance 是一个面向中文社交媒体人形机器人公共话语的 stance detection 数据集。它以机器人马拉松等公共事件为语境，收集公众对人形机器人的自然评论，并标注 Support / Oppose / Neutral 三类立场。

### 10.2 理论贡献

RoboStance 不只标注立场标签，还基于机器人意识形态、HRI 社会感知量表和 tolerance 理论构建了 discourse domain taxonomy，用于解释公众为什么支持、质疑或拒绝人形机器人。

### 10.3 方法贡献

RoboStance 可用于评估 LLM 在中文社交媒体隐含立场识别、话语域分类和 context-conditioned stance detection 上的能力，尤其适合分析机器人成功/失败情境下公众立场的变化。

---

## 十一、当前参考文献清单：按功能分组

### 机器人意识形态与容忍

- Firth, R. (2020). Robotic ideology.
- Cappuccio, M. L. (2024). Tolerance toward autonomous agents / autonomy estrangement.

### HRI 量表与机器人社会感知

- Bartneck et al. (2009). Godspeed Questionnaire.
- RoSAS 相关论文。
- Spatola (2021). Updated robot social perception scale.
- Eyssel & Kuchenbrandt (2012). Social categorization of social robots.
- Kuchenbrandt, Eyssel, Bobinger, & Neufeld (2013). Robot group membership and anthropomorphization.

### 社交媒体中的机器人公众感知

- Chung-En Yu (2020). YouTube comments and hotel robots / Godspeed-based coding.
- Ackermann (2025). Physical social robots in education and learning outcomes.

### Stance Detection 与 LLM

- Mohammad et al. (2016). SemEval-2016 Task 6.
- Li et al. (2021). P-Stance.
- Allaway & McKeown (2020). VAST.
- Conforti et al. (2020). Will-They-Won't-They.
- Mutlu et al. (2020). COVID-CQ.
- Kawintiranon & Singh (2021). Twitter Stance Election 2020.
- Niu et al. (2024). MmMtCSD.
- Pangtey (2025). Large Language Models Meet Stance Detection.

---

## 十二、下一步待补

- 补全每篇文献的正式 BibTeX / DOI。
- 确认 RoSAS、Spatola、Cappuccio 的准确题名、年份与引用格式。
- 将 `Discourse Domain` 与旧稿中的 `Rationale` 术语统一，建议正式稿中使用 `discourse domain` 或 `stance rationale domain`，避免把类别设计成天然带立场方向。
- 根据 BERTopic 或 pilot annotation 结果检验 D1-D5 是否需要合并、拆分或新增类别。
- 若论文中不直接输入图像特征，建议使用 `context-conditioned` 而不是 `multimodal` 描述任务。
