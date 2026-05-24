我给你提 3 个可行方案，10 天内都能做完

🥇 方案 A：「Beyond Generic Emotions: Tech-Reception-Specific Affect Categories in Chinese Social Media」

核心论点：GoEmotions 的 27 类、Plutchik 8 类、Ekman 6 类——对高新科技产品评论都不够用。它们抓不到：

你提出的新类（举例）
GoEmotions 里没有 / 抓不准
Replacement Anxiety（替代焦虑）
"外卖员快被取代了" → GoEmotions 标 fear，但其实是 prospective career displacement
Ontological Doubt（本体怀疑）
"这真是 AI 吗？还是遥控的" → 不在任何标签
Anthropomorphic Affection（拟人化共情）
"小机器人好可爱" → GoEmotions 标 love，但其实是 cuteness-toward-non-human
Technological Awe（技术敬畏）
"厉害啊科技进步" → wonder + fear 混合
Pseudo-witnessing Pleasure（戏谑见证）
"笑死哈哈哈" → joy 不准，是 distancing humor
Uncanny Discomfort（恐怖谷不适）
"看着有点怪" → 没有标签
Boundary Negotiation Distress（边界协商焦虑）
"有轮子叫汽车不叫机器人" → 隐性身份焦虑

论文结构（4 页）：
1. Introduction: 现有 affect taxonomy 主要源于 lab / 普通文本，对 emerging tech reception 失灵
2. Tech-Affect Taxonomy 提出: 8-10 类，每类有定义 + 典型例子
3. 数据 + 标注: 你的小红书 18k → 抽 500 条标注 + Cohen's Kappa
4. 实验:
- GoEmotions zh classifier 直接套你数据 → 显示 macro-F1 很低
- 在你 500 条上 fine-tune BGE → 显示提升 20-30%
- LLM zero-shot prompt（GPT-4o / Qwen-72B）做 baseline
5. 分析: 各类 affect × robot_status 分布 → 显示 status 对 affect 类型有显著影响
6. Discussion: tech-reception affect 的理论意义 + 局限

10 天工作量分解：
| 天数 | 做什么 |
|---|---|
| 1-2 | 定 taxonomy（8-10 类）+ 写 1-页 annotation guide + 写 intro 草稿 |
| 2-4 | 你 + 1 个研究助理标 500 条（每人标 250）+ 50 条 overlap 算 IRR |
| 4-5 | 训练 baseline：GoEmotions-zh 套用 + BGE 微调 + LLM zero-shot |
| 5-6 | 跑 affect × topic × status 交叉表 |
| 6-8 | 写主体（method, results, analysis） |
| 9 | 写 discussion + related work + 修限制 |
| 10 | Polish + 提交 |

EMNLP 接受预测：Findings 概率中-高。Tech-affect 这个 niche 论文圈在涨，标注小但 taxonomy 新颖且理论根硬，是 Findings 喜欢的类型。

---

🥈 方案 B：「How Robot 'Status' Reframes Affect: A Computational Study of Status-Conditioned Emotional Discourse」

核心论点：同一个实体（机器人），观众的情感反应被它的"被呈现状态"系统性重塑。失败时同情，强势时焦虑，可爱时拟人。这是 affect 研究里被忽视的"frame conditioning"现象。

论文结构：
1. Introduction: stance/affect detection 默认 target 固定，但同一 target 在不同 frame 下激发不同 affect
2. 数据: 你的 14 帖 4 个 status 层 + 已有 BERTopic 结果
3. Method: 用 LLM 给每条评论标 affect（用你定义的小 taxonomy 或 GoEmotions），按 status 切分
4. Results:
- 同一类 target → 不同 status 下 affect 分布显著不同
- "失败"激发 sympathy + ridicule（混合）
- "强势"激发 awe + threat（混合）
- 显示混合情感比单一情感占主导
5. Discussion: stance/affect detection 任务设计应该 condition on frame

优点：不需要标注，主要用 LLM auto-labeling + 你已有的结构
缺点：贡献偏分析性，弱于方案 A 的"提新 taxonomy"
10 天可行性：✅ 高，可能 7 天就写完

EMNLP 接受预测：Findings 概率中。亮点是"frame conditioning affect"这个新视角，但 reviewer 可能挑标注质量。