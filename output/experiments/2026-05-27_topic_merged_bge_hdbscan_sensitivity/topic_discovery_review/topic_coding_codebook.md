# Topic Coding Codebook (final nr=85)

## Analysis unit
- One row = one **comment** (`comment_id`), not post/user/thread.

## Machine vs human layers
- Machine `topic_id`: BERTopic+HDBSCAN candidate cluster after `reduce_topics(nr=85)`.
- Coder `domain`: higher-level discourse domain (open inductive; merge synonyms after round 1).
- Coder `label`: specific theme name for the machine topic.
- `mixed/unclear`: allowed when evidence is insufficient.

## Evidence to use (in order)
1. `top_terms` + `representative_docs`
2. `sample_comments_10` (10 comments per topic; full fields in `topic_comment_samples_final_nr85.csv`)
3. Legacy blocks `top_like_examples` / `post_diverse_examples` / `random_examples` remain in review sheet only

## Diagnostics
- `top_post_share_raw` > 0.30: check single-post dominance before naming.
- Compare `level1_share_raw` vs `level2_share_raw` for reply-structure bias.

## Agreement
- Two independent coders fill `coder1_sheet_final_nr85.csv` and `coder2_sheet_final_nr85.csv`.
- Rename completed files to `*_done.csv` before running agreement.
- Adjudicator fills `final_topic_map.csv` with `final_domain`, `final_label`, `adjudication_notes`.

## Primary analysis field
- Use raw/non-outlier topics for main human merge; `topic_assigned` is sensitivity only.
