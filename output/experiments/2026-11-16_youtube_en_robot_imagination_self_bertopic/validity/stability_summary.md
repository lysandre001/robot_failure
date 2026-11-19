# Q1 — clustering stability (reference: `bert_hdbscan_mcs80`)

- Documents: N=28096
- Primary outlier rate: 0.4149

## MCS sweep (frozen UMAP from main pipeline, seed=42)

| run_id | mcs | umap_seed | source | n_topics | outlier_rate | ari | nmi | mean_top10_jaccard | mean_top10_rbo | n_matched_topics |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mcs30 | 30 | nan | existing_bertopic | 136 | 0.385108 | 0.518033 | 0.75169 | 0.5573151793740029 | 1.1644269268529612 | 60.0 |
| mcs50 | 50 | nan | existing_bertopic | 90 | 0.382652 | 0.743006 | 0.8632 | 0.6442893363945997 | 1.3031830760365282 | 60.0 |
| mcs80 | 80 | 42.0 | existing_bertopic | 60 | 0.414935 | 1.0 | 1.0 | 1.0 | 1.7059332584823288 | 60.0 |
| mcs100 | 100 | nan | existing_bertopic | 48 | 0.451274 | 0.819949 | 0.899394 | 0.7003109635462575 | 1.54402939391747 | 50.0 |

## UMAP random seeds (re-fit UMAP + HDBSCAN mcs=80)

HDBSCAN on a fixed reduction is deterministic; seed variation refits UMAP only.

| run_id | mcs | umap_seed | source | n_topics | outlier_rate | ari | nmi | mean_top10_jaccard | mean_top10_rbo | n_matched_topics |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| umap_seed42 | 80 | 42.0 | primary_ref | 60 | 0.414935 | 1.0 | 1.0 | nan | nan | nan |
| umap_seed43 | 80 | 43.0 | cached | 60 | 0.412621 | 0.741946 | 0.838056 | nan | nan | nan |
| umap_seed44 | 80 | 44.0 | cached | 58 | 0.3708 | 0.658134 | 0.812235 | nan | nan | nan |
| umap_seed45 | 80 | 45.0 | cached | 57 | 0.405467 | 0.7661 | 0.849833 | nan | nan | nan |
| umap_seed46 | 80 | 46.0 | cached | 59 | 0.399381 | 0.78186 | 0.859858 | nan | nan | nan |