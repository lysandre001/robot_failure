# STM run 2026-11-17 12:01:21.822182
K selected: 40 (max exclusivity among 20,40,60 )
N docs after prep: 27993
Vocab: 4206

## Model
- prevalence ~ perspective + event
- content ~ perspective

## Compare to BERTopic
- BERTopic fixes embedding+UMAP+HDBSCAN then compares three codebook slices on same topic ids.
- STM jointly models prevalence/content covariates; expect directionally similar perspective contrasts on war/China/imagination tokens, not 1:1 topic alignment.

Artifacts: stm_searchK.csv, stm_top_terms_*.csv, stm_prevalence_summary.txt
