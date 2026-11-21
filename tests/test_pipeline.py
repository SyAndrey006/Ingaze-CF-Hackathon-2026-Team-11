"""Tests for schemas, Step 1 hygiene, and active deterministic pipeline behavior."""

from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.main import (
    DEFAULT_DATA as ENGINE_DATA,
    load_analytics as load_engine_analytics,
    load_graph as load_engine_graph,
    load_library as load_engine_library,
    plan as run_engine_plan,
)

from src.schemas.domain_models import (
    NormalizedCasesDB,
    NormalizedRulesDB,
    SectorCategory,
    SignalCode,
    TelemetrySnapshot,
)
from src.schemas.pipeline_models import (
    DiagnosisResult,
    ExtractedSignal,
    GuardrailResult,
    NormalizedClientInput,
    PhasePlan,
    RawScenarioBundle,
    ScoredAction,
    ScoredCandidates,
)
from src.schemas.submission_models import ScenarioSubmission, SubmissionPayload
from src.pipeline.step1_normalize_input import (
    INPUT_FILE,
    OUTPUT_DIR,
    _build_system_prompt,
    _is_quote_grounded,
    filter_contaminated_signals,
    load_standalone_input,
    run_normalization_cli,
)
from src.pipeline.step6_hr_proposal import generate_hr_proposal
from src.utils.verifier import verify_scenario_submission

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_PLACEHOLDER_PATH = BASE_DIR / "database" / "normalized" / "normalized_rules.json"
CASES_PLACEHOLDER_PATH = BASE_DIR / "database" / "normalized" / "normalized_cases.json"


class TestSchemaValidation(unittest.TestCase):
    """Smoke tests confirming schemas match the current database artifacts."""

    def test_normalized_rules_json_matches_schema(self) -> None:
        raw_text = RULES_PLACEHOLDER_PATH.read_text(encoding="utf-8")
        rules_db = NormalizedRulesDB.model_validate_json(raw_text)
        self.assertEqual(rules_db.schema_version, "1.0.0")
        self.assertIsInstance(rules_db.symptom_to_root_cause_rules, list)

    def test_normalized_cases_json_matches_schema(self) -> None:
        raw_text = CASES_PLACEHOLDER_PATH.read_text(encoding="utf-8")
        cases_db = NormalizedCasesDB.model_validate_json(raw_text)
        self.assertEqual(cases_db.schema_version, "1.0.0")
        self.assertIsInstance(cases_db.cases, list)

    def test_submission_payload_contains_8_required_and_3_optional_keys(self) -> None:
        scenario = ScenarioSubmission(
            scenario_code="EXAMPLE_SYNTHETIC_SCENARIO",
            diagnosed_root_causes=["Root cause example"],
            blocked_traps_and_guardrails=["Blocked wrong-sector tactic example"],
            phase_1_actions=["Foundational audit"],
            phase_2_actions=["Core structural fix"],
            phase_3_actions=["Downstream scaling"],
            matched_case_studies=["Example Case (+25% conversion)"],
            supporting_research_snippets=["Snippet 2: -30-35% mobile drop-off"],
            strategic_focus_and_do_not_touch=["Preserve healthy baseline"],
            cohort_specific_strategies=["Hub A vs. Hub B differentiation"],
            open_questions_and_hypotheses_for_client=["Verify ATS funnel logs"],
        )
        payload = SubmissionPayload(
            team_name="Team 11",
            chosen_architecture_paradigm="Hybrid Deterministic + AI Pipeline",
            scenarios=[scenario],
        )
        dumped = payload.model_dump()
        scenario_keys = set(dumped["scenarios"][0].keys())
        expected_keys = {
            "scenario_code",
            "diagnosed_root_causes",
            "blocked_traps_and_guardrails",
            "phase_1_actions",
            "phase_2_actions",
            "phase_3_actions",
            "matched_case_studies",
            "supporting_research_snippets",
            "strategic_focus_and_do_not_touch",
            "cohort_specific_strategies",
            "open_questions_and_hypotheses_for_client",
        }
        self.assertEqual(scenario_keys, expected_keys)


