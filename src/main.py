"""
Module: main.py
Stage: CLI End-to-End Orchestrator (Offline + Online Steps 1-6 + Verifier)
Execution Type: Utility

Description:
    Provides the unified CLI entrypoint for the Ingaze HR Strategy Recommendation
    Engine. Wires the complete end-to-end data flow: optionally triggers one-time
    offline indexing (`normalize_databases.py`), loads validated rules and case
    databases (`database_loader.py`), executes Online Steps 1-6 for each client
    scenario, runs the deterministic post-generation verifier (`verifier.py`),
    and exports `submission.json`.

Input:
    - CLI arguments (`--dataset`, `--snapshots`, `--extra-scenario`, `--rules-db`,
      `--cases-db`, `--rebuild-offline`, `--out`, `--trace-out`, `--provider`, `--model`).
    - Raw sandbox JSONs (`data/ingaze_sandbox_dataset.json`,
      `data/ingaze_synthetic_analytics_snapshots.json`).

Output:
    - submission (SubmissionPayload): Written as JSON to `submission.json` (ready for
      `python starter_baseline_and_validator.py --validate submission.json`).
    - Optional reasoning trace JSON for live Sunday judging demo auditability.

TODO:
    1. Wire optional trace export (`--trace-out`) printing or saving each scenario's
       `VerificationReport.reasoning_trace` for the live demo.
    2. Add clean CLI error reporting when verification fails (`not report.passed`) or
       when offline normalized DBs are missing/placeholder-only.
    3. Verify end-to-end execution across all 3 sandbox scenarios plus any live
       `--extra-scenario` blind test with zero hardcoded company branches.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Tuple

from src.offline.database_loader import (
    load_normalized_databases,
    load_raw_scenario_bundles,
)
from src.offline.normalize_databases import run_offline_normalization
from src.pipeline.step1_normalize_input import normalize_client_input
from src.pipeline.step2_root_cause_analysis import analyze_root_causes
from src.pipeline.step3_conditions_scoring import score_candidates_and_cases
from src.pipeline.step4_guardrail_check import apply_guardrail_checks
from src.pipeline.step5_phase_planner import build_phase_plan
from src.pipeline.step6_hr_proposal import generate_hr_proposal
from src.schemas.domain_models import NormalizedCasesDB, NormalizedRulesDB
from src.schemas.pipeline_models import (
    DiagnosisResult,
    GuardrailResult,
    NormalizedClientInput,
    PhasePlan,
    RawScenarioBundle,
    ScoredCandidates,
    VerificationReport,
)
from src.schemas.submission_models import ScenarioSubmission, SubmissionPayload
from src.utils.llm_client import LLMConfig, StructuredLLMClient
from src.utils.verifier import verify_scenario_submission

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_PATH = BASE_DIR / "data" / "ingaze_sandbox_dataset.json"
DEFAULT_SNAPSHOTS_PATH = BASE_DIR / "data" / "ingaze_synthetic_analytics_snapshots.json"
DEFAULT_TELEMETRY_DOC_PATH = BASE_DIR / "docs" / "ANALYTICS_TELEMETRY_DICTIONARY.md"
DEFAULT_RULES_PATH = BASE_DIR / "data" / "normalized" / "normalized_rules.json"
DEFAULT_CASES_PATH = BASE_DIR / "data" / "normalized" / "normalized_cases.json"
DEFAULT_SUBMISSION_PATH = BASE_DIR / "submission.json"

TEAM_NAME = "Team 11 — Ingaze Hybrid Strategy Engine"
ARCHITECTURE_PARADIGM = (
    "Hybrid Deterministic + AI Pipeline (Offline AI Rule/Case Normalization -> "
    "AI Noise Gate -> Formula Root-Cause, Scoring, 4-Way Guardrails & Phase Planner -> "
    "Grounded AI HR Proposal + Deterministic Verifier)"
)


def run_scenario_pipeline(
    raw_bundle: RawScenarioBundle,
    rules_db: NormalizedRulesDB,
    cases_db: NormalizedCasesDB,
    llm_client: StructuredLLMClient,
) -> Tuple[ScenarioSubmission, VerificationReport]:
    """
    Execute the complete 6-step online pipeline + deterministic verifier for a
    single incoming client scenario.
    """
    # Step 1 [AI + Noise Gate]: Raw scenario + T0 telemetry -> NormalizedClientInput
    client_input: NormalizedClientInput = normalize_client_input(
        raw_bundle=raw_bundle,
        llm_client=llm_client,
    )

    # Step 2 [Formula]: NormalizedClientInput + Rules -> DiagnosisResult
    diagnosis: DiagnosisResult = analyze_root_causes(
        client_input=client_input,
        rules_db=rules_db,
    )

    # Step 3 [Formula]: DiagnosisResult + Cases + Rules -> ScoredCandidates & Top-3 Cases
    scored: ScoredCandidates = score_candidates_and_cases(
        diagnosis=diagnosis,
        client_input=client_input,
        cases_db=cases_db,
        rules_db=rules_db,
    )

    # Step 4 [Formula]: ScoredCandidates + Client Context + Rules -> 4-Way GuardrailResult
    guardrails: GuardrailResult = apply_guardrail_checks(
        scored=scored,
        client_input=client_input,
        diagnosis=diagnosis,
        rules_db=rules_db,
    )

    # Step 5 [Formula]: PASS + PAUSE actions + Readiness + Rules -> Dynamic PhasePlan
    phase_plan: PhasePlan = build_phase_plan(
        guardrails=guardrails,
        diagnosis=diagnosis,
        rules_db=rules_db,
    )

    # Step 6 [AI]: Verified PhasePlan + Blocked/DoNotTouch + Top-3 Cases -> Plain-English Proposal
    scenario_submission: ScenarioSubmission = generate_hr_proposal(
        client_input=client_input,
        diagnosis=diagnosis,
        scored=scored,
        guardrails=guardrails,
        phase_plan=phase_plan,
        llm_client=llm_client,
    )

    # Post-Generation Sanity Verifier [Formula]: Enforce zero guardrail leaks & schema fidelity
    report: VerificationReport = verify_scenario_submission(
        submission=scenario_submission,
        client_input=client_input,
        diagnosis=diagnosis,
        scored=scored,
        guardrails=guardrails,
        phase_plan=phase_plan,
        cases_db=cases_db,
    )

    return scenario_submission, report


def run_all_scenarios(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    snapshots_path: Optional[Path] = DEFAULT_SNAPSHOTS_PATH,
    extra_scenario_path: Optional[Path] = None,
    rules_path: Path = DEFAULT_RULES_PATH,
    cases_path: Path = DEFAULT_CASES_PATH,
    output_path: Path = DEFAULT_SUBMISSION_PATH,
    rebuild_offline: bool = False,
    llm_config: Optional[LLMConfig] = None,
) -> Tuple[SubmissionPayload, List[VerificationReport]]:
    """
    Orchestrate offline DB initialization (if requested/missing), load normalized
    databases and active scenarios, run Steps 1-6 + verifier across all scenarios,
    and write `submission.json`.
    """
    llm_client = StructuredLLMClient(config=llm_config)

    # Offline Indexing [AI — runs once when rebuilding or if DBs do not exist yet]
    if rebuild_offline or not rules_path.exists() or not cases_path.exists():
        rules_db, cases_db = run_offline_normalization(
            sandbox_dataset_path=dataset_path,
            snapshots_dataset_path=snapshots_path,
            output_rules_path=rules_path,
            output_cases_path=cases_path,
            llm_client=llm_client,
            telemetry_dictionary_path=DEFAULT_TELEMETRY_DOC_PATH,
        )
    else:
        rules_db, cases_db = load_normalized_databases(
            rules_path=rules_path,
            cases_path=cases_path,
        )

    # Load active client scenarios + optional T0 analytics snapshots
    scenario_bundles: List[RawScenarioBundle] = load_raw_scenario_bundles(
        sandbox_dataset_path=dataset_path,
        snapshots_dataset_path=snapshots_path,
        extra_scenario_path=extra_scenario_path,
    )

    scenario_submissions: List[ScenarioSubmission] = []
    verification_reports: List[VerificationReport] = []

    for bundle in scenario_bundles:
        submission, report = run_scenario_pipeline(
            raw_bundle=bundle,
            rules_db=rules_db,
            cases_db=cases_db,
            llm_client=llm_client,
        )
        scenario_submissions.append(submission)
        verification_reports.append(report)

    payload = SubmissionPayload(
        team_name=TEAM_NAME,
        chosen_architecture_paradigm=ARCHITECTURE_PARADIGM,
        scenarios=scenario_submissions,
    )

    # TODO: Gate export on `all(r.passed for r in verification_reports)` and optionally
    #       write `verification_reports` trace logs for live demo inspection.
    output_path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    return payload, verification_reports


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser for running the strategy engine."""
    parser = argparse.ArgumentParser(
        description="Ingaze HR Strategy Recommendation Engine — Hybrid Deterministic + AI Pipeline."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS_PATH)
    parser.add_argument("--extra-scenario", "--blind-scenario", dest="extra_scenario", type=Path, default=None)
    parser.add_argument("--rules-db", type=Path, default=DEFAULT_RULES_PATH)
    parser.add_argument("--cases-db", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_SUBMISSION_PATH)
    parser.add_argument(
        "--rebuild-offline",
        action="store_true",
        help="Force re-running one-time AI offline normalization of rules & cases.",
    )
    parser.add_argument("--provider", choices=["openai", "openrouter", "gemini"], default="openai")
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    return parser


def main() -> None:
    """CLI entrypoint."""
    args = build_arg_parser().parse_args()
    llm_config = LLMConfig(provider=args.provider, model=args.model, temperature=0.0)
    run_all_scenarios(
        dataset_path=args.dataset,
        snapshots_path=args.snapshots,
        extra_scenario_path=args.extra_scenario,
        rules_path=args.rules_db,
        cases_path=args.cases_db,
        output_path=args.out,
        rebuild_offline=args.rebuild_offline,
        llm_config=llm_config,
    )


if __name__ == "__main__":
    main()
