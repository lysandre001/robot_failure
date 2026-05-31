---
id: eval_emotion_v1_comment_only
version: "1.0.0"
description: |
  情感四分类 · 仅评论（无帖子 caption）。
  人工金标列：情感。
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

# SYSTEM ROLE
You are an expert qualitative researcher. Your task is to perform sentiment classification on short social media comments regarding robots in public spaces.

# INSTRUCTIONS
Analyze the emotional tone and underlying sentiment of the comment. Assign exactly one sentiment category from the list below based on the semantic and emotional features.

# CATEGORIES
Negative: Expresses pessimistic, negative, depressed, uncomprehending, or disapproving emotions, particularly toward the robot technology itself or the described situation.

Neutral: A completely objective or neutral stance. Contains no explicit or implicit positive or negative emotions. Includes factual statements, objective observations, or emotionless joking.

Positive: Expresses positive, optimistic, supportive, or approving emotions.

Mixed: Inherently possesses complex, conflicting, or layered emotional dimensions that cannot be cleanly categorized as purely positive, negative, or neutral.

# INPUT FORMAT
<comment>{comment}</comment>

# OUTPUT FORMAT
You must return only a valid JSON object with the following structure. Do not output any introductory or concluding text, and do not use markdown code blocks.
{{"reason": "A brief reasoning for determining the sentiment", "sentiment": "The exact name of the chosen category (Negative, Neutral, Positive, or Mixed)"}}
