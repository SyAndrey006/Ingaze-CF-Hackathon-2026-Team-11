import json
import unittest
from copy import deepcopy

from scripts.evaluate_historical_replay import replay
from src.reasoning.hr_intake import load_analytics
from src.reasoning.hr_knowledge_graph import load_graph
from recommendation_engine import DEFAULT_DATA, plan


SCOPE = {"cohort": "installation_technicians", "site": "western_depot", "tenure": "applicant", "window": "Q3"}


def fact(signal, source=None, **kwargs):
    source = source or signal
    return {
        "id": signal, "signal": signal, "quality": "verified", "state": "present",
        "source_ref": source, "origins": [source], "scope": SCOPE.copy(), **kwargs,
    }


class ExpandedReasoningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = load_graph()
        cls.dataset = json.loads(DEFAULT_DATA.read_text())

    def plan(self, rows, **other):
        scenario = {"scenario_code": "unseen-services-firm", "diagnostic_observations": rows, **other}
        return plan(scenario, self.dataset, graph=self.graph)

    def pilot_rules(self, rows):
        output, _ = self.plan(rows)
        return {item["rule"] for item in output["phase_2_actions"]}

    def test_same_hiring_delay_has_distinct_stage_recommendations(self):
        for observations, expected in (
            (["form_obstacle_verified", "application_abandonment", "mobile_exposure"], "application_friction"),
            (["handoff_delay_verified"], "recruiter_handoff"),
            (["qualified_supply_verified"], "qualified_applicant_supply"),
            (["approval_queue_verified"], "requisition_approval"),
            (["interview_capacity_verified"], "interview_capacity"),
        ):
            with self.subTest(stage=expected):
                self.assertEqual(self.pilot_rules([fact("hiring_delay"), *(fact(signal) for signal in observations)]), {expected})

    def test_unknown_stage_asks_for_stage_evidence_without_pilot(self):
        output, trace = self.plan([fact("hiring_delay")])
        self.assertEqual(output["phase_2_actions"], [])
        self.assertIn("stage_unknown", [item.get("decision") for item in output["phase_1_actions"]])
        self.assertTrue(all(row["status"] == "plausible" for row in trace["diagnostic_hypotheses"]))

    def test_reported_approval_issue_is_discovery_only(self):
        output, trace = self.plan(
            [fact("hiring_delay")],
            client_internal_context={"workflow": "Requisitions are waiting for approval."},
        )
        self.assertEqual(output["phase_2_actions"], [])
        self.assertIn("requisition_approval", [item["rule"] for item in output["phase_1_actions"]])
        self.assertTrue(any(item["rule"] == "requisition_approval" and item["decision"] == "deferred"
                            for item in trace["action_decisions"]))

    def test_shared_source_and_counterevidence_defer_new_pilots(self):
        self.assertEqual(self.pilot_rules([
            fact("hiring_delay", "workflow_log"), fact("approval_queue_verified", "workflow_log"),
        ]), set())
        output, trace = self.plan([
            fact("hiring_delay"), fact("qualified_supply_verified"), fact("qualified_supply_adequate"),
        ])
        self.assertEqual(output["phase_2_actions"], [])
        hypothesis = next(row for row in trace["diagnostic_hypotheses"] if row["rule"] == "qualified_applicant_supply")
        self.assertEqual(hypothesis["status"], "conflicted")
        self.assertIn("qualified_supply_adequate", hypothesis["counterevidence_ids"])

    def test_new_hiring_concepts_have_correct_metric_denominators(self):
        output, trace = self.plan([
            fact("offer_decline_rate", value=.3, unit="fraction", metric_path="hiring_and_retention_kpis.offer_decline_pct"),
            fact("offer_terms_mismatch_verified"),
        ])
        row = next(item for item in trace["diagnostic_observations"] if item["id"] == "offer_decline_rate")
        self.assertEqual((row["value"], row["unit"], row["denominator"]), (30.0, "%", "extended_offers"))
        self.assertEqual({item["rule"] for item in output["phase_2_actions"]}, {"offer_acceptance"})

    def test_postacceptance_loss_is_distinct_from_offer_declines(self):
        self.assertEqual(self.pilot_rules([fact("prestart_loss"), fact("prestart_gap_verified")]), {"prestart_withdrawal"})
        self.assertEqual(self.pilot_rules([fact("offer_decline_rate"), fact("prestart_gap_verified")]), set())

    def test_flexibility_requires_role_fit_and_exits_from_same_cohort(self):
        facts = [fact("voluntary_exit_increase"), fact("flexibility_barrier_verified"), fact("flexibility_feasible")]
        self.assertEqual(self.pilot_rules(facts), {"work_location_flexibility"})
        self.assertEqual(self.pilot_rules(facts[:2]), set())
        other_site = {"scope": {**SCOPE, "site": "different_depot"}}
        self.assertEqual(self.pilot_rules([*facts[:2], fact("flexibility_feasible", **other_site)]), set())
        self.assertEqual(self.pilot_rules([*facts, fact("flexibility_infeasible")]), set())

    def test_measurement_artifact_and_report_integrity_rules(self):
        self.assertEqual(self.pilot_rules([
            fact("local_reputation"), fact("review_sample_shift_verified"),
            fact("tracking_attribution_gap_verified"), fact("campaign_outcomes_unmeasured"),
        ]), {"review_sample_shift", "campaign_attribution_gap"})

    def test_catalog_rule_sources_are_declared(self):
        self.assertGreaterEqual(len(self.graph["rules"]), 26)
        for key, rule in self.graph["rules"].items():
            with self.subTest(rule=key):
                self.assertTrue(rule["sources"])
                self.assertTrue(all(self.graph["sources"][source]["limitation"] for source in rule["sources"]))

    def test_replay_excludes_held_out_companies_and_their_t1(self):
        analytics = load_analytics()
        cases = self.dataset["raw_case_study_narratives"][:3]
        dataset = {**self.dataset, "raw_case_study_narratives": cases}
        result = replay(dataset, analytics, self.graph)
        self.assertEqual(result["case_count"], 3)
        for row in result["results"]:
            self.assertNotIn(row["held_out_case"], row["precedents"])
        changed = deepcopy(analytics)
        for item in changed["cases"].values():
            item["t1_after_12_months"] = {}
        self.assertEqual(result, replay(dataset, changed, self.graph))


if __name__ == "__main__":
    unittest.main()
