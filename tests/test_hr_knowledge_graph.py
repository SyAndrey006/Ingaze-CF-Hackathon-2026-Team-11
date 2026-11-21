import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.pipeline.step2_root_cause_analysis import diagnose, graph_export, load_graph
from recommendation_engine import DEFAULT_DATA, plan


class KnowledgeGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = load_graph()
        self.scope = {"cohort": "entry_level_engineering", "site": "north",
                      "tenure": "new_hire", "window": "2026-Q3"}

    def observation(self, key, signal, origins, *, quality="verified", state="present", **scope):
        return {
            "id": key, "signal": signal, "state": state, "quality": quality,
            "source_ref": f"fixture:{key}", "origins": origins, "scope": {**self.scope, **scope},
        }

    def results(self, observations, rule):
        return [result for result in diagnose(self.graph, observations) if result["rule"] == rule]

    def test_compatible_independent_signals_can_support_a_hypothesis(self):
        rows = [
            self.observation("promise", "documented_broken_promise", ["interviews"]),
            self.observation("exits", "early_attrition", ["hris"]),
        ]
        result, = self.results(rows, "expectation_drift")
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["evidence_ids"], ["exits", "promise"])

    def test_aliases_in_one_family_contribute_once(self):
        rows = [
            self.observation("promise", "documented_broken_promise", ["interviews"]),
            self.observation("index", "brand_misalignment", ["reviews"]),
            self.observation("star-gap", "expectation_gap", ["reviews"]),
        ]
        result, = self.results(rows, "expectation_drift")
        self.assertEqual(result["status"], "plausible")
        self.assertEqual(len(result["evidence_ids"]), 1)
        self.assertEqual(result["unmatched_families"], ["employee_exits"])
        self.assertEqual(result["origin_components"]["index"], result["origin_components"]["star-gap"])

    def test_overlapping_lineage_across_families_is_one_source(self):
        rows = [
            self.observation("promise", "documented_broken_promise", ["raw-survey"]),
            self.observation("exits", "early_attrition", ["exit-summary"]),
            self.observation("link", "manager_support", ["raw-survey", "exit-summary"]),
        ]
        result, = self.results(rows, "expectation_drift")
        self.assertEqual(result["status"], "plausible")
        self.assertEqual(len(result["evidence_ids"]), 1)
        self.assertEqual(result["origin_components"]["promise"], result["origin_components"]["exits"])

    def test_matching_can_pick_an_alternative_independent_origin(self):
        rows = [
            self.observation("a-promise", "documented_broken_promise", ["shared"]),
            self.observation("b-promise", "documented_broken_promise", ["interviews"]),
            self.observation("exits", "early_attrition", ["shared"]),
        ]
        result, = self.results(rows, "expectation_drift")
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["evidence_ids"], ["b-promise", "exits"])

    def test_sites_and_windows_are_not_combined(self):
        promise = self.observation("promise", "documented_broken_promise", ["interviews"])
        for different_scope in ({"site": "south"}, {"window": "2025-Q3"}, {"cohort": "all"}):
            with self.subTest(scope=different_scope):
                exits = self.observation("exits", "early_attrition", ["hris"], **different_scope)
                results = self.results([promise, exits], "expectation_drift")
                self.assertEqual(len(results), 2)
                self.assertTrue(all(row["status"] == "plausible" for row in results))

    def test_reported_direct_observation_and_unknown_scope_stay_plausible(self):
        exits = self.observation("exits", "early_attrition", ["hris"])
        for promise in (
            self.observation("promise", "documented_broken_promise", ["interviews"], quality="reported"),
            self.observation("promise", "documented_broken_promise", ["interviews"], window=None),
        ):
            with self.subTest(promise=promise):
                self.assertFalse(any(row["status"] == "supported"
                                     for row in self.results([promise, exits], "expectation_drift")))

    def test_unverified_observation_cannot_activate_a_pattern(self):
        rows = [self.observation("upload", "form_obstacle_verified", ["rumor"], quality="unverified")]
        self.assertEqual(diagnose(self.graph, rows), [])

    def test_reported_counterevidence_defers_overlapping_advocacy(self):
        rows = [
            self.observation("volunteers", "volunteers_verified", ["consent-log"]),
            self.observation("climate", "culture_ready", ["pulse"]),
            self.observation("burnout", "burnout", ["interviews"], quality="reported", site="all"),
        ]
        result, = self.results(rows, "advocacy_pilot")
        self.assertEqual(result["status"], "conflicted")
        self.assertEqual(result["counterevidence_ids"], ["burnout"])

    def test_unrelated_cohort_does_not_block_scoped_advocacy(self):
        rows = [
            self.observation("volunteers", "volunteers_verified", ["consent-log"]),
            self.observation("climate", "culture_ready", ["pulse"]),
            self.observation("burnout", "burnout", ["interviews"], cohort="warehouse"),
        ]
        result, = self.results(rows, "advocacy_pilot")
        self.assertEqual(result["status"], "supported")

    def test_graph_pack_adds_a_new_pattern_without_python_changes(self):
        rule = {
            "label": "A trial rule for distinct sector needs",
            "kind": "operational",
            "requires": [["new_support_signal"], ["early_attrition"]],
            "direct": 0,
            "sources": [],
            "diagnostic": "Check the workflow.",
            "pilot": "Pilot a workflow change.",
            "scale_gate": "Expand after attendance improves.",
        }
        custom = {"version": 1, "signals": {
            "new_support_signal": {"family": "new_family", "role": "direct", "meaning": "Verified signal"},
        }, "rules": {"new_rule": rule}}
        with tempfile.TemporaryDirectory() as directory:
            pack = Path(directory) / "pack.json"
            pack.write_text(json.dumps(custom))
            graph = load_graph([pack])
        observations = [
            self.observation("direct", "new_support_signal", ["operations"]),
            self.observation("exits", "early_attrition", ["hris"]),
        ]
        result = next(result for result in diagnose(graph, observations) if result["rule"] == "new_rule")
        self.assertEqual(result["status"], "supported")
        exported = graph_export(graph)
        node_ids = {node["id"] for node in exported["nodes"]}
        self.assertTrue(all(edge["from"] in node_ids and edge["to"] in node_ids for edge in exported["edges"]))

    def test_scoped_planner_chooses_location_of_funnel_bottleneck(self):
        dataset = json.loads(DEFAULT_DATA.read_text())
        scenario = {"scenario_code": "new_company", "profile_tags": ["freight"]}
        before = [
            self.observation("obstacle", "form_obstacle_verified", ["device-audit"]),
            self.observation("abandon", "application_abandonment", ["ats"]),
            self.observation("mobile", "mobile_exposure", ["traffic"]),
        ]
        after = [
            self.observation("completes", "form_completes", ["ats"]),
            self.observation("delay", "handoff_delay_verified", ["hand-off-log"]),
            self.observation("slow", "hiring_delay", ["requisition-records"]),
        ]
        original, _ = plan({**scenario, "diagnostic_observations": before}, dataset, graph=self.graph)
        revised, _ = plan({**scenario, "diagnostic_observations": after}, dataset, graph=self.graph)
        self.assertEqual([row["rule"] for row in original["phase_2_actions"]], ["application_friction"])
        self.assertEqual([row["rule"] for row in revised["phase_2_actions"]], ["recruiter_handoff"])

    def test_cli_writes_typed_graph_and_trace_for_all_sandbox_scenarios(self):
        root = DEFAULT_DATA.parent.parent
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("submission.json", "trace.json", "graph.json")]
            subprocess.run(
                [sys.executable, "-B", "recommendation_engine.py", "--out", str(paths[0]),
                 "--trace-out", str(paths[1]), "--graph-out", str(paths[2])],
                cwd=root, check=True, capture_output=True,
            )
            submission, trace, graph = [
                json.loads(path.read_text(encoding="utf-8")) for path in paths
            ]
            self.assertEqual(len(submission["scenarios"]), 3)
            self.assertEqual(len(trace), 3)
            self.assertTrue(all(entry["diagnostic_hypotheses"] for entry in trace))
            self.assertTrue(graph["edges"])


if __name__ == "__main__":
    unittest.main()
