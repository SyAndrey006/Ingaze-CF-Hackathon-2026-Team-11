"""Regression tests for the organizer's raw intake format."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.main import _persist_stage_result, run_custom_client
from src.pipeline.step1_normalize_input import load_standalone_input


def organizer_intake():
    return {
        "metadata": {"dataset_name": "Raw test intake"},
        "client_intake_case": {
            "scenario_code": "UNSEEN_MESSY_CLIENT",
            "company_name": "Orchard Controls",
            "basic_company_facts": {
                "industry": "Industrial software",
                "footprint_and_headcount": "82 employees at our Lyon office",
                "open_roles_mentioned_verbally": "Software engineers in Lyon",
            },
            "raw_discovery_call_notes": [
                {
                    "source": "Discovery with recruiting",
                    "raw_notes": (
                        "For the Lyon software hub, 2 of the last 5 hires resigned before the "
                        "6-month probation and 3 candidates withdrew while waiting for technical interview slots."
                    ),
                },
                {
                    "source": "Managing Director",
                    "raw_notes": (
                        "Do not launch a public employee advocacy campaign. "
                        "Veteran plant staff rarely leave and receive punctual travel allowances."
                    ),
                },
                {
                    "source": "Forwarded marketing note",
                    "raw_notes": "Our trade-fair campaign sent 900 smartphone clicks to the careers page.",
                },
            ],
            "ingaze_onboarding_surveys_raw": {
                "recruiting_cost_review_survey_response": {
                    "q5_process_note": "Average 19 days from HR interview to first technical round",
                    "q8_agency_note": "4 of 15 hires came through external headhunters",
                    "tracked_first_year_attrition_pct": None,
                },
                "internal_climate_and_candidate_feedback_notes": {
                    "raw_unfiltered_snippets": [
                        "[Exit note — Lyon Software Engineer] Job ad promised hybrid work. "
                        "Day one was fully on-site. Manager cancelled four 1-on-1s.",
                        "[Plant suggestion box] The coffee vending machine is broken.",
                    ],
                },
            },
            "outside_in_scraped_telemetry": {
                "public_reputation_telemetry": {"raw_unfiltered_overall_rating_5": 2.1},
                "career_website_and_jd_telemetry": {
                    "traffic_and_funnel_metrics": {
                        "last_30d_raw_bounce_or_dropoff_pct": 99,
                        "applicant_conversion_rate_pct": None,
                    },
                },
            },
        },
    }


class TestOrganizerMessyIntake(unittest.TestCase):
    def test_raw_intake_reaches_the_engine_without_an_llm(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / "intake.json"
            source.write_text(json.dumps(organizer_intake()), encoding="utf-8")

            def persist(code, stage, result, output_dir=None):
                return _persist_stage_result(code, stage, result, output_dir or folder)

            client = Mock()
            with patch("src.main._persist_stage_result", side_effect=persist), redirect_stdout(StringIO()):
                result = run_custom_client(
                    source, output_path=folder / "output.json",
                    proposal_output_path=folder / "proposal.md",
                    normalized_output_path=folder, llm_client=client,
                )
            normalized = json.loads(Path(result["normalized_input_path"]).read_text(encoding="utf-8"))

        client.generate_structured.assert_not_called()
        self.assertEqual("deterministic_messy_intake", result["normalization_status"])
        scenario, trace = result["scenarios"][0], result["traces"][0]
        self.assertEqual("UNSEEN_MESSY_CLIENT", scenario["scenario_code"])
        hypotheses = {row["rule"]: row for row in trace["diagnostic_hypotheses"]}
        self.assertEqual("lyon", hypotheses["expectation_drift"]["scope"]["site"])
        self.assertEqual("plausible", hypotheses["expectation_drift"]["status"])
        self.assertIn("employee_exits", hypotheses["expectation_drift"]["dependent_families"])
        self.assertIn("interview_capacity", {row.get("rule") for row in scenario["phase_1_actions"]})
        self.assertNotIn("interview_capacity", {row["rule"] for row in scenario["phase_2_actions"]})
        self.assertTrue(any("explicit restriction" in guard for guard in scenario["blocked_traps_and_guardrails"]))
        self.assertIn("punctual travel allowances", scenario["strategic_focus_and_do_not_touch"][0])
        self.assertTrue(normalized["healthy_baselines"])
        self.assertEqual("advocacy_pilot", trace["protected_scopes"][0]["rules"][0])
        self.assertTrue(all(row["quality"] == "reported" for row in trace["diagnostic_observations"]))
        self.assertTrue(all(row["source_ref"].startswith("/client_intake_case/") for row in trace["diagnostic_observations"]))
        self.assertNotIn("application_friction", hypotheses)
        self.assertEqual(4, len(trace["excluded_noise"]))
        measures = {row["metric_path"]: row for row in trace["normalized_measurements"]}
        self.assertEqual(19, measures["reported_hr_to_first_technical_interview"]["value"])
        self.assertEqual(5, measures["reported_early_exits"]["denominator_count"])
        self.assertEqual("6_months", measures["reported_early_exits"]["measurement_horizon"])
        self.assertEqual(26.67, measures["reported_agency_filled_roles_pct"]["value"])
        self.assertEqual(2, len(normalized["intake_normalization_audit"]["missing"]))

    def test_bare_intake_is_one_client_and_preserves_source_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "intake.json"
            source.write_text(json.dumps(organizer_intake()["client_intake_case"]), encoding="utf-8")
            bundles = load_standalone_input(source)
        self.assertEqual(1, len(bundles))
        rows = bundles[0].raw_scenario["reported_intake_observations"]
        self.assertTrue(rows[0]["source_ref"].startswith("/raw_discovery_call_notes/"))
