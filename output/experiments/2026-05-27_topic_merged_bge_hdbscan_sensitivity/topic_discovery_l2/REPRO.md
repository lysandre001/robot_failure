# Topic Discovery Reproducibility Pack

## Frozen inputs
- Run ID: `2026-05-27_topic_merged_bge_hdbscan_sensitivity`
- Analysis unit: `comment`
- Shared corpus: `output/experiments/2026-05-27_topic_merged_bge_hdbscan_sensitivity/shared_analyzable_corpus.csv`
- Corpus freeze: `topic_discovery_review/corpus_freeze.json`

## Pipeline commands

```bash
# Full pipeline (from repo root, venv python)
./.venv/bin/python -m phase1.run_topic_discovery --step all

# Individual steps
./.venv/bin/python -m phase1.run_topic_discovery --step freeze
./.venv/bin/python -m phase1.run_topic_discovery --step select
./.venv/bin/python -m phase1.run_topic_discovery --step review
./.venv/bin/python -m phase1.run_topic_discovery --step sensitivity
./.venv/bin/python -m phase1.run_topic_discovery --step agreement   # after coders finish
./.venv/bin/python -m phase1.run_topic_discovery --step backfill      # after adjudication
```

## Final model
- Base HDBSCAN: `mcs=30`
- Selected `reduce_topics` target: **nr=45**
- Selection notes: `topic_number_selection_notes.md`
- Final topics: `final_model/topics_final.csv`
- Final assignments: `final_model/doc_topics_final.csv`

## Coder materials
- Review sheet: `topic_review_sheet_final_nr45.csv`
- Coder sheets: `coder1_sheet_final_nr45.csv`, `coder2_sheet_final_nr45.csv`
- Codebook: `topic_coding_codebook.md`
- Adjudication template: `final_topic_map_template.csv` → fill as `final_topic_map.csv`

## Appendix tables
| File | Purpose |
|------|---------|
| `topic_number_cv_curve.csv` | C_V vs target nr_topics |
| `topic_number_cv_curve.png` | Coherence curve figure |
| `topic_number_candidate_diagnostics.csv` | Structural diagnostics per candidate |
| `hdbscan_candidate_summary.csv` | HDBSCAN mcs comparison |
| `topic_post_diagnostics_final_nr45.csv` | Topic-by-post dominance |
| `sensitivity/*` | Model/outlier/post-dominance sensitivity |
| `coder_agreement_summary.csv` | Cohen's kappa (after coding) |
| `final_domain_descriptive_stats.csv` | Backfilled domain stats |
| `output_manifest.csv` | File existence checklist |
