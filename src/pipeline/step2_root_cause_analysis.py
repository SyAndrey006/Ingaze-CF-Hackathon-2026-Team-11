"""
Module: step2_root_cause_analysis.py
Stage: Step 2 — Root Cause & Benchmark Analysis
Execution Type: Formula

Description:
    Deterministically evaluates `NormalizedClientInput` against the universal
    causal and threshold rules in `NormalizedRulesDB`. Separates true underlying
    cross-pillar root causes from surface symptoms, compares T0 telemetry against
    sector peer benchmarks, locks in healthy baselines ("do not touch"), and
    computes cultural readiness + active blockers for downstream guardrails.

Input:
    - client_input (NormalizedClientInput): Clean canonical signals, healthy
      baselines, asymmetries, and T0 telemetry from Step 1.
    - rules_db (NormalizedRulesDB): Validated universal rules from `normalized_rules.json`.

Output:
    - diagnosis (DiagnosisResult): Inferred root causes, explained surface symptoms,
      benchmark deviations, locked healthy baselines, cultural readiness profile,
      active blockers, and open client discovery hypotheses consumed by Steps 3, 4, 5, and 6.

TODO:
    1. Implement `evaluate_telemetry_benchmarks` to deterministically compare T0
       metrics against `sector_benchmarks` and `rules_db.metric_benchmark_thresholds`
       (handle `t0_telemetry is None` gracefully for narrative-only blind scenarios).
    2. Implement `infer_cross_pillar_root_causes` using `rules_db.symptom_to_root_cause_rules`
       so downstream symptoms (e.g., low applicant volume, early attrition) map to
       structural root causes while respecting `excluded_if_signals` and focus caps.
    3. Implement `assess_cultural_readiness` to detect active blockers (Say-Do Gap,
       workload burnout, management crisis) vs. healthy/ready internal cultures
       (high trust + organic ambassadors), locking healthy baselines into
       `locked_healthy_baselines` with zero company-name hardcoding.
"""

from __future__ import annotations

from typing import List

from src.schemas.domain_models import NormalizedRulesDB, SignalCode
from src.schemas.pipeline_models import (
    BenchmarkDeviation,
    CulturalReadinessAssessment,
    DiagnosedRootCause,
    DiagnosisResult,
    NormalizedClientInput,
)


def evaluate_telemetry_benchmarks(
    client_input: NormalizedClientInput,
    rules_db: NormalizedRulesDB,
) -> List[BenchmarkDeviation]:
    """
    Compare each available T0 client metric against `sector_benchmarks` and
    `rules_db.metric_benchmark_thresholds` to emit quantitative deviations and
    confirmed signals (both problem signals and healthy-baseline signals).
    """
    # TODO: 1. Return empty list cleanly if `client_input.t0_telemetry` is None.
    # TODO: 2. Resolve dot-paths from `rules_db.metric_benchmark_thresholds` against
    #          `t0_telemetry` and `sector_benchmarks`.
    # TODO: 3. Classify each metric as CRITICAL / WARNING / HEALTHY / OUTPERFORMING
    #          respecting metric polarity (higher-is-better vs. lower-is-better).
    raise NotImplementedError("TODO: Implement evaluate_telemetry_benchmarks")


def infer_cross_pillar_root_causes(
    confirmed_signals: List[SignalCode],
    client_input: NormalizedClientInput,
    rules_db: NormalizedRulesDB,
) -> List[DiagnosedRootCause]:
    """
    Deterministically fire `rules_db.symptom_to_root_cause_rules` to separate
    underlying structural root causes from downstream surface symptoms.
    """
    # TODO: 1. Match `required_signals` and verify none of `excluded_if_signals` are active.
    # TODO: 2. Compute confidence from `supporting_signals` overlap and attach affected cohorts
    #          plus supporting evidence quotes from `client_input.canonical_signals`.
    # TODO: 3. Deduplicate and avoid symptom stuffing (keep only well-supported root causes).
    raise NotImplementedError("TODO: Implement infer_cross_pillar_root_causes")


def assess_cultural_readiness(
    confirmed_signals: List[SignalCode],
    client_input: NormalizedClientInput,
) -> CulturalReadinessAssessment:
    """
    Evaluate internal cultural readiness (healthy trust + organic ambassadors vs.
    active Say-Do Gap / burnout / management crisis) to guide Steps 4 and 5.
    """
    # TODO: 1. Check active blocker signals (SAY_DO_GAP, WORKLOAD_BURNOUT, WEAK_MIDDLE_MANAGEMENT).
    # TODO: 2. Check healthy readiness signals (HEALTHY_AUTHENTIC_EVP, STRONG_INTERNAL_CULTURE_HEALTHY,
    #          ACTIVE_ORGANIC_AMBASSADORS_PRESENT).
    # TODO: 3. Set `advocacy_readiness_status` to READY_TO_ACCELERATE, DIAGNOSTICS_FIRST,
    #          or BLOCKED_UNTIL_STABILIZED with a transparent rationale.
    raise NotImplementedError("TODO: Implement assess_cultural_readiness")


def analyze_root_causes(
    client_input: NormalizedClientInput,
    rules_db: NormalizedRulesDB,
) -> DiagnosisResult:
    """
    Step 2 entrypoint: run deterministic benchmark evaluation, cross-pillar root
    cause inference, healthy-baseline locking, and readiness assessment.
    """
    # TODO: 1. Run `evaluate_telemetry_benchmarks(...)` and merge triggered signals with
    #          `client_input.canonical_signals`.
    # TODO: 2. Run `infer_cross_pillar_root_causes(...)` and `assess_cultural_readiness(...)`.
    # TODO: 3. Lock verified `healthy_baselines`, surface deterministic `open_data_hypotheses`
    #          (e.g., site variance checks, manager-level attrition clustering), and record `trace_log`.
    raise NotImplementedError("TODO: Implement Step 2 (analyze_root_causes)")
