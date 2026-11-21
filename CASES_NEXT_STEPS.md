# Historical case store maintenance

The reviewed case store currently contains 21 normalized cases. Human-reviewed
curation lives in `database/curation/case_curation.json`; the deterministic
builder and checker are in `src/offline/case_normalizer.py`.

```powershell
# Verify curation and the normalized output without writing files
python -m src.offline.case_normalizer --check

# Rebuild the normalized case store after curation changes
python -m src.offline.case_normalizer

# Run case store, matcher, and integration coverage
python -m unittest tests.test_case_normalizer tests.test_case_matching -v
```

The online planner uses `database/knowledge/hr_knowledge_graph.json` for its
deterministic policy rules. `database/normalized/normalized_rules.json` retains
the shared case-scoring weights; it is not a second source of diagnosis or
guardrail rules.

## Add a historical case

1. Add the source narrative to `raw_case_study_narratives` in
   `database/ingaze_sandbox_dataset.json`. Add matching T0/T1 analytics to
   `database/ingaze_synthetic_analytics_snapshots.json` when available.
2. Draft curation with `python -m src.offline.case_curation_drafter --dry-run`.
   Drafting may use the configured LLM, but the builder itself is deterministic.
3. Review the source quotes, tags, actions, and research references in
   `database/curation/case_curation.json`; approve the draft with
   `python -m src.offline.case_curation_drafter --approve CASE_ID`.
4. Run the case-store checker and test commands above. Do not use historical
   T1 outcomes to change live ranking or present them as forecasts.
