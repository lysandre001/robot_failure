# Methods: Topic Discovery (Draft)

## Corpus and analysis unit
We analyze **comments** (`comment_id`) from the frozen shared corpus (`n=26,811`; SHA in `corpus_freeze.json`). Raw unified comments (`n=41,251`) were filtered for empty/short text, insufficient effective tokens, duplicates, and missing metadata; exclusion counts are reported in `config.json` → `summary_corpus`.

## Embedding and clustering
Comments were embedded with `BAAI/bge-base-zh-v1.5`, reduced with UMAP (`n_components=5`, `random_state=42`), and clustered with BERTopic + HDBSCAN. We compared HDBSCAN `min_cluster_size` candidates (30/50/80/100) on outlier rate, topic count, and largest-cluster share (`hdbscan_candidate_summary.csv`). **`mcs=50`** was retained as the base candidate (88 raw topics; largest valid-cluster share 7.6%) because `mcs=80` produced a dominant mega-cluster (~39% of valid docs).

## Topic-number selection
Before manual coding, we scanned `reduce_topics(nr)` for `nr ∈ {10,15,…,100}` on the `mcs=50` model, computing **C_V coherence** (gensim, jieba-tokenized corpus) and structural diagnostics per candidate (`topic_number_cv_curve.csv`). Maximum C_V occurred at `nr=50` (C_V=0.683) but implied a 20% largest-cluster share; we **rejected** this blind optimum and selected **`nr=85`** (84 topics, C_V=0.559, largest-cluster share 7.6%) as the final machine solution—highest C_V among candidates passing the 12% largest-cluster guard (`topic_number_selection_notes.md`).

## Outliers
Raw HDBSCAN outlier rate is 44.4% (`topic_raw=-1`); we treat outliers as conservative handling of low-density semantic tail. Primary human merge uses **raw non-outlier** assignments; `topic_assigned` after `reduce_outliers` (0.9% outliers) is sensitivity only (`sensitivity/outlier_raw_vs_assigned.csv`).

## Human merge (pending)
Two coders independently label each final machine topic using enhanced review sheets (`top_terms`, representative docs, cross-post, random, and top-like examples). Coders may use `mixed/unclear`. An adjudicator produces `final_topic_map.csv`; agreement is summarized with Cohen's kappa.

## Validation and sensitivity
- Topic purity: random audit sample (`purity_validation_sample.csv`) plus targeted review of high `top_post_share_raw` topics (`sensitivity/high_post_dominance_topics.csv`).
- Model sensitivity: adjacent `nr` candidates (`sensitivity/adjacent_topic_number_comparison.csv`).
- HDBSCAN sensitivity: alternate `mcs` summaries (`sensitivity/hdbscan_mcs_sensitivity_summary.csv`).

## Reproducibility
See `REPRO.md` for commands and output inventory.
