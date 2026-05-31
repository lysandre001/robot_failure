# Methods: Topic Discovery — Level 2（二级回复）

## Corpus and analysis unit
**Level-2 replies only** (`comment_level=2`; `n=10,910`). Frozen in `corpus_freeze.json`. Subset of the shared analyzable corpus (`n=26,811` pooled).

## Embedding and clustering
Comments embedded with `BAAI/bge-base-zh-v1.5`, UMAP (`n_components=5`, `random_state=42`), BERTopic + HDBSCAN. Compared `min_cluster_size` 30/50/80/100 (`hdbscan_candidate_summary.csv`). **`mcs=30`** retained (50 raw topics; largest valid-cluster share 10.0%; `mcs=80/100` collapse to mega-clusters).

## Topic-number selection
Scanned `reduce_topics(nr)` for `nr ∈ {10,15,…,100}` on the `mcs=30` model; C_V + 12% largest-cluster guard (`topic_number_cv_curve.csv`). Max C_V at `nr=15` rejected (largest share 32.9%). Selected **`nr=45`** (44 topics, C_V=0.505, largest share 10.0%) — `topic_number_selection_notes.md`. For `nr≥45`, C_V plateaus because base HDBSCAN yields at most ~50 topics.

## Outliers
Raw HDBSCAN outlier rate 47.8% (`topic_raw=-1`). Primary human merge uses raw non-outlier assignments.

## Human merge (pending)
Coder sheets: `coder{1,2}_sheet_final_nr45.csv`. Agreement → `final_topic_map.csv` → backfill.

## Validation
Cluster metrics: run root `layer_cluster_metrics.csv` + `EVALUATION_CHECKLIST.md`. See `REPRO.md` for commands.
