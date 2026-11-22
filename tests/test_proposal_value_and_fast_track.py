"""Site-scoped comparisons, population-fit research, fast-track guardrails and ROI ranges."""

from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from src.main import (
    DEFAULT_DATA,
    load_analytics,
    load_graph,
    load_library,
    plan,
)
from src.offline.roi_estimator import _stated_amounts, estimate_roi
from src.pipeline.step2_root_cause_analysis import _word_scope

RETAIL_ONLY_SOURCES = {"friebel_2021", "dube_2019", "kesavan_2022", "friebel-heinz-zubanov-manager-attention"}


class ProposalValueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = json.loads(DEFAULT_DATA.read_text(encoding="utf-8-sig"))
        cls.graph = load_graph()
        cls.analytics = load_analytics()
        cls.library = load_library()
        cls.scenarios = {row["scenario_code"]: row for row in cls.dataset["company_scenarios_to_diagnose"]}

    def _plan(self, scenario):
        with patch("src.main._persist_stage_result", return_value=None):
            return plan(scenario, self.dataset, self.library, self.graph, self.analytics)

    def _scenario(self, prefix):
        return copy.deepcopy(next(row for code, row in self.scenarios.items() if code.startswith(prefix)))

    # --- Step 2: site scope survives "X (vs. Y)" comparisons -------------------
    def test_comparison_keeps_subject_sites_only_when_both_sides_are_named(self):
        scenario = {"headcount_and_footprint": "900 employees across 3 sites (Alpha, Beta, Gamma)"}
        both = _word_scope(scenario, "Rating fell to 3.1 in Alpha and Beta (vs. 4.2 in Gamma).")
        self.assertEqual(both["site"], "alpha+beta")
        one_side = _word_scope(scenario, "Variance across sites (Gamma at 4.3/5 vs.")
        self.assertIsNone(one_side["site"])
        whereas = _word_scope(scenario, "Alpha hires well, whereas Beta struggles.")
        self.assertIsNone(whereas["site"])

    def test_site_asymmetry_scopes_people_root_causes_to_struggling_sites(self):
        result, _ = self._plan(self._scenario("SCENARIO_A"))
        scoped = {row["rule"]: row["scope"]["site"] for row in result["diagnosed_root_causes"]}
        self.assertEqual(scoped.get("management_practice"), "berlin+milan")
        self.assertEqual(scoped.get("expectation_drift"), "berlin+milan")

    # --- Step 3: population-specific research ----------------------------------
    def test_retail_only_studies_are_not_cited_for_non_retail_clients(self):
        for code, scenario in self.scenarios.items():
            result, _ = self._plan(copy.deepcopy(scenario))
            cited = {row.get("source_id") or row.get("id") for row in result["supporting_research_snippets"]}
            self.assertFalse(cited & RETAIL_ONLY_SOURCES, code)

    # --- Step 4/5: fast track flips with the evidence ---------------------------
    def test_fast_apply_is_fast_tracked_only_with_direct_form_evidence(self):
        result, _ = self._plan(self._scenario("SCENARIO_B"))
        guards = " ".join(result["blocked_traps_and_guardrails"])
        self.assertIn("Fast-track", guards)
        pilot = next(row for row in result["phase_2_actions"] if row["rule"] == "application_friction")
        self.assertTrue(pilot.get("fast_track"))

        tweaked = self._scenario("SCENARIO_B")
        signals = tweaked["ingaze_platform_signals"]
        signals["recruiting_and_jds"] = signals["recruiting_and_jds"].replace(
            " because it requires desktop-style account registration and a 5-page CV upload", ""
        )
        result, _ = self._plan(tweaked)
        guards = " ".join(result["blocked_traps_and_guardrails"])
        self.assertIn("Defer fast-apply deployment", guards)
        self.assertFalse(any(row.get("fast_track") and row["rule"] == "application_friction"
                             for row in result["phase_2_actions"]))

    def test_advocacy_accelerates_for_healthy_culture_and_defers_with_blocker(self):
        result, _ = self._plan(self._scenario("SCENARIO_C"))
        guards = " ".join(result["blocked_traps_and_guardrails"])
        self.assertIn("Accelerate advocacy", guards)

        tweaked = self._scenario("SCENARIO_C")
        tweaked["ingaze_platform_signals"]["reputation_and_reviews"] += (
            " Recent clinic reviews report severe burnout and chronic understaffing."
        )
        result, _ = self._plan(tweaked)
        guards = " ".join(result["blocked_traps_and_guardrails"])
        self.assertNotIn("Accelerate advocacy", guards)

    def test_ceo_advocacy_request_stays_deferred_under_say_do_gap(self):
        result, _ = self._plan(self._scenario("SCENARIO_A"))
        guards = " ".join(result["blocked_traps_and_guardrails"])
        self.assertIn("Defer external advocacy", guards)
        self.assertFalse(any(row.get("fast_track") for row in result["phase_2_actions"]))

    # --- ROI ranges and pilot targets -------------------------------------------
    def test_roi_ranges_and_targets_are_grounded_in_client_and_precedents(self):
        for prefix in ("SCENARIO_A", "SCENARIO_B", "SCENARIO_C"):
            result, trace = self._plan(self._scenario(prefix))
            lines = result.get("expected_roi_estimates", [])
            self.assertTrue(lines, prefix)
            for line in lines:
                self.assertLessEqual(line["low"], line["high"])
                self.assertTrue(line["precedent_cases"])
            self.assertTrue(any("target_metric" in row for row in result["phase_2_actions"]), prefix)
            self.assertIn("Expected Value (CFO View)", trace["proposal_markdown"])

    def test_stated_amounts_are_annualized_from_their_period(self):
        observations = [{
            "signal": "agency_spend", "state": "present", "source_ref": "ctx#1",
            "text": "Operations is burning €190k/quarter on temporary agencies.",
            "quantities": [{"value": 190000.0, "unit": "EUR", "text": "€190k"}],
        }]
        found = _stated_amounts(observations, {"agency_spend"}, "EUR")
        self.assertEqual(found[0]["annual_value"], 760000.0)

    def test_no_precedent_delta_means_no_number(self):
        diagnosis = {"intake": {"observations": [], "measurements": [
            {"metric_path": "hiring_and_retention_kpis.estimated_annual_attrition_exposure_eur",
             "value": 500000, "peer_value": None, "source_ref": "telemetry"},
        ]}}
        roi = estimate_roi(diagnosis, {"matched_case_studies": []}, cases=[])
        self.assertEqual(roi["roi_lines"], [])
        self.assertTrue(roi["not_quantified"])


if __name__ == "__main__":
    unittest.main()
