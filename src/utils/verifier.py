"""
Module: verifier.py
Stage: Step 6 Post-Generation Verifier & Trace Builder
Execution Type: Formula

Description:
    Deterministically verifies that the AI-generated `ScenarioSubmission` from
    Step 6 strictly honors every upstream Formula decision (no blocked or
    do-not-touch actions leaked into `phase_1/2/3_actions`, no paused actions
    promoted ahead of `deferred_min_phase`, exact Top-3 sandbox case names, and
    clean focus bounds) and constructs an inspectable end-to-end reasoning trace.

Input:
    - submission (ScenarioSubmission): Plain-English proposal produced by Step 6.
    - client_input (NormalizedClientInput): Step 1 normalized client context & filtered noise.
    - diagnosis (DiagnosisResult): Step 2 root causes & locked healthy baselines.
    - scored (ScoredCandidates): Step 3 ranked actions & Top-3 matched cases.
    - guardrails (GuardrailResult): Step 4 PASS / PAUSE / BLOCKED / DO_NOT_TOUCH routing.
    - phase_plan (PhasePlan): Step 5 verified phase assignments.
    - cases_db (NormalizedCasesDB): Validated 11 sandbox case study names.

Output:
    - report (VerificationReport): Pass/fail audit errors, warnings, and structured
      reasoning trace consumed by `src/main.py` before exporting `submission.json`.

TODO:
    1. Implement hard guardrail leak checks: fail verification if any `BLOCKED` action,
       `DO_NOT_TOUCH` overhaul, or `filtered_noise_items` topic appears inside
       `phase_1_actions`, `phase_2_actions`, or `phase_3_actions`.
    2. Implement contract & quality checks mirroring `starter_baseline_and_validator.py`:
       non-empty required lists, `len(diagnosed_root_causes) <= 6`, `len(matched_case_studies) <= 3`,
       all matched cases exist in `cases_db`, and phase progression is non-degenerate.
    3. Build a concise JSON-serializable reasoning trace (`Step 1 -> Step 6`) for
       live Sunday Q&A demo auditability (CFO-ready evidence trail).
"""

from __future__ import annotations

from typing import Any, Dict

from src.schemas.domain_models import NormalizedCasesDB
from src.schemas.pipeline_models import (
    DiagnosisResult,
    GuardrailResult,
    NormalizedClientInput,
    PhasePlan,
    ScoredCandidates,
    VerificationReport,
)
from src.schemas.submission_models import ScenarioSubmission


def build_reasoning_trace(
    client_input: NormalizedClientInput,
    diagnosis: DiagnosisResult,
    scored: ScoredCandidates,
    guardrails: GuardrailResult,
    phase_plan: PhasePlan,
) -> Dict[str, Any]:
    """
    Assemble an inspectable, step-by-step audit trace summarizing signal extraction,
    noise filtering, root-cause rules fired, scoring breakdown, guardrail routing,
    and phase sequencing decisions.
    """
    # TODO: 1. Aggregate `trace_log` entries and key IDs from Steps 1-5 into a clean dict.
    # TODO: 2. Include counts of passed/paused/blocked/do-not-touch items and Top-3 case scores.
    # TODO: 3. Return JSON-serializable dict for CLI inspection or demo display.
    raise NotImplementedError("TODO: Implement build_reasoning_trace")


def verify_scenario_submission(
    submission: ScenarioSubmission,
    client_input: NormalizedClientInput,
    diagnosis: DiagnosisResult,
    scored: ScoredCandidates,
    guardrails: GuardrailResult,
    phase_plan: PhasePlan,
    cases_db: NormalizedCasesDB,
) -> VerificationReport:
    """
    Run deterministic sanity and guardrail-fidelity checks on Step 6's
    `ScenarioSubmission` before allowing export to `submission.json`.
    """
    # TODO: 1. Verify no BLOCKED, DO_NOT_TOUCH, or filtered noise concepts leaked into Phase 1/2/3.
    # TODO: 2. Verify all `matched_case_studies` match valid `cases_db` names and count <= 3.
    # TODO: 3. Verify phase sequencing fidelity (paused items do not appear in disallowed earlier phases).
    # TODO: 4. Attach `build_reasoning_trace(...)` and return `VerificationReport`.
    raise NotImplementedError("TODO: Implement verify_scenario_submission")