class TestPipelineBehavior(unittest.TestCase):
    """Exercise active pipeline behavior alongside the Step 1 normalization tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = json.loads(ENGINE_DATA.read_text(encoding="utf-8-sig"))
        cls.graph = load_engine_graph()
        cls.analytics = load_engine_analytics()
        cls.library = load_engine_library()

    def _plan_scenario(self, scenario_index: int):
        scenario = self.dataset["company_scenarios_to_diagnose"][scenario_index]
        with patch("src.main._persist_stage_result", return_value=None):
            return run_engine_plan(
                scenario,
                self.dataset,
                self.library,
                self.graph,
                self.analytics,
            )

    def test_step1_noise_filtering_strips_contaminated_rows(self) -> None:
        class LLMFlaggedSignal(ExtractedSignal):
            is_unverified_or_external_noise: bool = True

        bundle = RawScenarioBundle(
            scenario_code="SYNTHETIC_TECH_CLIENT",
            raw_scenario={
                "company_name": "Synthetic Tech Client",
                "industry": "B2B software",
                "workforce_target": "Software engineers",
                "client_internal_context": (
                    "Corporate posts have low engagement. Unverified third-party pilot "
                    "data in the platform feed."
                ),
                "ingaze_platform_signals": {
                    "reviews": "Retail weekend shift fatigue in shop staff."
                },
            },
        )
        verified = ExtractedSignal(
            signal_code=SignalCode.LOW_CORPORATE_SOCIAL_ENGAGEMENT,
            evidence_quote="Corporate posts have low engagement.",
            source_stream="outside_in_platform",
            severity="MEDIUM",
        )
        unverified = LLMFlaggedSignal(
            signal_code=SignalCode.UNPREDICTABLE_SHIFT_SCHEDULING,
            evidence_quote="Unverified third-party pilot data in the platform feed.",
            source_stream="outside_in_platform",
            severity="HIGH",
        )
        impossible = ExtractedSignal(
            signal_code=SignalCode.WORKLOAD_BURNOUT,
            evidence_quote="Retail weekend shift fatigue in shop staff.",
            source_stream="inside_out_client",
            severity="HIGH",
        )

        clean, noise = filter_contaminated_signals(bundle, [verified, unverified, impossible])

        self.assertEqual([signal.signal_code for signal in clean], [SignalCode.LOW_CORPORATE_SOCIAL_ENGAGEMENT])
        self.assertEqual(len(noise), 2)
        self.assertTrue(any("unverified" in item.reason_filtered.lower() for item in noise))
        self.assertTrue(any("physical retail" in item.reason_filtered.lower() for item in noise))

    def test_step1_deduplicates_signal_codes_and_merges_evidence_and_cohorts(self) -> None:
        bundle = RawScenarioBundle(
            scenario_code="SYNTHETIC_TECH_CLIENT",
            raw_scenario={
                "company_name": "Synthetic Tech Client",
                "industry": "B2B software",
                "workforce_target": "Software engineers",
                "client_internal_context": (
                    "16% of new hires leave within six months. "
                    "Early first-year turnover is elevated in Berlin."
                ),
                "ingaze_platform_signals": {},
            },
        )
        first = ExtractedSignal(
            signal_code=SignalCode.EARLY_FIRST_YEAR_ATTRITION,
            evidence_quote="16% of new hires leave within six months.",
            source_stream="inside_out_client",
            severity="MEDIUM",
            affected_cohorts=["Milan product squad"],
        )
        second = ExtractedSignal(
            signal_code=SignalCode.EARLY_FIRST_YEAR_ATTRITION,
            evidence_quote="Early first-year turnover is elevated in Berlin.",
            source_stream="t0_telemetry",
            severity="HIGH",
            affected_cohorts=["Berlin product squad", "Milan product squad"],
        )

        clean, noise = filter_contaminated_signals(bundle, [first, second])

        self.assertEqual(noise, [])
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean[0].signal_code, SignalCode.EARLY_FIRST_YEAR_ATTRITION)
        self.assertIn(first.evidence_quote, clean[0].evidence_quote)
        self.assertIn(second.evidence_quote, clean[0].evidence_quote)
        self.assertEqual(
            clean[0].affected_cohorts,
            ["Milan product squad", "Berlin product squad"],
        )
        self.assertEqual(clean[0].severity, "HIGH")

    def test_step1_accepts_fuzzy_and_key_value_metric_evidence(self) -> None:
        bundle = RawScenarioBundle(
            scenario_code="SYNTHETIC_TECH_CLIENT",
            raw_scenario={
                "company_name": "Synthetic Tech Client",
                "industry": "B2B software",
                "client_internal_context": (
                    "New engineering leads were promoted without management coaching "
                    "or a standardized career progression framework. Teams face heavy "
                    "workload pressure. HR manually exports LinkedIn post and employee "
                    "sharing statistics into spreadsheets for four hours each week."
                ),
                "ingaze_platform_signals": {},
            },
            t0_telemetry=TelemetrySnapshot.model_validate(
                {"public_reputation": {"overall_review_rating_5": 3.83}}
            ),
        )
        quotes_and_codes = [
            (
                SignalCode.CAREER_PATH_OPACITY,
                "New engineering leads lack coaching and standardized career path framework.",
            ),
            (
                SignalCode.WORKLOAD_BURNOUT,
                "Teams face heavy workload and burnout pressure.",
            ),
            (
                SignalCode.MANUAL_HR_SPREADSHEET_DRAG,
                "HR manually exports LinkedIn post metrics into spreadsheets for four hours weekly.",
            ),
            (
                SignalCode.LOW_PUBLIC_RATING,
                "overall_review_rating_5: 3.83",
            ),
            (
                SignalCode.SAY_DO_GAP,
                "A completely unsupported claim about unrelated proprietary workflow software.",
            ),
        ]
        extracted = [
            ExtractedSignal(
                signal_code=signal_code,
                evidence_quote=quote,
                source_stream="inside_out_client",
                severity="MEDIUM",
            )
            for signal_code, quote in quotes_and_codes
        ]

        clean, noise = filter_contaminated_signals(bundle, extracted)

        self.assertTrue(_is_quote_grounded(bundle, quotes_and_codes[0][1]))
        self.assertTrue(_is_quote_grounded(bundle, quotes_and_codes[2][1]))
        self.assertTrue(_is_quote_grounded(bundle, quotes_and_codes[3][1]))
        self.assertEqual(len(clean), len(extracted))
        self.assertEqual(noise, [])

    def test_step1_prompt_explicitly_captures_say_do_gap(self) -> None:
        prompt = _build_system_prompt()
        self.assertIn("SAY_DO_GAP", prompt)
        self.assertIn("greater than 1.1", prompt)

    def test_step1_loads_standalone_json_objects_lists_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            single_path = directory / "single.json"
            single_path.write_text(
                json.dumps({"company_name": "Single Client", "industry": "Healthcare"}),
                encoding="utf-8",
            )
            single = load_standalone_input(single_path)
            self.assertEqual(len(single), 1)
            self.assertEqual(single[0].scenario_code, "single")

            list_path = directory / "clients.json"
            list_path.write_text(
                json.dumps(
                    [
                        {"scenario_code": "CLIENT_A", "company_name": "Client A"},
                        {"scenario_id": "CLIENT_B", "company_name": "Client B"},
                    ]
                ),
                encoding="utf-8",
            )
            clients = load_standalone_input(list_path)
            self.assertEqual(
                [bundle.scenario_code for bundle in clients],
                ["CLIENT_A", "CLIENT_B"],
            )

            text_path = directory / "client_brief.txt"
            text_path.write_text("A growing clinical services company needs staff.", encoding="utf-8")
            text_bundle = load_standalone_input(text_path)[0]
            self.assertEqual(text_bundle.raw_scenario["company_name"], "client_brief")
            self.assertEqual(
                text_bundle.raw_scenario["client_internal_context"],
                "A growing clinical services company needs staff.",
            )

            wrapped_path = directory / "wrapped.json"
            wrapped_path.write_text(
                json.dumps({"clients": [{"company_name": "Wrapped Client"}]}),
                encoding="utf-8",
            )
            wrapped = load_standalone_input(wrapped_path)
            self.assertEqual(wrapped[0].scenario_code, "wrapped")

    def test_step1_reads_input_json_and_writes_intermediate_file(self) -> None:
        class FakeLLMClient:
            def generate_structured(self, system_prompt, user_prompt, response_model):
                payload = json.loads(user_prompt)
                raw = payload["raw_scenario"]
                return response_model.model_validate(
                    {
                        "scenario_code": payload["scenario_code"],
                        "company_name": raw.get("company_name", "Unknown client"),
                        "industry_raw": raw.get("industry", "Unspecified"),
                        "sector_category": "B2B_TECH_SAAS",
                    }
                )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            client_io_dir = root / "data" / "client_io"
            input_path = client_io_dir / "input.json"
            output_dir = root / "data" / "intermediate_steps"
            client_io_dir.mkdir(parents=True)
            input_path.write_text(
                json.dumps(
                    {
                        "company_name": "Client Alpha",
                        "industry": "B2B software",
                        "client_internal_context": "A growing software company.",
                    }
                ),
                encoding="utf-8",
            )
            captured = io.StringIO()
            with redirect_stdout(captured):
                results = run_normalization_cli(
                    file_path=input_path,
                    output_dir=output_dir,
                    llm_client=FakeLLMClient(),
                )

            normalized_path = output_dir / "input" / "step1_normalize_input.json"
            self.assertEqual(len(results), 1)
            self.assertTrue(normalized_path.is_file())
            loaded = NormalizedClientInput.model_validate_json(
                normalized_path.read_text(encoding="utf-8")
            )
            self.assertEqual(loaded.scenario_code, "input")
            self.assertIn("Processing input.json...", captured.getvalue())
            self.assertIn("Normalization complete:", captured.getvalue())
            self.assertNotIn("Healthy Baselines", captured.getvalue())
            self.assertIn("healthy_baselines", json.loads(normalized_path.read_text(encoding="utf-8")))

    def test_step1_empty_input_json_prints_add_data_message(self) -> None:
        class UnexpectedLLMClient:
            def generate_structured(self, *args, **kwargs):
                raise AssertionError("No LLM call should happen for an empty input template.")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "data" / "client_io" / "input.json"
            input_path.parent.mkdir(parents=True)
            input_path.write_text("{}", encoding="utf-8")
            captured = io.StringIO()
            with redirect_stdout(captured):
                results = run_normalization_cli(
                    file_path=input_path,
                    output_dir=root / "data" / "intermediate_steps",
                    llm_client=UnexpectedLLMClient(),
                )
            self.assertEqual(results, [])
            self.assertIn("No client details found", captured.getvalue())

    def test_step1_default_output_directory_is_intermediate_steps(self) -> None:
        self.assertEqual(OUTPUT_DIR, BASE_DIR / "data" / "intermediate_steps")
        self.assertEqual(INPUT_FILE, BASE_DIR / "data" / "client_io" / "input.json")

    def test_step4_guardrail_blocks_wrong_industry_and_pauses_premature_advocacy(self) -> None:
        result, trace = self._plan_scenario(0)
        self.assertTrue(
            any("Exclude retail store shift rotation" in item for item in trace["guardrails"])
        )
        self.assertTrue(
            any("Defer external advocacy" in item for item in trace["guardrails"])
        )
        phase_actions = " ".join(
            str(item)
            for key in ("phase_1_actions", "phase_2_actions", "phase_3_actions")
            for item in result[key]
        ).casefold()
        self.assertNotIn("retail store shift rotation", phase_actions)

    def test_step5_phase_planner_accelerates_advocacy_when_culture_healthy(self) -> None:
        result, _ = self._plan_scenario(2)
        phase_one = [item for item in result["phase_1_actions"] if item.get("rule") == "advocacy_pilot"]
        phase_two = [item for item in result["phase_2_actions"] if item.get("rule") == "advocacy_pilot"]
        phase_three = [item for item in result["phase_3_actions"] if item.get("rule") == "advocacy_pilot"]
        self.assertTrue(phase_one, "Readiness diagnostics must precede the advocacy pilot.")
        self.assertTrue(phase_two, "Healthy internal conditions allow a scoped pilot after diagnostics.")
        self.assertTrue(phase_three, "Scaling remains gated on measured pilot outcomes.")
        self.assertTrue(phase_two[0].get("prerequisite"))
        self.assertTrue(phase_three[0].get("condition"))

    def test_step6_proposal_is_deterministic_and_covers_approved_stages(self) -> None:
        result, trace = self._plan_scenario(0)
        proposal = trace["proposal_markdown"]
        for heading in (
            "## Executive Summary",
            "## Key Problems",
            "## What NOT to Do / Strengths to Protect",
            "## Three-Phase Action Plan",
            "## Precedents & Next Steps",
        ):
            self.assertIn(heading, proposal)
        self.assertIn("SCENARIO_A_CLOUDNOVA_FINTECH", proposal)
        self.assertIn("Exclude retail store shift rotation", proposal)
        self.assertEqual(result["scenario_code"], "SCENARIO_A_CLOUDNOVA_FINTECH")
        executive_section = proposal.split("## Executive Summary", 1)[1].split(
            "## Key Problems", 1
        )[0]
        self.assertNotIn("prerequisite", executive_section.casefold())
        baseline_section = proposal.split("### Strengths to protect", 1)[1].split(
            "### Cohort and site differences", 1
        )[0]
        self.assertEqual(baseline_section.count("82nd percentile"), 1)
        self.assertNotIn('{"', proposal)
        self.assertNotIn("client_internal_context.", proposal)
        self.assertNotIn("missing families:", proposal.casefold())
        self.assertNotIn("dependent families:", proposal.casefold())
        self.assertNotIn("status: plausible", proposal.casefold())
        self.assertNotIn("decision: conditional", proposal.casefold())
        self.assertNotIn("### Leadership requests", proposal)
        self.assertNotIn("{", proposal)
        self.assertNotIn("root causes match", proposal.casefold())
        self.assertNotIn("t0->t1", proposal.casefold())
        lines = proposal.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("### "):
                following = next((item for item in lines[index + 1:] if item.strip()), "")
                self.assertFalse(following.startswith("#"), f"Empty subsection: {line}")

        class ClearLLM:
            called = False

            def generate_structured(self, *, system_prompt, user_prompt, response_model):
                self.called = True
                self.assert_grounding_prompt = "Do not invent" in system_prompt
                return response_model.model_validate(
                    {"proposal_markdown": "## Executive Summary\nReview the evidence, then sequence the approved work."}
                )

        class UngroundedLLM(ClearLLM):
            def generate_structured(self, *, system_prompt, user_prompt, response_model):
                self.called = True
                return response_model.model_validate(
                    {"proposal_markdown": "## Executive Summary\nSave 93% and invest €999,999 immediately."}
                )

        arguments = (
            {"scenario_code": "SAFE_TEST", "company_name": "Safe Test"},
            {"diagnostic_hypotheses": []},
            {"matched_case_studies": [], "supporting_research_snippets": []},
            {"guards": []},
            {"phase_1_actions": [{"action": "Audit the available evidence."}],
             "phase_2_actions": [{"action": "Run a scoped pilot after the audit."}],
             "phase_3_actions": [{"condition": "Scale only after verified results."}]},
        )
        deterministic = generate_hr_proposal(*arguments)
        optional_llm = ClearLLM()
        polished = generate_hr_proposal(*arguments, llm_client=optional_llm)
        self.assertTrue(optional_llm.called)
        self.assertTrue(optional_llm.assert_grounding_prompt)
        self.assertIn("Review the evidence", polished)
        self.assertNotEqual(polished, deterministic)
        self.assertEqual(generate_hr_proposal(*arguments, llm_client=UngroundedLLM()), deterministic)

    def test_step6_proposal_hides_engine_metadata_and_summarizes_shared_gates(self) -> None:
        scope = {
            "site": "milan",
            "cohort": "engineering_workforce",
            "tenure": "new_or_early_tenure",
            "window": "intake",
        }
        prerequisite = (
            "Complete the diagnostic and verify the proposed mechanism in this exact scope. "
            "Confirm missing or dependent observations against independent records."
        )
        phase_one_action = "Compare exits and role expectations across comparable teams."
        proposal = generate_hr_proposal(
            {
                "scenario_code": "FORMAT_TEST",
                "company_name": "Example Works",
                "industry_raw": "Industrial technology",
                "healthy_baselines": [{
                    "asset_or_cohort_name": "Tenured workforce",
                    "evidence": "Experienced technicians rarely leave.",
                    "do_not_touch_scope": "Keep the proven retention practices in place.",
                }],
                "filtered_noise_items": [{
                    "inferred_mismatched_action_or_topic": "Promotional traffic",
                    "raw_excerpt": "/client_intake_case/marketing/offer",
                    "reason_filtered": "This external campaign claim is unrelated to employee retention.",
                }],
                "leadership_requests": [],
            },
            {
                "scenario_code": "FORMAT_TEST",
                "intake": {"observations": [{
                    "signal": "early_attrition",
                    "scope": scope,
                    "text": "Several recent hires left within their first year.",
                }]},
            },
            {
                "matched_case_studies": [],
                "supporting_research_snippets": [{
                    "source_id": "bauer_2007",
                    "finding": "Structured onboarding supports role clarity.",
                }],
            },
            {
                "guards": [],
                "decisions": [{"rule": "expectation_drift", "scope": scope, "decision": "deferred", "reason": "Wait for cohort-level evidence."}],
            },
            {
                "diagnosed_root_causes": [{
                    "hypothesis": "Expectation drift may contribute to early exits",
                    "status": "plausible",
                    "scope": scope,
                }],
                "phase_1_actions": [{"action": phase_one_action, "scope": scope}],
                "phase_2_actions": [
                    {"action": "Pilot an accurate role preview.", "scope": scope, "prerequisite": prerequisite, "pilot_design": "Ask new hires to review the draft."},
                    {"action": "Pilot manager coaching.", "scope": scope, "prerequisite": prerequisite},
                ],
                "phase_3_actions": [
                    {"condition": "Scale when early retention improves.", "scope": scope, "prerequisite": "Complete the scoped pilot and review the agreed measures."},
                    {"condition": "Expand after role clarity improves.", "scope": scope, "prerequisite": "Complete the scoped pilot and review the agreed measures."},
                ],
                "open_questions_and_hypotheses_for_client": [{"verify": phase_one_action, "dependent_families": ["employee_exits"]}],
                "strengths": "Experienced technicians rarely leave.",
            },
        )

        self.assertNotIn('{"', proposal)
        self.assertNotIn("client_internal_context.", proposal)
        self.assertNotIn("missing families:", proposal.casefold())
        self.assertNotIn("dependent families:", proposal.casefold())
        self.assertNotIn("status: plausible", proposal.casefold())
        self.assertNotIn("decision: conditional", proposal.casefold())
        self.assertNotIn("early_attrition", proposal)
        self.assertNotIn("bauer_2007", proposal)
        self.assertNotIn("/client_intake_case/", proposal)
        self.assertIn("(Milan — Engineering, new hires)", proposal)
        self.assertIn("Promotional Traffic (excluded)", proposal)
        self.assertIn("Tenured workforce", proposal)
        self.assertEqual(proposal.count("Complete the diagnostic and verify the proposed mechanism in this exact scope."), 1)
        self.assertEqual(proposal.count("Complete the scoped pilot and review the agreed measures."), 1)
        self.assertNotIn("### Questions for HR to confirm", proposal)
        self.assertNotIn("### Leadership requests", proposal)

    def test_verifier_builds_a_serializable_pipeline_trace(self) -> None:
        scenario_code = "VERIFIER_SMOKE_TEST"
        client_input = NormalizedClientInput(
            scenario_code=scenario_code,
            company_name="Synthetic client",
            industry_raw="General enterprise",
            sector_category=SectorCategory.GENERAL_ENTERPRISE,
        )
        diagnosis = DiagnosisResult(scenario_code=scenario_code)
        scored = ScoredCandidates(scenario_code=scenario_code)
        guardrails = GuardrailResult(scenario_code=scenario_code)
        phase_plan = PhasePlan(scenario_code=scenario_code)
        submission = ScenarioSubmission(scenario_code=scenario_code)

        report = verify_scenario_submission(
            submission,
            client_input,
            diagnosis,
            scored,
            guardrails,
            phase_plan,
            NormalizedCasesDB(),
        )

        self.assertTrue(report.passed)
        self.assertEqual(report.reasoning_trace["scenario_code"], scenario_code)
        self.assertEqual(
            set(report.reasoning_trace),
            {"scenario_code", "step1", "step2", "step3", "step4", "step5"},
        )
        json.dumps(report.model_dump(mode="json"))


if __name__ == "__main__":
    unittest.main()
