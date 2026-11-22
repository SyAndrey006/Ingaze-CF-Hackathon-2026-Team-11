"""Regression tests for LLM normalization of nested organizer intakes."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.main import _persist_stage_result, run_custom_client
from src.pipeline.step1_normalize_input import (
    load_standalone_input,
    normalize_client_input,
)
from src.schemas.pipeline_models import RawScenarioBundle


ROOT = Path(__file__).resolve().parents[1]
BLIND_TEST = ROOT / "data" / "ingaze_sunday_blind_test_meridiana.json"


class CapturingNormalizer:
    """Structured fake that returns grounded facts from the blind intake."""

    def __init__(self):
        self.calls = []

    def generate_structured(self, system_prompt, user_prompt, response_model):
        payload = json.loads(user_prompt)
        raw = payload["raw_scenario"]
        self.calls.append({"system": system_prompt, "payload": payload})
        if "basic_company_facts" not in raw:
            return response_model.model_validate(
                {
                    "scenario_code": payload["scenario_code"],
                    "company_name": raw.get("company_name", "Unknown client"),
                    "industry_raw": raw.get("industry", "Unspecified"),
                    "sector_category": "GENERAL_ENTERPRISE",
                }
            )
        facts = raw["basic_company_facts"]
        surveys = raw["ingaze_onboarding_surveys_raw"]
        agency_quote = surveys["recruiting_cost_review_survey_response"]["q8_agency_note"]
        tracking_quote = raw["outside_in_scraped_telemetry"][
            "career_website_and_jd_telemetry"
        ]["traffic_and_funnel_metrics"]["tracking_diagnostic_note"]
        return response_model.model_validate(
            {
                "scenario_code": payload["scenario_code"],
                "company_name": raw["company_name"],
                "industry_raw": facts["industry"],
                "sector_category": "GENERAL_ENTERPRISE",
                "workforce_archetypes": [
                    "MIXED_DISTRIBUTED",
                    "DESKLESS_FRONTLINE_LOGISTICS",
                    "DESK_BASED_TECH_SPECIALIST",
                ],
                "headcount": 1150,
                "locations_count": 6,
                "workforce_target_summary": facts["open_roles_mentioned_verbally"],
                "canonical_signals": [
                    {
                        "signal_code": "MOBILE_PORTAL_FRICTION",
                        "evidence_quote": tracking_quote,
                        "source_stream": "outside_in_platform",
                        "severity": "HIGH",
                        "affected_cohorts": ["field electrical technicians"],
                    },
                    {
                        "signal_code": "CAREER_PATH_OPACITY",
                        "evidence_quote": "department directors block internal transfers between legacy IT and the Smart-Grid AI team",
                        "source_stream": "inside_out_client",
                        "severity": "HIGH",
                        "affected_cohorts": ["mid-level Data and Cloud engineers"],
                    },
                    {
                        "signal_code": "HIGH_EXTERNAL_AGENCY_DEPENDENCY",
                        "evidence_quote": agency_quote,
                        "source_stream": "inside_out_client",
                        "severity": "HIGH",
                        "affected_cohorts": ["field technicians"],
                    },
                    {
                        "signal_code": "GENERIC_BOILERPLATE_JDS",
                        "evidence_quote": "job ads read like 1998 municipal legal notices",
                        "source_stream": "inside_out_client",
                        "severity": "MEDIUM",
                        "affected_cohorts": ["field technicians"],
                    },
                    {
                        "signal_code": "LOW_PUBLIC_RATING",
                        "evidence_quote": "headline Glassdoor/Indeed score sits at 3.34 stars",
                        "source_stream": "outside_in_platform",
                        "severity": "MEDIUM",
                    },
                ],
                "healthy_baselines": [
                    {
                        "asset_or_cohort_name": "Field electrical technicians",
                        "evidence": "Over 91% stay for years; technicians receive paid high-voltage certifications and a compressed summer workweek.",
                        "related_signal": "HIGH_COHORT_RETENTION_HEALTHY",
                        "do_not_touch_scope": "Preserve the field technician retention strengths while fixing recruitment friction.",
                    }
                ],
                "cohort_site_asymmetries": [
                    {
                        "struggling_segment": "Mid-level Data and Cloud engineers at the HQ",
                        "struggling_evidence": "Department directors block internal transfers between legacy IT and the Smart-Grid AI team.",
                        "healthy_comparison_segment": "Field electrical technicians",
                        "healthy_evidence": "Over 91% stay for years.",
                    }
                ],
                "leadership_requests": [
                    {
                        "stakeholder_role": "CHRO",
                        "requested_action_text": "Launch a TikTok and LinkedIn Gen-Z employee ambassador campaign next month.",
                        "inferred_action_category": "AMBASSADOR_SELECTION_ENABLEMENT",
                        "requested_urgency": "IMMEDIATE_PHASE_1",
                        "target_scope": "early-career candidates",
                    },
                    {
                        "stakeholder_role": "CHRO",
                        "requested_action_text": "Hire a creative agency for a six-month corporate EVP overhaul from scratch.",
                        "inferred_action_category": "EVP_OVERHAUL_FROM_SCRATCH",
                        "requested_urgency": "IMMEDIATE_PHASE_1",
                        "target_scope": "company-wide",
                    },
                ],
                "budget_and_cfo_constraints": [
                    "CFO and Grid Operations Committee require hard savings on external staffing agency spend before approving discretionary branding."
                ],
            }
        )


class TestOrganizerMessyIntake(unittest.TestCase):
    def test_loader_preserves_nested_raw_intake_for_normalization(self):
        bundles = load_standalone_input(BLIND_TEST)
        self.assertEqual(1, len(bundles))
        raw = bundles[0].raw_scenario
        self.assertEqual("SCENARIO_BLIND_02_MERIDIANA", bundles[0].scenario_code)
        self.assertIn("raw_discovery_call_notes", raw)
        self.assertIn("ingaze_onboarding_surveys_raw", raw)
        self.assertIn("outside_in_scraped_telemetry", raw)
        self.assertNotIn("intake_normalization_audit", raw)

    def test_blind_intake_uses_llm_and_generates_valid_submission(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            client = CapturingNormalizer()

            def persist(code, stage, result, output_dir=None):
                return _persist_stage_result(code, stage, result, output_dir or folder)

            with patch("src.main._persist_stage_result", side_effect=persist):
                with redirect_stdout(io.StringIO()):
                    result = run_custom_client(
                        BLIND_TEST,
                        output_path=folder / "submission.json",
                        proposal_output_path=folder / "proposal.md",
                        normalized_output_path=folder,
                        llm_client=client,
                    )

            self.assertEqual(1, len(client.calls))
            raw_sent_to_llm = client.calls[0]["payload"]["raw_scenario"]
            self.assertIn("raw_discovery_call_notes", raw_sent_to_llm)
            self.assertIn("ingaze_onboarding_surveys_raw", raw_sent_to_llm)
            self.assertIn("outside_in_scraped_telemetry", raw_sent_to_llm)
            self.assertIn("nested objects, arrays", client.calls[0]["system"])
            self.assertEqual("llm_normalized", result["normalization_status"])
            self.assertEqual("SCENARIO_BLIND_02_MERIDIANA", result["scenarios"][0]["scenario_code"])
            self.assertTrue(result["scenarios"][0]["diagnosed_root_causes"])
            self.assertTrue((folder / "submission.json").is_file())
            self.assertTrue((folder / "proposal.md").is_file())

    def test_plain_text_brief_uses_the_same_llm_normalizer(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            brief = "A field engineering team loses applicants during a lengthy mobile application."
            source = folder / "brief.txt"
            source.write_text(brief, encoding="utf-8")
            client = CapturingNormalizer()
            with redirect_stdout(io.StringIO()):
                result = run_custom_client(
                    source,
                    output_path=folder / "submission.json",
                    proposal_output_path=folder / "proposal.md",
                    normalized_output_path=folder,
                    llm_client=client,
                )
        self.assertEqual("llm_normalized", result["normalization_status"])
        self.assertEqual(1, len(client.calls))
        self.assertEqual(
            brief,
            client.calls[0]["payload"]["raw_scenario"]["client_internal_context"],
        )

    def test_deterministic_fallback_extracts_blind_case_core_signals(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            client = CapturingNormalizer()
            with redirect_stdout(io.StringIO()):
                result = run_custom_client(
                    BLIND_TEST,
                    output_path=folder / "submission.json",
                    proposal_output_path=folder / "proposal.md",
                    normalized_output_path=folder,
                    skip_llm_normalization=True,
                    llm_client=client,
                )
            normalized = json.loads(
                Path(result["normalized_input_path"]).read_text(encoding="utf-8")
            )
        self.assertEqual("deterministic_fallback", result["normalization_status"])
        self.assertEqual([], client.calls)
        signals = {row["signal_code"] for row in normalized["canonical_signals"]}
        self.assertTrue(
            {
                "MOBILE_PORTAL_FRICTION",
                "CAREER_PATH_OPACITY",
                "HIGH_EXTERNAL_AGENCY_DEPENDENCY",
            }.issubset(signals)
        )
        self.assertTrue(normalized["healthy_baselines"])
        self.assertTrue(normalized["cohort_site_asymmetries"])
        self.assertTrue(result["scenarios"][0]["phase_2_actions"])

    def test_normalizer_does_not_bypass_llm_for_pre_audited_input(self):
        client = CapturingNormalizer()
        raw = {
            "scenario_code": "AUDITED_CLIENT",
            "company_name": "Audited Client",
            "industry": "Industrial engineering",
            "intake_normalization_audit": {"measurements": [], "excluded": []},
        }
        normalized = normalize_client_input(
            RawScenarioBundle(scenario_code="AUDITED_CLIENT", raw_scenario=raw),
            client,
        )
        self.assertEqual(1, len(client.calls))
        self.assertEqual("AUDITED_CLIENT", normalized.scenario_code)
