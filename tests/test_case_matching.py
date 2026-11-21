"""
Module: test_case_matching.py
Stage: Tests (case store helpers for Step 3)

Synthetic, company-agnostic client profiles against the real normalized case store.
Also covers `load_normalized_cases` and `build_normalized_cases` delegation.

Run: python -m unittest tests.test_case_matching -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.offline.case_matching import (
    candidate_actions_from_cases,
    load_scoring_weights,
    rank_top_cases,
)
from src.offline.case_normalizer import DEFAULT_OUTPUT, DEFAULT_SANDBOX, DEFAULT_SNAPSHOTS
from src.offline.database_loader import load_normalized_cases
from src.offline.normalize_databases import build_normalized_cases
from src.pipeline.step2_root_cause_analysis import load_graph
from src.pipeline.step3_conditions_scoring import load_library, score_diagnostic_candidates
from src.schemas.domain_models import (
    ActionCategory,
    NormalizedCasesDB,
    SectorCategory,
    SignalCode,
    WorkforceArchetype,
)
from src.schemas.pipeline_models import ExtractedSignal, NormalizedClientInput

RULES_PATH = DEFAULT_OUTPUT.parent / "normalized_rules.json"

TECH_SECTORS = {SectorCategory.B2B_TECH_SAAS, SectorCategory.FINTECH_PAYMENTS}

# Desk-based FinTech profile, deliberately salted with funnel signals that retail cases also carry.
DESK_FINTECH = dict(
    client_signals=[
        SignalCode.LOW_INBOUND_QUALIFIED_APPLICANTS,
        SignalCode.GENERIC_BOILERPLATE_JDS,
        SignalCode.HIGH_APPLICATION_DROPOFF,
        SignalCode.MOBILE_PORTAL_FRICTION,
        SignalCode.LOW_CORPORATE_SOCIAL_ENGAGEMENT,
    ],
    workforce=[WorkforceArchetype.DESK_BASED_TECH_SPECIALIST],
    sector=SectorCategory.FINTECH_PAYMENTS,
)

# Frontline logistics profile, deliberately salted with signals that tech cases also carry.
FRONTLINE_LOGISTICS = dict(
    client_signals=[
        SignalCode.HIGH_APPLICATION_DROPOFF,
        SignalCode.HIGH_TIME_TO_HIRE,
        SignalCode.WEAK_MIDDLE_MANAGEMENT,
        SignalCode.CAREER_PATH_OPACITY,
        SignalCode.SAY_DO_GAP,
        SignalCode.HIGH_FINANCIAL_TURNOVER_RISK,
    ],
    workforce=[WorkforceArchetype.DESKLESS_FRONTLINE_LOGISTICS],
    sector=SectorCategory.LOGISTICS_FREIGHT,
)


class TestCaseMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = load_normalized_cases(DEFAULT_OUTPUT)
        cls.weights = load_scoring_weights(RULES_PATH)
        cls.by_id = {c.case_id: c for c in cls.db.cases}

    def _is_retail(self, case_id):
        c = self.by_id[case_id]
        return (
            c.sector_category == SectorCategory.RETAIL_OMNICHANNEL
            or WorkforceArchetype.DESKLESS_FRONTLINE_RETAIL in c.workforce_archetypes
        )

    def _is_tech(self, case_id):
        c = self.by_id[case_id]
        return (
            c.sector_category in TECH_SECTORS
            or WorkforceArchetype.DESK_BASED_TECH_SPECIALIST in c.workforce_archetypes
        )

    def test_desk_fintech_never_gets_retail_case(self):
        top = rank_top_cases(self.db, weights=self.weights, **DESK_FINTECH)
        self.assertEqual(len(top), 3)
        for r in top:
            self.assertFalse(self._is_retail(r.match.case_id), r.match.case_id)

    def test_frontline_logistics_never_gets_tech_case(self):
        top = rank_top_cases(self.db, weights=self.weights, **FRONTLINE_LOGISTICS)
        self.assertTrue(top)
        for r in top:
            self.assertFalse(self._is_tech(r.match.case_id), r.match.case_id)

    def test_ranking_output_contract(self):
        planned = [ActionCategory.CANDIDATE_PERSONA_CALIBRATION, ActionCategory.PERSONA_ALIGNED_JDS]
        top = rank_top_cases(self.db, planned_actions=planned, weights=self.weights, **FRONTLINE_LOGISTICS)
        scores = [r.match.similarity_score for r in top]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for r in top:
            self.assertGreaterEqual(r.match.similarity_score, 0.0)
            self.assertLessEqual(r.match.similarity_score, 1.0)
            self.assertLessEqual(len(r.match.quantified_roi_highlights), 3)
            self.assertIn("root causes match", r.reason)
            self.assertIn("planned actions have precedent", r.reason)
            self.assertTrue(set(r.match.matched_problem_tags) <= set(FRONTLINE_LOGISTICS["client_signals"]))

    def test_precedent_must_share_a_root_cause(self):
        # Same sector + workforce alone must not make a case a precedent.
        for profile in (DESK_FINTECH, FRONTLINE_LOGISTICS):
            for r in rank_top_cases(self.db, weights=self.weights, k=50, **profile):
                self.assertTrue(r.match.matched_problem_tags, r.match.case_id)
        no_overlap = dict(FRONTLINE_LOGISTICS, client_signals=[SignalCode.ACTIVE_ORGANIC_AMBASSADORS_PRESENT])
        self.assertEqual(rank_top_cases(self.db, weights=self.weights, **no_overlap), [])
        self.assertTrue(rank_top_cases(self.db, weights=self.weights, min_shared_root_causes=0, **no_overlap))

    def test_ranking_is_deterministic(self):
        a = rank_top_cases(self.db, weights=self.weights, **DESK_FINTECH)
        b = rank_top_cases(self.db, weights=self.weights, **DESK_FINTECH)
        self.assertEqual([r.match for r in a], [r.match for r in b])

    def test_candidate_actions_respect_signal_and_workforce_overlap(self):
        actions = candidate_actions_from_cases(self.db, **FRONTLINE_LOGISTICS)
        self.assertTrue(actions)
        client = set(FRONTLINE_LOGISTICS["client_signals"])
        wf = set(FRONTLINE_LOGISTICS["workforce"])
        for action, case_id, phase in actions:
            case = self.by_id[case_id]
            self.assertIsInstance(action, ActionCategory)
            self.assertTrue(client & set(case.canonical_problem_tags))
            self.assertTrue(wf & set(case.workforce_archetypes))
            self.assertIn(int(phase), (1, 2, 3))
        self.assertEqual(len(actions), len(set((a, c) for a, c, _ in actions)))

    def test_candidate_actions_never_cross_workforce(self):
        for action, case_id, _ in candidate_actions_from_cases(self.db, **DESK_FINTECH):
            self.assertFalse(self._is_retail(case_id), (action, case_id))


class TestCaseStoreLoading(unittest.TestCase):
    def test_load_normalized_cases_ok(self):
        db = load_normalized_cases(DEFAULT_OUTPUT)
        with DEFAULT_SANDBOX.open(encoding="utf-8") as fh:
            n_raw = len(json.load(fh)["raw_case_study_narratives"])
        self.assertEqual(len(db.cases), n_raw)

    def test_load_rejects_empty_and_duplicates(self):
        db = load_normalized_cases(DEFAULT_OUTPUT)
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.json"
            empty.write_text(NormalizedCasesDB().model_dump_json(), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_normalized_cases(empty)

            dup = Path(tmp) / "dup.json"
            dup_db = NormalizedCasesDB(cases=[db.cases[0], db.cases[0]])
            dup.write_text(dup_db.model_dump_json(), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_normalized_cases(dup)

            with self.assertRaises(FileNotFoundError):
                load_normalized_cases(Path(tmp) / "missing.json")

    def test_build_normalized_cases_matches_written_store(self):
        with DEFAULT_SANDBOX.open(encoding="utf-8") as fh:
            sandbox = json.load(fh)
        with DEFAULT_SNAPSHOTS.open(encoding="utf-8") as fh:
            snapshots = json.load(fh)
        built = build_normalized_cases(sandbox, snapshots, llm_client=None)
        stored = load_normalized_cases(DEFAULT_OUTPUT)
        self.assertEqual(built.model_dump(), stored.model_dump())

    def test_step3_consumes_normalized_case_store(self):
        client = NormalizedClientInput(
            scenario_code="STEP3_CASE_STORE_TEST",
            company_name="Test FinTech",
            industry_raw="FinTech",
            sector_category=SectorCategory.FINTECH_PAYMENTS,
            workforce_archetypes=[WorkforceArchetype.DESK_BASED_TECH_SPECIALIST],
            canonical_signals=[
                ExtractedSignal(
                    signal_code=SignalCode.MOBILE_PORTAL_FRICTION,
                    evidence_quote="Applicants abandon the mobile application form.",
                    source_stream="outside_in_platform",
                ),
                ExtractedSignal(
                    signal_code=SignalCode.GENERIC_BOILERPLATE_JDS,
                    evidence_quote="Engineering job descriptions use generic boilerplate.",
                    source_stream="outside_in_platform",
                ),
                ExtractedSignal(
                    signal_code=SignalCode.LOW_INBOUND_QUALIFIED_APPLICANTS,
                    evidence_quote="Qualified applicant volume is low.",
                    source_stream="inside_out_client",
                ),
            ],
        )
        diagnosis = {
            "scenario_code": client.scenario_code,
            "profile": [],
            "intake": {"observations": [], "snapshot": {}},
            "diagnostic_hypotheses": [],
            "prioritized_hypotheses": [],
        }
        dataset = json.loads(DEFAULT_SANDBOX.read_text(encoding="utf-8"))
        graph = load_graph()
        scored = score_diagnostic_candidates(
            diagnosis,
            dataset,
            load_library(),
            graph,
            {"active": {}, "cases": {}},
            normalized_client_input=client.model_dump(mode="json"),
        )
        self.assertEqual(len(scored["normalized_case_matches"]), 3)
        self.assertTrue(scored["case_informed_action_candidates"])
        case_by_id = {case.case_id: case for case in load_normalized_cases(DEFAULT_OUTPUT).cases}
        for match in scored["normalized_case_matches"]:
            case = case_by_id[match["case_id"]]
            self.assertFalse(
                case.sector_category == SectorCategory.RETAIL_OMNICHANNEL
                or WorkforceArchetype.DESKLESS_FRONTLINE_RETAIL in case.workforce_archetypes
            )


if __name__ == "__main__":
    unittest.main()
