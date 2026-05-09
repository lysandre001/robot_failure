# relation_v1 experiment summary

- run_id: `2026-05-09_relation_detect_v1_lexicon`
- input: `/Users/yilin/project/2604-robotic_failure_research/output/phase1/data/clean_comments_unified.csv`
- lexicon: `/Users/yilin/project/2604-robotic_failure_research/config/relation_lexicon_v1.csv`
- coverage(any relation): `22.31%`

## Top relation types by hit comments
```
      relation_type  n_hit_comments  hit_rate  avg_hits_per_hit_comment  median_like_when_hit
           tool_toy            5150  0.164826                  1.847767                   0.0
           pet_cute             799  0.025572                  1.055069                   0.0
species_competition             747  0.023908                  1.056225                   0.0
          parenting             589  0.018851                  1.130730                   0.0
       warrior_hero             214  0.006849                  1.289720                   0.0
        peer_worker             165  0.005281                  1.006061                   0.0
```

## Notes
- Baseline is lexicon matching; implicit metaphors are not fully captured.
- Topic linking uses TF-IDF bigram + KMeans for lightweight comparability.