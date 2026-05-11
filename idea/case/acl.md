一、对你「机器人是谁 / 我是谁 / 形象关系」最相关的更新

🌟 1. Entity Framing and Role Portrayal in the News (Mahmoud et al., Findings 2025)

这篇的框架几乎就是你想做的事。它把"实体框架"分成 3 大类、22 个子类的角色：

          实体角色（Entity Role）
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    Protagonist  Antagonist  Innocent
    （主角）      （反角）     （无辜者）
        │           │           │
   ┌────┴────┐ ┌───┴───┐  ┌───┴────┐
   英雄/守护者 罪犯/欺骗者  受害者/被剥削者
   先驱/创新者 阴谋家/敌人  无助者
   殉道者     腐败者      ...
   ...

对你的启发：
- 你想做的"机器人是谁"完全可以套这个框架——机器人在不同 status 下被赋予什么 role？
- 失败状态："innocent victim（无辜受害者）" / "incompetent fool（无能者）"
- 弱势状态："helpless infant（无助婴儿）"
- 强势成功："threat（威胁）" / "hero（英雄）" 二元
- 这是 22 类的预定义体系，你可以拿来当 codebook 起点，不用从零建
- 论文配套数据集 + 标注协议公开，标注协议可以直接借鉴你的研究

我建议：你的"机器人指代"分析升级为 entity role portrayal——不只是"它/他/小可爱"的指代分类，而是"机器人被框架成什么角色"。这是更高层、更可发表的方法论。

🌟 2. Capturing Author Self Beliefs in Social Media Language (Mangalik et al., Main 2025)

直接对应你的"我是谁"那个问题。这篇做的事：从社媒语言里抽取作者自我信念（self-beliefs）——比如"我是受害者/我是观察者/我是专家"。

对你的启发：
- 你想做的"我是谁"（旁观者/共情者/焦虑主体/占有者）正好是 self-belief 的一种
- 它给了一套心理学校准的维度（基于 self-belief 心理学），而不是你和我自己脑补的位格类型
- 方法论现成可用

🌟 3. Talking Point based Ideological Discourse Analysis in News Events (Nakshatri et al., Findings 2025)

这篇做的是"形象之间的关系"——不同立场怎么围绕同一事件展开"talking points"，谁支持谁、谁反对谁。

对你的启发：
- 把"talking points"换成"对机器人的不同框架"——它给你一套抽取-比较-对齐的流程
- 适合做"跨 status 同一话题怎么被不同地讲述"

🌟 4. TikTalkCoref (ACL 2025) - 中文社媒 multimodal coreference

第一个中文社媒共指消解数据集（抖音短视频）。

对你的启发：
- 你之前想做的"它/他/她"指代消解，现在有现成的中文社媒模型可参考
- TikTok 短视频评论生态跟小红书类似，模型可能直接迁移

---

二、对你「评论层级 / 反驳结构」最相关的更新

🌟 5. ZS-CSD: Zero-Shot Conversational Stance Detection (Ding et al., Findings 2025)

这篇就是给你做的。来自武汉大学，中文微博数据，做的就是评论树里的立场检测：

数据集特征
价值
280 个 target × 多层 conversation tree（深度 1 到 ≥6）
跟你的小红书评论树同构
中文
直接用
立场三分类：favor / against / neutral
跟你说的"附和/反驳" 对应
同时考虑 speaker interaction（谁回谁，对齐还是不对齐）
这正是你说"结构没用上"的部分

关键警示：他们 SOTA 只到 F1=43.81%——zero-shot 中文对话立场检测真的很难。我之前给你说"规则版能到 70-80%"是基于英文表面分析，中文社媒 + 隐含立场 + 反讽 + 表情符号实际效果会差很多。

对你的启发：
- 不要做完整 zero-shot 立场分类（难度太大，需要标 280 target 训练数据）
- 缩到你研究的 1 个 target：「机器人」——这就把 zero-shot 问题变成 in-target 问题，准确率能上 70-80%
- 数据集可以下载来 fine-tune 或做 few-shot prompt
- 方法：他们用 SITPCL（speaker interaction + target-aware prototypical contrastive learning）。如果你不想训模型，可以借鉴他们的"speaker interaction encoding"思路，加到 LLM prompt 里

🌟 6. Parody Detection (ACL 2025)

7 个数据集，含中文，14755 标注用户，21210 标注评论，带 user interaction graphs。

对你的启发：
- 你的语料里"反讽/戏谑"很多（"输在起跑线上"、"机器人也是人"），这是 parody 的一种
- 该论文的 user interaction graph 模型可以借鉴——把评论树建成图、每个节点编码、做立场学习
- 数据集可以拿来当外部预训练数据：先在它上面 fine-tune，再迁移到你的小红书数据

🌟 7. GNN on Conversation Graphs for Abusive Language Detection (ACL 2025)

虽然主题是 abusive language，但方法论可直接迁移：把社媒会话建模成图（节点=评论，边=回复关系），用 GNN 学。

对你的启发：
- 你之前问"评论层级没用上"，这个论文给出了具体方法
- 可作为对话分析的工程蓝图

---

三、对你的「主题建模」流程最相关的更新

🌟 8. Neural Topic Modeling with LLMs in the Loop (Yang et al., Main 2025)

这是 ACL 2025 主会主题建模的旗舰论文。框架：

