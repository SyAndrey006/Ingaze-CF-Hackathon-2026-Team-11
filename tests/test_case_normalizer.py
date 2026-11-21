"""
Module: test_case_normalizer.py
Stage: Tests (Offline case store)

Checks that the curated case mapping is verbatim-grounded, schema-valid and complete,
and that the written normalized_cases.json round-trips through NormalizedCasesDB.

Run: python -m unittest tests.test_case_normalizer -v
"""

from __future__ import annotations

import copy
import json
import unittest

from src.offline.case_normalizer import (
    DEFAULT_CURATION,
    DEFAULT_OUTPUT,
    DEFAULT_SANDBOX,
    DEFAULT_SNAPSHOTS,
    UnreviewedCurationWarning,
    build_cases_db,
    research_snippet_nos,
    verify_curation,
)
from src.schemas.domain_models import NormalizedCasesDB, SignalCode, WorkforceArchetype


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestCaseNormalizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sandbox = _load(DEFAULT_SANDBOX)
        cls.snapshots = _load(DEFAULT_SNAPSHOTS)
        cls.curation = _load(DEFAULT_CURATION)
        cls.db = build_cases_db(cls.sandbox, cls.snapshots, cls.curation)

    def test_curation_has_zero_errors(self):
        errors = verify_curation(self.curation, self.sandbox["raw_case_study_narratives"])
        self.assertEqual(errors, [], "\n".join(errors))

    def test_one_unique_case_per_raw_narrative(self):
        n_raw = len(self.sandbox["raw_case_study_narratives"])
        self.assertEqual(len(self.db.cases), n_raw)
        self.assertEqual(len({c.case_id for c in self.db.cases}), n_raw)

    def test_fabricated_quote_is_rejected(self):
        broken = copy.deepcopy(self.curation)
        broken["cases"][0]["problem_signals"][0]["quote"] = "this sentence does not exist in the case"
        errors = verify_curation(broken, self.sandbox["raw_case_study_narratives"])
        self.assertTrue(any("not verbatim" in e for e in errors))

    def test_no_active_scenario_names_leak(self):
        dumped = self.db.model_dump_json()
        for scenario in self.sandbox["company_scenarios_to_diagnose"]:
            first_word = scenario["company_name"].split()[0]
            self.assertNotIn(first_word, dumped, f"Scenario name leaked: {first_word}")

    def test_every_case_has_steps_and_snapshot_cases_have_roi(self):
        with_snapshot = {s["case_name"] for s in self.snapshots.get("case_study_analytics_snapshots", [])}
        for case in self.db.cases:
            self.assertTrue(case.intervention_steps, case.case_id)
            if case.case_name in with_snapshot:
                self.assertTrue(case.quantified_roi_deltas, case.case_id)
                self.assertIsNotNone(case.t0_snapshot, case.case_id)
                self.assertIsNotNone(case.t1_snapshot, case.case_id)

    def test_snippet_range_comes_from_dataset(self):
        valid = research_snippet_nos(self.sandbox)
        broken = copy.deepcopy(self.curation)
        broken["cases"][0]["snippets"] = [max(valid) + 1]
        errors = verify_curation(broken, self.sandbox["raw_case_study_narratives"], valid_snippet_nos=valid)
        self.assertTrue(any("does not exist" in e for e in errors))
        # A dataset with more snippets accepts the higher number.
        errors = verify_curation(
            broken, self.sandbox["raw_case_study_narratives"], valid_snippet_nos=valid | {max(valid) + 1}
        )
        self.assertEqual(errors, [])

    def test_review_status_required(self):
        broken = copy.deepcopy(self.curation)
        del broken["cases"][0]["review_status"]
        errors = verify_curation(broken, self.sandbox["raw_case_study_narratives"])
        self.assertTrue(any("review_status" in e for e in errors))

    def test_llm_draft_is_built_with_warning_and_flag(self):
        drafted = copy.deepcopy(self.curation)
        for entry in drafted["cases"]:
            entry["review_status"] = "reviewed"
        drafted["cases"][0]["review_status"] = "llm_draft"
        with self.assertWarns(UnreviewedCurationWarning):
            db = build_cases_db(self.sandbox, self.snapshots, drafted)
        self.assertEqual(db.cases[0].curation_review_status, "llm_draft")
        self.assertIn("1 unreviewed LLM drafts", db.source_dataset_version)
        self.assertTrue(all(c.curation_review_status == "reviewed" for c in db.cases[1:]))

    def test_advocacy_sequencing_precedents(self):
        """Crisis case defers advocacy to phase 3; healthy-culture case starts it in phase 1."""
        by_id = {c.case_id: c for c in self.db.cases}
        crisis = by_id["CASE_05_ALFA"]
        healthy = by_id["CASE_02_SOLARIS"]
        self.assertIn(SignalCode.SAY_DO_GAP, crisis.canonical_problem_tags)
        self.assertIn(SignalCode.STRONG_INTERNAL_CULTURE_HEALTHY, healthy.healthy_starting_conditions)
        adv = "AMBASSADOR_SELECTION_ENABLEMENT"
        self.assertEqual(min(s.phase_bucket for s in crisis.intervention_steps if s.action_category.value == adv), 3)
        self.assertEqual(min(s.phase_bucket for s in healthy.intervention_steps if s.action_category.value == adv), 1)

    def test_frontline_cases_never_use_linkedin_storytelling(self):
        frontline = {WorkforceArchetype.DESKLESS_FRONTLINE_LOGISTICS, WorkforceArchetype.DESKLESS_FRONTLINE_RETAIL}
        for case in self.db.cases:
            if frontline & set(case.workforce_archetypes):
                cats = {s.action_category.value for s in case.intervention_steps}
                self.assertNotIn("TECHNICAL_LINKEDIN_STORYTELLING", cats, case.case_id)

    def test_written_json_validates(self):
        if not DEFAULT_OUTPUT.exists():
            self.skipTest("run `python -m src.offline.case_normalizer` first")
        db = NormalizedCasesDB.model_validate_json(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(len(db.cases), len(self.sandbox["raw_case_study_narratives"]))


if __name__ == "__main__":
    unittest.main()
