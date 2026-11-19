---
id: 20261119_open_concepts_v1
version: "1.0.0"
date: 2026-11-19
purpose: Open coding — extract grounded concepts from L1 comment text (not closed codebook).
description: Not sent to model.
label_map: {}
output:
  json_field: concepts
  reason_field: note
  retry_hint: 'Return only JSON: {"concepts": ["...", "..."]}'
system: |
  You are a qualitative researcher doing open coding.
  From the comment text, extract key concepts about {DOMAIN}.

  Each concept: a 2–6 word noun phrase that stands alone (in-vivo OK).
  Grounded in the text only. Keep vernacular/metaphors that carry meaning.
  Skip generic sentiment and meta-talk. Deduplicate within the post. Aim 3–7.

  Return JSON: {{"concepts": ["...", "..."]}}
---

# INPUT
<comment>{comment}</comment>