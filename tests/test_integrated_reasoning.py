import json
import unittest
from copy import deepcopy

from src.pipeline.step2_root_cause_analysis import (
    diagnose, load_analytics, load_graph, normalize_intake, normalize_narrative, normalize_reviewed,
)
from src.pipeline.messy_intake import adapt_messy_intake
from src.pipeline.step4_guardrail_check import evaluate_guardrails
from recommendation_engine import DEFAULT_DATA, case_matches, plan


class IntegratedReasoningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = json.loads(DEFAULT_DATA.read_text())
        cls.analytics = load_analytics()
        cls.graph = load_graph()
        cls.scenarios = cls.dataset["company_scenarios_to_diagnose"]

    def run_plan(self, scenario):
        return plan(scenario, self.dataset, graph=self.graph, analytics=self.analytics)

    def fact(self, id_, signal, source, **extra):
        row = {
            "id": id_, "signal": signal, "quality": "verified", "state": "present",
            "source_ref": source, "origins": [source],
            "scope": {"cohort": "field_applicants", "site": "north", "tenure": "applicant", "window": "Q3"},
        }
        return {**row, **extra}

    def test_official_defaults_use_graph_for_three_phases(self):
        phase_2_rules = []
        for scenario in self.scenarios:
            output, trace = self.run_plan(scenario)
            self.assertTrue(trace["normalized_measurements"])
            self.assertTrue(trace["diagnostic_hypotheses"])
            for phase in (1, 2, 3):
                self.assertTrue(output[f"phase_{phase}_actions"])
            self.assertEqual(len(output["matched_case_studies"]), 3)
            self.assertTrue(all(pilot["decision"] == "conditional" for pilot in output["phase_2_actions"]))
            phase_2_rules.append({action["rule"] for action in output["phase_2_actions"]})
        self.assertIn("expectation_drift", phase_2_rules[0])
        self.assertNotIn("advocacy_pilot", phase_2_rules[0])
        self.assertIn("application_friction", phase_2_rules[1])
        self.assertIn("feedback_coverage", phase_2_rules[2])

    def test_metric_units_denominators_and_sources(self):
        intake = normalize_intake(self.scenarios[1], self.graph, self.analytics)
        values = {row["metric_path"]: row for row in intake["measurements"]}
        dropoff = values["career_portal_and_funnel.application_form_dropoff_pct"]
        conversion = values["career_portal_and_funnel.applicant_conversion_rate_pct"]
        self.assertEqual((dropoff["value"], dropoff["unit"], dropoff["denominator"]), (63, "%", "application_starts"))
        self.assertEqual(conversion["denominator"], "portal_visits")
        self.assertEqual(dropoff["peer_value"], 41.2)
        self.assertTrue(dropoff["source_ref"].startswith("telemetry:"))
        cloud = normalize_intake(self.scenarios[0], self.graph, self.analytics)
        attrition = next(row for row in cloud["measurements"] if "six_month_new_hire" in row["metric_path"])
        self.assertEqual(attrition["measurement_horizon"], "6_months")
        self.assertEqual(attrition["scope"]["site"], "berlin+milan")

    def test_fraction_values_and_dated_windows_are_normalized(self):
        value = normalize_reviewed(self.fact(
            "dropoff", "application_abandonment", "ats", value=.35, unit="fraction",
            metric_path="career_portal_and_funnel.application_form_dropoff_pct",
            period_start="2026-07-01", period_end="2026-09-30",
        ))
        self.assertEqual((value["value"], value["unit"]), (35, "%"))
        self.assertEqual(value["scope"]["window"], "2026-07-01/2026-09-30")
        with self.assertRaisesRegex(ValueError, "invalid value or unit"):
            normalize_reviewed({**value, "value": 300, "unit": "%"})

    def test_provenance_detects_shared_population_and_duplicate_source_reference(self):
        for metadata in ({"population_ids": ["sample_44"]}, {"dependency_ids": ["shared_derived_measure"]}):
            rows = [
                self.fact("claim", "documented_broken_promise", "interviews", **metadata),
                self.fact("exits", "early_attrition", "hris", **metadata),
            ]
            drift = next(row for row in diagnose(self.graph, rows) if row["rule"] == "expectation_drift")
            self.assertEqual(drift["status"], "plausible")
            self.assertTrue(drift["dependent_families"])
            self.assertFalse(drift["missing_families"])
        rows = [self.fact("claim", "documented_broken_promise", "same_report"),
                self.fact("exits", "early_attrition", "same_report", origins=["copied_into_pipeline"])]
        drift = next(row for row in diagnose(self.graph, rows) if row["rule"] == "expectation_drift")
        self.assertEqual(drift["status"], "plausible")

    def test_narrative_negation_is_counterevidence_not_support(self):
        scenario = {"scenario_code": "unknown-company",
                    "client_internal_context": {"workload": "There is no severe burnout."}}
        _, trace = self.run_plan(scenario)
        self.assertTrue(any(row["signal"] == "burnout" and row["state"] == "absent"
                            for row in trace["diagnostic_observations"]))
        self.assertNotIn("burnout", trace["advocacy_blockers"])

    def test_competing_form_evidence_prevents_form_pilot_for_unseen_company(self):
        rows = [
            self.fact("obstacle", "form_obstacle_verified", "audit"),
            self.fact("dropoff", "application_abandonment", "ats"),
            self.fact("mobile", "mobile_exposure", "device_report"),
            self.fact("completed", "form_completes", "followup"),
            self.fact("handoff", "handoff_delay_verified", "recruiter_queue"),
            self.fact("slow", "hiring_delay", "requisition_log"),
        ]
        scenario = {"scenario_code": "new-aboveground-freight", "profile_tags": ["freight"],
                    "diagnostic_observations": rows}
        output, trace = self.run_plan(scenario)
        self.assertEqual([pilot["rule"] for pilot in output["phase_2_actions"]], ["recruiter_handoff"])
        conflict = next(row for row in trace["diagnostic_hypotheses"] if row["rule"] == "application_friction")
        self.assertEqual(conflict["status"], "conflicted")
        self.assertIn("completed", conflict["counterevidence_ids"])

    def test_protected_scope_prevents_even_supported_pilot(self):
        rows = [self.fact("handoff", "handoff_delay_verified", "queue"),
                self.fact("slow", "hiring_delay", "requisition_log")]
        for row in rows:
            row["scope"]["site"] = "north+south"
        scenario = {"scenario_code": "new-company", "diagnostic_observations": rows,
                    "protected_scopes": [{"scope": {"site": "north"}, "rules": ["recruiter_handoff"]}]}
        output, trace = self.run_plan(scenario)
        self.assertEqual(output["phase_2_actions"], [])
        self.assertIn("protected scope", trace["action_decisions"][0]["reason"])

    def test_prohibited_requests_do_not_become_interventions(self):
        scenario = deepcopy(self.scenarios[1])
        field = "leadership_perceptions_and_requests"
        scenario["client_internal_context"][field] += " Also copy the retail store weekend shift rotation."
        output, _ = self.run_plan(scenario)
        guards = " ".join(output["blocked_traps_and_guardrails"])
        self.assertIn("Exclude technical LinkedIn storytelling", guards)
        self.assertIn("Exclude retail store shift rotation", guards)
        policies = " ".join(pilot["action"] for pilot in output["phase_2_actions"])
        self.assertNotIn("retail store", policies)
        self.assertNotIn("LinkedIn", policies)

    def test_manual_cv_and_uninstrumented_funnel_intake_patterns(self):
        scenario = adapt_messy_intake({
            "client_intake_case": {
                "scenario_code": "GENERAL_INTAKE_PATTERN_TEST",
                "company_name": "Generic Engineering Company",
                "basic_company_facts": {
                    "industry": "Industrial engineering",
                    "footprint_and_headcount": "Engineering workforce across two locations",
                },
                "ingaze_onboarding_surveys_raw": {
                    "employer_archetype_survey_response": {
                        "q8_initiative_hr_believes_they_need": (
                            "A corporate culture video and increased sponsored job-board advertising"
                        ),
                    },
                    "recruiting_cost_review_survey_response": {
                        "q4_screening_note": (
                            "Recruiters spend 8 hours per week manually opening unqualified CV PDFs in a shared inbox."
                        ),
                    },
                },
                "outside_in_scraped_telemetry": {
                    "career_website_and_jd_telemetry": {
                        "traffic_and_funnel_metrics": {
                            "tracking_diagnostic_note": (
                                "The webform is uninstrumented and has zero pre-screening; no conversion pixel is installed."
                            ),
                        }
                    },
                },
            },
        })
        observations, _ = normalize_narrative(scenario, self.graph)
        signals = {row["signal"] for row in observations if row["state"] == "present"}
        self.assertIn("tracking_workflow_verified", signals)
        self.assertIn("manual_tracking_load", signals)
        self.assertIn("tracking_attribution_gap_reported", signals)
        gap_rows = [
            row for row in observations
            if row["signal"] == "tracking_attribution_gap_reported"
        ]
        self.assertTrue(gap_rows)
        self.assertEqual({"present"}, {row["state"] for row in gap_rows})
        diagnoses = diagnose(self.graph, observations)
        self.assertIn("manual_measurement", {row["rule"] for row in diagnoses})
        self.assertIn(
            "increased sponsored job-board advertising",
            scenario["client_internal_context"]["leadership_perceptions_and_requests"],
        )

        # The broadened client phrasing must not introduce this signal in the
        # official scenarios, which remain protected by the output regression check.
        for official_scenario in self.scenarios:
            official_observations, _ = normalize_narrative(official_scenario, self.graph)
            self.assertNotIn(
                "tracking_attribution_gap_reported",
                {row["signal"] for row in official_observations},
                official_scenario["scenario_code"],
            )

    def test_step4_defers_premature_brand_video_and_job_board_spend(self):
        scenario = {
            "scenario_code": "GENERAL_GUARDRAIL_TEST",
            "client_internal_context": {},
            "requests": [
                {"request_text": "Produce a corporate culture video before addressing internal issues."},
                {"request_text": "Double sponsored job-board ad spend next quarter."},
            ],
        }
        expectation_gap = {
            "id": "expectation-gap", "signal": "documented_broken_promise",
            "quality": "reported", "state": "present", "evidence_type": "reported_observation",
        }
        funnel_gap = {
            "id": "funnel-gap", "signal": "tracking_attribution_gap_reported",
            "quality": "reported", "state": "present", "evidence_type": "reported_observation",
        }

        def guards_for(observations):
            state = evaluate_guardrails(
                scenario, {}, {"observations": observations, "excluded": []}, [], [], set()
            )
            return state["guards"]

        guards = guards_for([expectation_gap, funnel_gap])
        self.assertIn(
            "Defer corporate culture or branding videos until internal expectation gaps and management practices are verified and addressed.",
            guards,
        )
        self.assertIn(
            "Defer increasing sponsored job-board ad spend until funnel tracking, pre-screening filters, and qualified conversion are verified.",
            guards,
        )

        without_blocker = guards_for([funnel_gap])
        without_funnel_signal = guards_for([expectation_gap])
        self.assertNotIn(
            "Defer corporate culture or branding videos until internal expectation gaps and management practices are verified and addressed.",
            without_blocker,
        )
        self.assertNotIn(
            "Defer increasing sponsored job-board ad spend until funnel tracking, pre-screening filters, and qualified conversion are verified.",
            without_funnel_signal,
        )

    def test_burnout_mutation_defers_advocacy_but_keeps_feedback_pilot(self):
        clean = deepcopy(self.scenarios[2])
        changed = deepcopy(clean)
        changed["client_internal_context"]["cohort_and_site_asymmetries"] += (
            " Interviews report severe workload burnout in the target cohort."
        )
        original, _ = self.run_plan(clean)
        revised, trace = self.run_plan(changed)
        old = {pilot["rule"] for pilot in original["phase_2_actions"]}
        new = {pilot["rule"] for pilot in revised["phase_2_actions"]}
        self.assertIn("advocacy_pilot", old)
        self.assertNotIn("advocacy_pilot", new)
        self.assertIn("feedback_coverage", new)
        self.assertIn("burnout", trace["advocacy_blockers"])

    def test_t1_outcomes_do_not_change_ranking(self):
        scenario = self.scenarios[1]
        active = self.analytics["active"][scenario["scenario_code"]]
        cases = self.dataset["raw_case_study_narratives"]
        original = case_matches(cases, {"mobile_friction", "agency_spend"}, {"freight"},
                                graph=self.graph, active=active, case_analytics=self.analytics["cases"])
        changed = deepcopy(self.analytics["cases"])
        name = original[0]["case"]
        changed[name]["t1_after_12_months"]["hiring_and_retention_kpis"]["agency_filled_roles_pct"] = 0
        mutated = case_matches(cases, {"mobile_friction", "agency_spend"}, {"freight"},
                               graph=self.graph, active=active, case_analytics=changed)
        self.assertEqual([(row["case"], row["score"]) for row in original],
                         [(row["case"], row["score"]) for row in mutated])
        self.assertNotEqual(original[0]["observed_t0_t1"], mutated[0]["observed_t0_t1"])

    def test_policy_and_synthetic_and_scientific_records_remain_distinct(self):
        output, trace = self.run_plan(self.scenarios[2])
        kinds = {item["evidence_class"] for item in output["supporting_research_snippets"]}
        self.assertTrue({"mandatory_constraint", "published_scientific_finding", "organizer_reference"} <= kinds)
        self.assertTrue(all(row["quality"] != "verified" for row in trace["diagnostic_observations"]
                            if row["evidence_type"] == "synthetic_observation"))
        self.assertTrue(trace["operational_assumptions"])


if __name__ == "__main__":
    unittest.main()
