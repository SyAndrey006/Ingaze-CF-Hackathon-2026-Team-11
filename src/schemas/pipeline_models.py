"""Typed Pydantic contracts for normalized inputs and audit utilities.

The live graph-driven orchestrator passes JSON-compatible dictionaries between
Steps 2-5. These models define Step 1 output and reusable typed objects consumed
by the verifier and schema-level tests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from src.schemas.domain_models import (
    ActionCategory,
    GuardrailRoute,
    HRPillar,
    PhaseNumber,
    ResearchSnippet,
    SectorCategory,
    SectorPeerBenchmarks,
    SignalCode,
    TelemetrySnapshot,
    WorkforceArchetype,
)


# =============================================================================
# Pipeline Input Bundle (Raw Scenario + Optional T0 Telemetry)
# =============================================================================


class RawScenarioBundle(BaseModel):
    """Unprocessed single client scenario loaded from the sandbox JSON files."""

    scenario_code: str = Field(..., description="Unique scenario identifier (join key).")
    raw_scenario: Dict[str, Any] = Field(
        ...,
        description="Raw scenario dict from `company_scenarios_to_diagnose`.",
    )
    t0_telemetry: Optional[TelemetrySnapshot] = Field(
        default=None,
        description="Optional T0 quantitative telemetry joined via `scenario_code`.",
    )
    sector_benchmarks: Optional[SectorPeerBenchmarks] = Field(
        default=None,
        description="Optional sector peer benchmarks joined via `scenario_code`.",
    )


# =============================================================================
# Step 1 Output: Normalized Client Input (AI + Noise Gate)
# =============================================================================


class ExtractedSignal(BaseModel):
    """Canonical signal mapped from raw client narrative or platform signals."""

    signal_code: SignalCode = Field(..., description="Canonical problem/symptom/readiness tag.")
    evidence_quote: str = Field(..., description="Grounded quote or metric supporting this signal.")
    source_stream: Literal["outside_in_platform", "inside_out_client", "t0_telemetry"] = Field(
        ..., description="Which intake stream provided the evidence."
    )
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(default="MEDIUM")
    affected_cohorts: List[str] = Field(
        default_factory=list,
        description="Specific hubs, sites, or role cohorts affected (empty means company-wide).",
    )


class FilteredNoiseItem(BaseModel):
    """Contaminated, unverified, or out-of-scope data stripped by Step 1 Noise Gate."""

    raw_excerpt: str = Field(..., description="Noisy or contaminated snippet from raw feed.")
    inferred_mismatched_action_or_topic: str = Field(
        ..., description="What false intervention/topic the noise would have triggered."
    )
    reason_filtered: str = Field(
        ..., description="Why this row was stripped (e.g., unverified external pilot artifact, sector mismatch)."
    )


class HealthyBaseline(BaseModel):
    """Verified healthy metric, asset, or cohort that MUST NOT be disrupted."""

    asset_or_cohort_name: str = Field(..., description="E.g., compensation band, flagship hub, tenured cohort.")
    evidence: str = Field(..., description="Quantified evidence proving health (e.g., 82nd pct pay, 94% retention).")
    related_signal: SignalCode = Field(..., description="Canonical healthy signal code.")
    do_not_touch_scope: str = Field(
        ..., description="Explicit boundary of what must be preserved without overhaul."
    )


class CohortSiteAsymmetry(BaseModel):
    """Explicit divergence between healthy and struggling sites, hubs, or subpopulations."""

    struggling_segment: str = Field(..., description="Affected hubs, facilities, or cohorts.")
    struggling_evidence: str = Field(..., description="Metrics/symptoms in the struggling segment.")
    healthy_comparison_segment: str = Field(..., description="High-performing comparison cohort or hub.")
    healthy_evidence: str = Field(..., description="Metrics demonstrating health in the comparison segment.")


class LeadershipRequest(BaseModel):
    """Executive or stakeholder proposal extracted for deterministic guardrail evaluation."""

    stakeholder_role: str = Field(..., description="E.g., CEO, VP Engineering, Marketing Director, External Agency.")
    requested_action_text: str = Field(..., description="Raw summary of what the stakeholder wants to do.")
    inferred_action_category: ActionCategory = Field(
        ..., description="Mapped canonical action category for Steps 3 & 4."
    )
    requested_urgency: Literal["IMMEDIATE_PHASE_1", "STANDARD", "UNSPECIFIED"] = Field(default="UNSPECIFIED")
    target_scope: str = Field(default="company-wide", description="Hubs/cohorts targeted by the request.")


class NormalizedClientInput(BaseModel):
    """Output contract of Step 1 (`step1_normalize_input.py`) consumed by Steps 2, 4, and 6."""

    scenario_code: str = Field(...)
    company_name: str = Field(...)
    industry_raw: str = Field(...)
    sector_category: SectorCategory = Field(...)
    workforce_archetypes: List[WorkforceArchetype] = Field(default_factory=list)
    headcount: Optional[int] = Field(default=None, ge=1)
    locations_count: Optional[int] = Field(default=None, ge=1)
    workforce_target_summary: str = Field(default="")
    declared_evp: str = Field(default="")
    canonical_signals: List[ExtractedSignal] = Field(default_factory=list)
    filtered_noise_items: List[FilteredNoiseItem] = Field(default_factory=list)
    healthy_baselines: List[HealthyBaseline] = Field(default_factory=list)
    cohort_site_asymmetries: List[CohortSiteAsymmetry] = Field(default_factory=list)
    leadership_requests: List[LeadershipRequest] = Field(default_factory=list)
    budget_and_cfo_constraints: List[str] = Field(default_factory=list)
    t0_telemetry: Optional[TelemetrySnapshot] = Field(default=None)
    sector_benchmarks: Optional[SectorPeerBenchmarks] = Field(default=None)


# =============================================================================
# Step 2 Output: Root Cause & Benchmark Analysis (Formula)
# =============================================================================


class BenchmarkDeviation(BaseModel):
    """Deterministic comparison of a single client T0 metric against sector peer benchmark."""

    metric_name: str = Field(...)
    client_value: float = Field(...)
    benchmark_value: float = Field(...)
    delta: float = Field(..., description="Signed difference (`client_value - benchmark_value`).")
    status: Literal["CRITICAL", "WARNING", "HEALTHY", "OUTPERFORMING"] = Field(...)
    triggered_signal: Optional[SignalCode] = Field(default=None)


class DiagnosedRootCause(BaseModel):
    """Inferred structural root cause separated from surface symptoms."""

    root_cause_code: SignalCode = Field(...)
    primary_pillar: HRPillar = Field(...)
    rule_id: str = Field(..., description="ID of the rule from `normalized_rules.json` that inferred this cause.")
    explained_surface_symptoms: List[SignalCode] = Field(default_factory=list)
    affected_cohorts: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    supporting_snippet_nos: List[int] = Field(default_factory=list)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    plain_english_summary: str = Field(default="")


class CulturalReadinessAssessment(BaseModel):
    """Deterministic readiness profile governing advocacy acceleration vs. deferral."""

    is_culture_healthy: bool = Field(default=False)
    has_active_say_do_gap: bool = Field(default=False)
    has_active_burnout_or_mgmt_crisis: bool = Field(default=False)
    has_existing_organic_ambassadors: bool = Field(default=False)
    advocacy_readiness_status: Literal["READY_TO_ACCELERATE", "DIAGNOSTICS_FIRST", "BLOCKED_UNTIL_STABILIZED"] = Field(
        default="DIAGNOSTICS_FIRST"
    )
    readiness_rationale: str = Field(default="")


class DiagnosisResult(BaseModel):
    """Output contract of Step 2 (`step2_root_cause_analysis.py`) consumed by Steps 3, 4, 5, and 6."""

    scenario_code: str = Field(...)
    inferred_root_causes: List[DiagnosedRootCause] = Field(default_factory=list)
    surface_symptoms_explained: List[SignalCode] = Field(default_factory=list)
    benchmark_deviations: List[BenchmarkDeviation] = Field(default_factory=list)
    locked_healthy_baselines: List[HealthyBaseline] = Field(default_factory=list)
    cultural_readiness: CulturalReadinessAssessment = Field(default_factory=CulturalReadinessAssessment)
    active_blockers: List[SignalCode] = Field(default_factory=list)
    all_confirmed_signals: List[SignalCode] = Field(default_factory=list)
    open_data_hypotheses: List[str] = Field(
        default_factory=list,
        description="Concrete HRIS/ATS/scheduling questions to verify with the client.",
    )
    trace_log: List[str] = Field(default_factory=list)


# =============================================================================
# Step 3 Output: Conditions & Score System (Formula)
# =============================================================================


class ScoreBreakdown(BaseModel):
    """Transparent component scores summing to an action's or case's total score."""

    root_cause_overlap_score: float = Field(default=0.0, ge=0.0, le=1.0)
    workforce_fit_score: float = Field(default=0.0, ge=0.0, le=1.0)
    sector_fit_score: float = Field(default=0.0, ge=0.0, le=1.0)
    roi_evidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    cfo_auditability_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ScoredAction(BaseModel):
    """Candidate HR intervention ranked by Step 3 formula scoring."""

    action_id: str = Field(..., description="Unique candidate action ID for traceability.")
    action_title: str = Field(..., description="Clear action label.")
    action_category: ActionCategory = Field(...)
    source_type: Literal["UNIVERSAL_RULE", "CASE_PRECEDENT", "EXECUTIVE_REQUEST", "COHORT_ORIGINAL"] = Field(...)
    target_root_causes: List[SignalCode] = Field(default_factory=list)
    target_cohorts: List[str] = Field(default_factory=list)
    applicable_sectors: List[SectorCategory] = Field(default_factory=list)
    applicable_workforces: List[WorkforceArchetype] = Field(default_factory=list)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    total_score: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_roi_summary: str = Field(default="", description="Quantified % or EUR ROI precedent.")
    supporting_case_names: List[str] = Field(default_factory=list)
    supporting_snippet_nos: List[int] = Field(default_factory=list)
    stakeholder_origin: Optional[str] = Field(
        default=None,
        description="Set if candidate originated from a leadership request.",
    )
    requested_urgency: Optional[Literal["IMMEDIATE_PHASE_1", "STANDARD", "UNSPECIFIED"]] = Field(default=None)


class MatchedCaseScore(BaseModel):
    """Ranked historical case study from `normalized_cases.json` (Top-3 selected)."""

    case_id: str = Field(...)
    case_name: str = Field(...)
    sector_category: SectorCategory = Field(...)
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    matched_problem_tags: List[SignalCode] = Field(default_factory=list)
    measured_roi_summary: str = Field(...)
    quantified_roi_highlights: List[str] = Field(default_factory=list)


class ScoredCandidates(BaseModel):
    """Output contract of Step 3 (`step3_conditions_scoring.py`) consumed by Steps 4 and 6."""

    scenario_code: str = Field(...)
    ranked_actions: List[ScoredAction] = Field(default_factory=list)
    top_matched_cases: List[MatchedCaseScore] = Field(
        default_factory=list,
        description="Top-3 matched historical Case Studies.",
    )
    selected_research_snippets: List[ResearchSnippet] = Field(default_factory=list)
    trace_log: List[str] = Field(default_factory=list)


# =============================================================================
# Step 4 Output: Guardrail Check (Formula)
# =============================================================================


class RoutedAction(BaseModel):
    """Candidate action annotated with its deterministic guardrail route and audit reason."""

    action: ScoredAction = Field(...)
    route: GuardrailRoute = Field(...)
    triggered_rule_ids: List[str] = Field(default_factory=list)
    reason: str = Field(..., description="Auditable plain-English explanation of routing decision.")
    deferred_min_phase: Optional[PhaseNumber] = Field(
        default=None,
        description="Minimum phase allowed when route == PAUSE.",
    )
    unlock_condition: Optional[str] = Field(
        default=None,
        description="Condition that must be satisfied before executing a PAUSEd action.",
    )


class GuardrailResult(BaseModel):
    """Output contract of Step 4 (`step4_guardrail_check.py`) routing actions to Step 5 and Step 6."""

    scenario_code: str = Field(...)
    passed_actions: List[RoutedAction] = Field(
        default_factory=list,
        description="Route=PASS -> flows to Step 5 (Phase Plan).",
    )
    paused_actions: List[RoutedAction] = Field(
        default_factory=list,
        description="Route=PAUSE -> flows to Step 5 (Phase Plan) with minimum phase / unlock gate.",
    )
    blocked_actions: List[RoutedAction] = Field(
        default_factory=list,
        description="Route=BLOCKED -> flows directly to Step 6 (HR Proposal).",
    )
    do_not_touch_items: List[RoutedAction] = Field(
        default_factory=list,
        description="Route=DO_NOT_TOUCH -> flows directly to Step 6 (HR Proposal).",
    )
    filtered_noise_traps: List[FilteredNoiseItem] = Field(
        default_factory=list,
        description="Noise rows stripped in Step 1 forwarded to Step 6 for transparent guardrail reporting.",
    )
    trace_log: List[str] = Field(default_factory=list)


# =============================================================================
# Step 5 Output: Phase Plan (Formula)
# =============================================================================


class PlannedAction(BaseModel):
    """Action assigned to a concrete execution phase with sequencing metadata."""

    action: ScoredAction = Field(...)
    assigned_phase: PhaseNumber = Field(...)
    was_paused: bool = Field(default=False)
    was_accelerated: bool = Field(default=False)
    sequencing_reason: str = Field(..., description="Why this action belongs in this phase.")
    unlock_condition: Optional[str] = Field(default=None)


class PhasePlan(BaseModel):
    """Output contract of Step 5 (`step5_phase_planner.py`) consumed by Step 6."""

    scenario_code: str = Field(...)
    phase_1_actions: List[PlannedAction] = Field(default_factory=list)
    phase_2_actions: List[PlannedAction] = Field(default_factory=list)
    phase_3_actions: List[PlannedAction] = Field(default_factory=list)
    sequencing_rationale: List[str] = Field(default_factory=list)
    trace_log: List[str] = Field(default_factory=list)


# =============================================================================
# Post-Generation Verification Report (Utility)
# =============================================================================


class VerificationReport(BaseModel):
    """Output contract of `src/utils/verifier.py` validating Step 6 output before export."""

    scenario_code: str = Field(...)
    passed: bool = Field(default=False)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    reasoning_trace: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inspectable end-to-end reasoning trace for live judging demo.",
    )