NTM 学全局主题
       │
       ▼ 候选主题词
       ╭──────────╮
       │   LLM     │ ← 用 LLM 评估主题词质量、提供更好的主题词
       │ (in loop) │
       ╰─────┬────╯
             ▼
   Optimal Transport 对齐
   （根据 LLM 信心动态调整）
       │
       ▼
   更新 NTM

核心创新：LLM 不是替代 NTM，而是 in-the-loop 校准 NTM。模块化，任何现有 NTM 都能接——理论上 BERTopic 也行。

对你的启发：
- 比"BERTopic 跑完用 LLM 重命名主题"更有原则
- 但工程复杂，至少 1-2 周
- 建议作为 v3 升级路径，不是当前阶段

🌟 9. S³ - Semantic Signal Separation (Kardos et al., Main 2025)

新型主题模型，思路是**"语义信号分离"**而不是聚类。把整个语料看成多个语义信号的混合，然后做 ICA 类的分离。

对你的启发：
- 适合"评论是多个语义信号叠加"的情况——你的语料里一条评论常同时有"嘲讽 + 怀疑 + 隐喻"
- BERTopic 强制一条评论一个主题；S³ 允许一条评论分解成多个信号
- 可以并行试一下，跟 BERTopic 对比

🌟 10. ZeroDL - Zero-shot Distribution Learning for Text Clustering via LLMs (Findings 2025)

用 LLM 做无监督文本聚类，不需要任何标注数据。

对你的启发：
- 跑一遍跟 BERTopic 对比，看是不是 LLM 直接聚出来的更符合人类学直觉
- 工程上比 LLM-ITL 简单

🌟 11. LLMTaxo - Constructing Taxonomy of Factual Claims via LLMs (Findings 2025)

用 LLM 自动构建社媒声明的层级 taxonomy。

对你的启发：
- 这个直接对应你想要的「先 master schema 再细分」
- 你可以让 LLM 在 anchor 上自动生成主题层级 taxonomy，跟 BERTopic 的 hierarchical_topics 对比

---

四、综合判断：我们的方案要不要调

✅ 不需要大改

你的 anchor + residual 设计仍然主流方法，没有更优替代方案出来。

🔧 建议调整 3 处

调整 1：「机器人是谁」从指代统计升级到 entity role portrayal

之前：用 robot_reference_lexicon 统计"它/他/小可爱"分布
升级：套用 [Entity Framing 论文](https://aclanthology.org/2025.findings-acl)的 22 类 role 框架，在你的 4 个 status 子集上各做一份 entity role distribution 表

好处：方法论现成、有可比性、可投稿框架更清楚

调整 2：「我是谁」用 self-belief 框架而非自创位格类型

之前：旁观者/共情者/焦虑主体/占有者（你和我自创）
升级：用 [Mangalik et al.](https://aclanthology.org/2025.acl-long) 的 self-belief 维度（心理学校准的）

好处：避免自创类型被审稿人质疑"理论依据不足"

调整 3：对话立场检测降低期望值

之前：我说规则版能 70-80% 准确
修正：基于 ZS-CSD 的 SOTA 只有 43.81%，中文 + 多层评论 + zero-shot 是真难

实际可行的做法：
- 缩到 1 个 target「机器人」 → 变成 in-target，准确率提到 70%+
- 用 ZS-CSD 数据集做 fine-tune 或 few-shot prompt
- 或者干脆只做反驳标记的检测（"不/才不/反对"）+ BGE 反向语义余弦，准确率会高一些
- 接受 70% 的标注精度，做"分布性结论"而非"逐条诊断"

---

五、给你的具体新建议

优先
动作
用到的 ACL 2025 工作
🥇
「机器人是谁」用 entity role portrayal 框架做
Entity Framing (Mahmoud)
🥈
「我是谁」用 self-belief 维度
Capturing Author Self Beliefs (Mangalik)
🥉
反驳分类用 ZS-CSD 数据 + 缩到机器人单 target
ZS-CSD (Ding)
🔧
anchor schema 跑 LLMTaxo 对比 BERTopic hierarchical_topics
LLMTaxo
🔧
主题建模可选 v3：LLM-ITL
LLM-ITL (Yang)
🆕
反讽/戏谑评论加跑 parody detector
Parody Detection (ACL 2025)

我最强烈推荐的一条

🥇 entity role portrayal——它给你的"机器人是谁"研究：
1. 现成的 22 类 role taxonomy（不用自己设计）
2. 标注协议公开（你的人工编码可以照做）
3. 论文里有评估方法（你研究有可比基线）
4. 是 2025 年新出的，追这个热点写文章正当时

---

六、一个诚实补充

ACL 2025 主流仍是 LLM 中心化（fine-tune、prompt、agent...），纯统计/聚类的主题建模论文相对在缩。你的研究如果走"主题建模 + 解释"路线，是经典 CSS 套路；如果想追 hot topic，可以考虑加一层 LLM-based 解释（比如用 LLM 给每个主题生成"role portrayal 描述"）。

但不要为了追热点放弃方法论严谨——LLM 解释虽然漂亮，但缺乏可重现性，CSS/Communication 期刊审稿人对纯 LLM 方法警惕度上升。你目前的 BERTopic + 人类学解释路径反而是相对稳妥的。