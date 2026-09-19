---
id: emotion_zh
version: "1.0.0"
description: |
  情感四分类 · 中文评论 · 金标列 情感。
label_map:
  Positive: Positive
  Negative: Negative
  Neutral: Neutral
  Mixed: Mixed
output:
  json_field: sentiment
  reason_field: reason
  retry_hint: '仅输出 JSON：{"reason": "...", "sentiment": "Positive|Negative|Neutral|Mixed"}'
---

# 角色
对关于机器人的短评论做**情感极性**分类，只选一个标签（英文枚举与 gold 一致）。

# 类别
- **Positive**：积极、支持、赞赏、乐观。
- **Negative**：消极、嘲讽、失望、恐惧、反对。
- **Neutral**：客观陈述、无明显正负情感。
- **Mixed**：正负或复杂情感并存，无法归入单一极性。

# 输入
<comment>{comment}</comment>

# 输出
{{"reason": "简要理由", "sentiment": "Positive|Negative|Neutral|Mixed"}}
