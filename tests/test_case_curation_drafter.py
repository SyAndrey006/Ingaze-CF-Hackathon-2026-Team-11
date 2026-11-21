"""
Module: test_case_curation_drafter.py
Stage: Tests (LLM-assisted case curation maintenance)

Uses a fake StructuredLLMClient (no API key, no network). A reviewed case is held out
of the curation to simulate a newly added raw case.

Run: python -m unittest tests.test_case_curation_drafter -v
"""

from __future__ import annotations

import copy
import json
import unittest

from src.offline.case_curation_drafter import (
    CaseCurationDraft,
    approve,
    build_prompts,
    draft_case_entry,
    draft_missing_cases,
    next_case_id,
    uncurated_raw_cases,
)
from src.offline.case_normalizer import (
    DEFAULT_CURATION,
    DEFAULT_SANDBOX,
    DEFAULT_SNAPSHOTS,
    UnreviewedCurationWarning,
    build_cases_db,
)

HELD_OUT_INDEX = 2  # a reviewed case we pretend is new


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _as_draft(entry):
    keys = ("sector_category", "workforce_archetypes", "problem_signals", "healthy_signals", "steps", "snippets")
    return CaseCurationDraft.model_validate({k: entry[k] for k in keys})


class FakeLLM:
    """Returns the queued drafts in order (last one repeats) and records every call."""

    def __init__(self, *drafts):
        self.drafts = list(drafts)
        self.calls = []

    def generate_structured(self, system_prompt, user_prompt, response_model):
        self.calls.append({"system": system_prompt, "user": user_prompt, "model": response_model})
        return self.drafts[min(len(self.calls) - 1, len(self.drafts) - 1)]


class TestCaseCurationDrafter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshots = _load(DEFAULT_SNAPSHOTS)
        cls.full_curation = _load(DEFAULT_CURATION)
        # Restrict the sandbox to already-curated cases so these tests do not depend on
        # whether newly added raw cases have been drafted yet.
        curated = {e["case_name"] for e in cls.full_curation["cases"]}
        cls.sandbox = _load(DEFAULT_SANDBOX)
        cls.sandbox["raw_case_study_narratives"] = [
            c for c in cls.sandbox["raw_case_study_narratives"] if c["case_name"] in curated
        ]

    def setUp(self):
        self.curation = copy.deepcopy(self.full_curation)
        self.held_out = self.curation["cases"].pop(HELD_OUT_INDEX)
        self.raw_case = next(
            c for c in self.sandbox["raw_case_study_narratives"] if c["case_name"] == self.held_out["case_name"]
        )

    def test_detects_uncurated_case(self):
        todo = uncurated_raw_cases(self.sandbox, self.curation)
        self.assertEqual([c["case_name"] for c in todo], [self.held_out["case_name"]])
        self.assertEqual(uncurated_raw_cases(self.sandbox, self.full_curation), [])

    def test_valid_draft_is_appended_and_buildable_with_warning(self):
        llm = FakeLLM(_as_draft(self.held_out))
        new = draft_missing_cases(self.sandbox, self.curation, llm)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(len(new), 1)
        entry = new[0]
        self.assertEqual(entry["review_status"], "llm_draft")
        self.assertEqual(entry["case_name"], self.held_out["case_name"])
        self.assertNotIn(entry["case_id"], {e["case_id"] for e in self.curation["cases"][:-1]})
        with self.assertWarns(UnreviewedCurationWarning):
            db = build_cases_db(self.sandbox, self.snapshots, self.curation)
        self.assertEqual(len(db.cases), len(self.sandbox["raw_case_study_narratives"]))

    def test_retries_with_error_feedback(self):
        bad = copy.deepcopy(self.held_out)
        bad["problem_signals"][0]["quote"] = "a paraphrase that is not in the text"
        llm = FakeLLM(_as_draft(bad), _as_draft(self.held_out))
        entry = draft_case_entry(self.raw_case, self.sandbox, self.curation, llm)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("not verbatim", llm.calls[1]["user"])
        self.assertEqual(len(entry["problem_signals"]), len(self.held_out["problem_signals"]))

    def test_persistently_invalid_items_are_dropped_with_notes(self):
        bad = copy.deepcopy(self.held_out)
        bad["problem_signals"][0]["quote"] = "a paraphrase that is not in the text"
        bad["snippets"] = bad["snippets"] + [999]
        llm = FakeLLM(_as_draft(bad))
        entry = draft_case_entry(self.raw_case, self.sandbox, self.curation, llm, max_attempts=2)
        self.assertEqual(len(llm.calls), 2)
        self.assertEqual(len(entry["problem_signals"]), len(self.held_out["problem_signals"]) - 1)
        self.assertNotIn(999, entry["snippets"])
        notes = " ".join(entry["draft_notes"])
        self.assertIn("quote not verbatim", notes)
        self.assertIn("999", notes)

    def test_step_order_renumbered_and_empty_snippets_retried(self):
        sloppy = copy.deepcopy(self.held_out)
        for s in sloppy["steps"]:
            s["step_order"] = s["phase_bucket"]  # typical model mistake
        sloppy["snippets"] = []
        llm = FakeLLM(_as_draft(sloppy))
        entry = draft_case_entry(self.raw_case, self.sandbox, self.curation, llm, max_attempts=2)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("snippets is empty", llm.calls[1]["user"])
        self.assertEqual([s["step_order"] for s in entry["steps"]], list(range(1, len(entry["steps"]) + 1)))
        self.assertTrue(any("needs review" in n for n in entry["draft_notes"]))

    def test_prompt_never_contains_active_scenarios(self):
        system, user = build_prompts(self.raw_case, self.sandbox, self.curation)
        for scenario in self.sandbox["company_scenarios_to_diagnose"]:
            first_word = scenario["company_name"].split()[0]
            self.assertNotIn(first_word, system + user)
        self.assertIn(self.raw_case["initial_challenge"], user)
        self.assertNotIn('"llm_draft"', user)  # only reviewed entries serve as examples

    def test_approve_marks_reviewed(self):
        llm = FakeLLM(_as_draft(self.held_out))
        entry = draft_missing_cases(self.sandbox, self.curation, llm)[0]
        self.assertEqual(approve(self.curation, [entry["case_id"], "CASE_99_NOPE"]), ["CASE_99_NOPE"])
        self.assertEqual(entry["review_status"], "reviewed")
        self.assertNotIn("draft_notes", entry)

    def test_next_case_id(self):
        ids = ["CASE_01_A", "CASE_11_B"]
        self.assertEqual(next_case_id("New Co (Some Sector)", ids), "CASE_12_NEW_CO")
        self.assertEqual(next_case_id("Ünïcode Name", []), "CASE_01_UNICODE_NAME")


if __name__ == "__main__":
    unittest.main()
