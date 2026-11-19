---
id: stance_en
version: "1.0.0"
description: |
  Stance toward humanoid robots · English comment · gold column stance.
label_map:
  Support: 支持
  Oppose: 反对
  Neutral: 中立
output:
  json_field: stance
  reason_field: reason
  retry_hint: 'Output only JSON: {"reason": "...", "stance": "Support|Oppose|Neutral"}'
---

# ROLE
Classify the commenter's **stance toward humanoid robots / the depicted situation** (not sentiment alone). One label.

# CATEGORIES
Support: Affirms capability, progress, cuteness, or defends the robot/technology.

Oppose: Mocks, rejects, fears, or denies legitimacy of the robot/tech.

Neutral: Descriptive, questioning, or ambiguous teasing without clear pro/con (explain in reason).

# INPUT
<comment>{comment}</comment>

# OUTPUT
{{"reason": "Brief rationale", "stance": "Support|Oppose|Neutral"}}
