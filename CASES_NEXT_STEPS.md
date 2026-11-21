# Case store: status + next steps for Claude Code

Owner: case normalization (11 historical cases). Scope is ONLY the case store, not the full pipeline.

## Done (already in the repo)
- `database/curation/case_curation.json`: AI-assisted, human-reviewed mapping of all 11 raw case narratives to the
  canonical enums in `src/schemas/domain_models.py` (sector, workforce, problem signals, healthy signals,
  intervention steps with phase_bucket, research snippet numbers). Every signal has an exact source quote and
  an evidence level (`stated` / `inferred`).
- `src/offline/case_normalizer.py`: deterministic builder. Verifies every quote is verbatim in the raw case,
  validates enums, joins the T0/T1 analytics snapshots 1:1 on `case_name`, computes ROI deltas sorted by
  impact and writes `database/normalized/normalized_cases.json` (NormalizedCasesDB).
  - build: `python -m src.offline.case_normalizer`
  - verify only: `python -m src.offline.case_normalizer --check`
- `database/normalized/normalized_cases.json`: generated, 11 cases, validates against NormalizedCasesDB.
- `tests/test_case_normalizer.py`: 8 tests (quotes verbatim, fabricated quote rejected, no scenario names leak,
  advocacy precedents crisis -> phase 3 vs healthy -> phase 1, no LinkedIn storytelling for frontline).
  Run: `python -m unittest tests.test_case_normalizer -v`

## Next steps (do these, nothing else)
1. In `src/offline/normalize_databases.py`, implement ONLY `build_normalized_cases(...)` by delegating to
   `src.offline.case_normalizer.build_cases_db(raw_sandbox_data, raw_snapshots_data, curation)` where curation
   is loaded from `database/curation/case_curation.json`. Keep the `llm_client` parameter (unused, document why:
   curation was drafted once with an LLM and human-reviewed, so runtime is deterministic). Do NOT touch
   `build_normalized_rules` (owned by a teammate).
2. In `src/offline/database_loader.py`, implement ONLY `load_normalized_cases(cases_path)`:
   read file, `NormalizedCasesDB.model_validate_json`, fail fast if `cases` is empty, check unique case_id and
   case_name, return the db.
3. Add a helper module `src/offline/case_matching.py` (pure functions, no company names) used later by Step 3:
   - `candidate_actions_from_cases(cases_db, client_signals, workforce, sector) -> list` of
     (ActionCategory, case_id, phase_bucket) from cases whose problem tags overlap the client's signals and
     whose workforce archetypes intersect the client's workforce.
   - `rank_top_cases(cases_db, client_signals, workforce, sector, planned_actions, weights, k=3)`:
     hard exclude workforce mismatch (frontline vs desk-based tech), then score with
     `ScoringWeightsConfig` from normalized_rules.json (root_cause_overlap, workforce_fit, sector_fit,
     roi_evidence, cfo_auditability). Return score breakdown + human-readable reason
     ("3/5 root causes match, same workforce") + top 3 `delta_display` lines.
   - Unit tests with synthetic, company-agnostic signal sets: a desk-based tech FinTech profile must never get a
     retail case in the top 3; a frontline logistics profile must never get a tech case.
4. Run all tests: `python -m unittest discover -s tests -t .` and report results.

## Review TODO for the human owner
- Check the 5 tags with `"evidence": "inferred"` in `case_curation.json`.
- Align any new signal or action names with the rules owner before adding them to `domain_models.py`.

## Adding a new historical case (no code changes)
1. Append the narrative to `raw_case_study_narratives` in `database/ingaze_sandbox_dataset.json`
   (optional: a T0/T1 record with the same `case_name` in `database/ingaze_synthetic_analytics_snapshots.json`).
2. Draft the curation with the LLM (needs a key in `.env`, see `.env_template`):
   `python -m src.offline.case_curation_drafter` (`--dry-run` to preview). Quotes are verified verbatim;
   the model is re-prompted with the errors, and anything still invalid is dropped and listed in `draft_notes`.
3. Review the entry in `database/curation/case_curation.json` (`--list-drafts`), fix tags if needed, then
   `python -m src.offline.case_curation_drafter --approve CASE_12_...`.
4. Rebuild: `python -m src.offline.case_normalizer`. Unreviewed drafts are built with a warning and
   `curation_review_status: "llm_draft"` in `normalized_cases.json`.

Case count and valid research snippet numbers are read from the dataset; nothing is hardcoded to 11 / 1..10.
New enum values (sector, workforce, signal, action) still need `domain_models.py` + `case_matching.py`
(`DESK_BASED_WORKFORCES`, `FRONTLINE_WORKFORCES`, `ADJACENT_SECTORS`), aligned with the rules owner.
