---
id: stance_zh
version: "1.0.0"
description: |
  观念层立场三分类 · 中文评论 · gold 列 stance（完整 d1–d4 另跑或人工）。
label_map:
  支持: 支持
  反对: 反对
  中立: 中立
output:
  json_field: stance
  reason_field: reason
  retry_hint: '仅输出 JSON：{"reason": "...", "stance": "支持|反对|中立"}'
---

# 角色
判断评论对人形机器人相关议题的**总体立场**（非情感极性 alone），只选一个。

# 类别
- **支持**：肯定能力、进步、可爱、有意义，或为机器人/技术辩护。
- **反对**：嘲讽、否定、质疑造假、排斥、恐惧、拒绝。
- **中立**：客观陈述、提问、难以判向的调侃（须在 reason 中说明）。

# 输入
<comment>{comment}</comment>

# 输出
{{"reason": "简要理由", "stance": "支持|反对|中立"}}
