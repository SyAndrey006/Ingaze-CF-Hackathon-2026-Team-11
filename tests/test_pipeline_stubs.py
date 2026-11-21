"""
Module: test_pipeline_stubs.py
Stage: Tests (Schema Validation, Noise Filtering & Guardrail Blocking Stubs)
Execution Type: Utility

Description:
    Provides placeholder unit tests verifying that all Pydantic schemas and
    placeholder normalized JSON templates validate cleanly today, alongside
    TODO-marked test skeletons for Step 1 noise filtering, Step 4 guardrail
    blocking/pausing/do-not-touch routing, Step 5 phase sequencing, and Step 6
    submission contract validation.

Input:
    - Pydantic models from `src/schemas/*`.
    - Placeholder JSONs from `database/normalized/*.json`.
    - Pipeline stage entrypoints from `src/pipeline/*` and `src/utils/verifier.py`.

Output:
    - Passing schema smoke tests now and runnable TDD targets as each team
      member replaces `NotImplementedError` stubs with real implementations.

TODO:
    1. Replace `unittest.SkipTest` / `assertRaises(NotImplementedError)` assertions
       with full behavioral assertions as Steps 1-6 are implemented.
    2. Add synthetic company-agnostic test fixtures covering:
       (a) noisy cross-industry review export filtering,
       (b) premature external advocacy paused under active Say-Do Gap / burnout,
       (c) advocacy acceleration when internal culture is healthy & organic ambassadors exist,
       (d) healthy baseline preservation (`DO_NOT_TOUCH`).
    3. Add an end-to-end contract test validating `SubmissionPayload` against
       `starter_baseline_and_validator.validate_submission`.
"""

from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from src.schemas.domain_models import (
    ActionCategory,
    GuardrailRoute,
    NormalizedCasesDB,
    NormalizedRulesDB,
    SectorCategory,
    SignalCode,
    TelemetrySnapshot,
    WorkforceArchetype,
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

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_PLACEHOLDER_PATH = BASE_DIR / "database" / "normalized" / "normalized_rules.json"
CASES_PLACEHOLDER_PATH = BASE_DIR / "database" / "normalized" / "normalized_cases.json"


class TestSchemaAndPlaceholderValidation(unittest.TestCase):
    """Smoke tests confirming all Pydantic schemas and JSON placeholders load cleanly."""

    def test_placeholder_normalized_rules_json_matches_schema(self) -> None:
        raw_text = RULES_PLACEHOLDER_PATH.read_text(encoding="utf-8")
        rules_db = NormalizedRulesDB.model_validate_json(raw_text)
        self.assertEqual(rules_db.schema_version, "1.0.0")
        self.assertIsInstance(rules_db.symptom_to_root_cause_rules, list)

    def test_placeholder_normalized_cases_json_matches_schema(self) -> None:
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


class TestPipelineBehaviorPlaceholders(unittest.TestCase):
    """TODO-driven unit test placeholders for Steps 1-6."""

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

            normalized_path = output_dir / "input_normalized.json"
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
        # TODO: Implement once `step4_guardrail_check.apply_guardrail_checks` is built.
        # Verify:
        #   - RETAIL_SHIFT_ROTATION for DESK_BASED_TECH_SPECIALIST -> GuardrailRoute.BLOCKED
        #   - AMBASSADOR_SELECTION_ENABLEMENT with active SAY_DO_GAP -> GuardrailRoute.PAUSE (min Phase 3)
        #   - COMPENSATION_BAND_OVERHAUL with COMPETITIVE_COMPENSATION_HEALTHY -> GuardrailRoute.DO_NOT_TOUCH
        _ = (
            ActionCategory.RETAIL_SHIFT_ROTATION,
            GuardrailRoute.BLOCKED,
            SectorCategory.FINTECH_PAYMENTS,
            SignalCode.SAY_DO_GAP,
            WorkforceArchetype.DESK_BASED_TECH_SPECIALIST,
            NormalizedClientInput,
            DiagnosisResult,
            ScoredAction,
            ScoredCandidates,
            GuardrailResult,
            PhasePlan,
        )
        self.skipTest("TODO: Implement Step 4 guardrail routing test once Step 4 is implemented.")

    def test_step5_phase_planner_accelerates_advocacy_when_culture_healthy(self) -> None:
        # TODO: Implement once `step5_phase_planner.build_phase_plan` is built.
        # Verify that when `HEALTHY_AUTHENTIC_EVP` and `ACTIVE_ORGANIC_AMBASSADORS_PRESENT`
        # are active (with zero Say-Do Gap/burnout), advocacy/tracking accelerates instead
        # of waiting behind irrelevant cultural-repair prerequisites.
        self.skipTest("TODO: Implement Step 5 phase acceleration test once Step 5 is implemented.")


if __name__ == "__main__":
    unittest.main()
