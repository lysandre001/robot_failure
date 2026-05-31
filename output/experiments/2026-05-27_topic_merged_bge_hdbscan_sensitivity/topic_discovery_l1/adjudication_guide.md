# Adjudication Guide

## Inputs
- `coder1_sheet_final_nr85_done.csv` — coder 1 completed labels
- `coder2_sheet_final_nr85_done.csv` — coder 2 completed labels
- `topic_coding_codebook.md` — coding rules

## Steps
1. Each coder independently fills `domain`, `label`, `notes` for every `topic_id`.
2. Save completed sheets as `*_done.csv` (do not overwrite blank templates).
3. Run agreement:
   ```bash
   ./.venv/bin/python -m phase1.run_topic_discovery --step agreement
   ```
4. Review `coder_disagreements.csv`; adjudicator fills `final_topic_map.csv`:
   - Copy `final_topic_map_template.csv` → `final_topic_map.csv` if starting fresh.
   - Columns: `topic_id`, `final_domain`, `final_label`, `adjudication_notes`, `validation_flag`
5. Run backfill:
   ```bash
   ./.venv/bin/python -m phase1.run_topic_discovery --step backfill
   ```

## Agreement metrics
- Cohen's kappa on `domain` (primary)
- Cohen's kappa on `label` (secondary; report disagreement types)
- Re-code domains with kappa < 0.60 before final map freeze

## Freeze rule
Once `final_topic_map.csv` is approved, rename to `final_topic_map_frozen.csv` and do not edit without a new run id.
