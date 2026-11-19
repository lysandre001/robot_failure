# L1 open concept extraction

Infer outputs for open coding live here (not under `output/label_runs/`).

Each run: `output/concept_extract/<run_id>/`

- `run.yaml` — experiment config snapshot
- `log.jsonl` — source of truth (resume by `comment_id|model|scope`)
- `comment_concepts.csv` — wide table (`export_open_concepts.py`)
- `concepts_long.csv` — long table for merge
- `merge/roundN/` — optional canonical merge batches

Experiment yaml: `human_label_llm/experiment/20261119_youtube_l1_open_concepts_*.yaml`  
`output_root: output/concept_extract`