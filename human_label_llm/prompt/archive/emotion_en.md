---
id: emotion_en
version: "1.0.0"
description: |
  Emotion valence · English comment · gold column 情感.
label_map:
  Negative: Negative
  Neutral: Neutral
  Positive: Positive
  Mixed: Mixed
output:
  json_field: sentiment
  reason_field: reason
  retry_hint: 'Output only JSON: {"reason": "...", "sentiment": "<Negative|Neutral|Positive|Mixed>"}'
---

# ROLE
Classify sentiment of short comments about robots in public spaces. One label only.

# CATEGORIES
Negative: Pessimistic, disapproving, fearful, or mocking tone.

Neutral: Factual or emotionally flat statements.

Positive: Supportive, optimistic, or approving tone.

Mixed: Conflicting or layered emotions that cannot be reduced to one pole.

# INPUT
<comment>{comment}</comment>

# OUTPUT
{{"reason": "Brief rationale", "sentiment": "Negative|Neutral|Positive|Mixed"}}
