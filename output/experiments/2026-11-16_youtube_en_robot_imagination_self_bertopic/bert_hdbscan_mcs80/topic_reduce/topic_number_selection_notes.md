Base: bert_hdbscan_mcs80 (~60 HDBSCAN topics).
Merge method: BERTopic reduce_topics (c-TF-IDF cosine), not keyword mega.
Outlier rate unchanged by reduce_topics (~41.5% at -1).

Recommended report merge: **nr=35 → 34 topics**, C_V=0.5261, largest_share=0.255 on non-outlier docs.
No scanned nr≤35 met 12% largest-cluster guard (EN comments are bursty); pick by C_V within 12–35.

Structural alt (max_share≤12% only at end of grid): nr=55 → 54 topics (minimal merge).

Re-run: `.venv/bin/python -m tools.topic_validity.reduce_topics_scan`
Re-materialize another K: `--select-only 25` (or any scanned nr).