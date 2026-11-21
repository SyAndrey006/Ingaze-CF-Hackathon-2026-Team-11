"""
Module: domain_models.py
Stage: Schemas (Shared Domain Ontology & Offline Database Models)
Execution Type: Schema

Description:
    Defines canonical Enums/Literals (HR pillars, universal signal codes,
    workforce archetypes, sector categories, action categories, guardrail routes,
    and phase numbers) alongside Pydantic models for telemetry snapshots and the
    two normalized offline JSON databases (`normalized_rules.json` and
    `normalized_cases.json`).

Input:
    - Raw domain knowledge and analytics snapshot structures from
      `database/ingaze_sandbox_dataset.json`,
      `database/ingaze_synthetic_analytics_snapshots.json`, and
      `docs/ANALYTICS_TELEMETRY_DICTIONARY.md`.

Output:
    - Typed Pydantic domain schemas consumed by `src/offline/*`,
      `src/pipeline/step1..step6`, and `src/utils/*`.

TODO:
    1. Refine or extend `SignalCode`, `ActionCategory`, and `WorkforceArchetype`
       literals if offline normalization discovers additional generalizable HR concepts.
    2. Add Pydantic field validators (e.g., percentage bounds 0-100, rating bounds 1-5,
       scoring weight sum == 1.0) once team agrees on final scoring math.
    3. Keep 100% of enum values and rule schemas company-agnostic (never encode
       company names or scenario codes as domain literals).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Canonical Domain Enums (Company-Agnostic HR Ontology)
# =============================================================================


class HRPillar(str, Enum):
    """The 4 interconnected Ingaze Employer Intelligence pillars."""

    EMPLOYER_BRANDING_REPUTATION = "EMPLOYER_BRANDING_REPUTATION"
    RECRUITING_TALENT_ATTRACTION = "RECRUITING_TALENT_ATTRACTION"
    EMPLOYEE_ADVOCACY = "EMPLOYEE_ADVOCACY"
    RETENTION_INTERNAL_CLIMATE = "RETENTION_INTERNAL_CLIMATE"


class SectorCategory(str, Enum):
    """Canonical industry sectors used for sector-fit matching and guardrails."""

    B2B_TECH_SAAS = "B2B_TECH_SAAS"
    FINTECH_PAYMENTS = "FINTECH_PAYMENTS"
    LOGISTICS_FREIGHT = "LOGISTICS_FREIGHT"
    RETAIL_OMNICHANNEL = "RETAIL_OMNICHANNEL"
    HEALTHCARE_CLINICAL = "HEALTHCARE_CLINICAL"
    BANKING_FINANCIAL_SERVICES = "BANKING_FINANCIAL_SERVICES"
    CLEANTECH_SUSTAINABILITY_BCORP = "CLEANTECH_SUSTAINABILITY_BCORP"
    GENERAL_ENTERPRISE = "GENERAL_ENTERPRISE"


class WorkforceArchetype(str, Enum):
    """Canonical workforce segments capturing device, channel, and physical realities."""

    DESK_BASED_TECH_SPECIALIST = "DESK_BASED_TECH_SPECIALIST"
    DESKLESS_FRONTLINE_LOGISTICS = "DESKLESS_FRONTLINE_LOGISTICS"
    DESKLESS_FRONTLINE_RETAIL = "DESKLESS_FRONTLINE_RETAIL"
    MULTISITE_CLINICAL_HEALTHCARE = "MULTISITE_CLINICAL_HEALTHCARE"
    EARLY_CAREER_GEN_Z = "EARLY_CAREER_GEN_Z"
    CORPORATE_HQ_ADMIN = "CORPORATE_HQ_ADMIN"
    MIXED_DISTRIBUTED = "MIXED_DISTRIBUTED"


class SignalCode(str, Enum):
    """Canonical problem, symptom, operational drag, and readiness signal codes."""

    # --- Reputation & EVP Signals (Pillar 1) ---
    SAY_DO_GAP = "SAY_DO_GAP"
    LOW_EMPLOYER_BRAND_ALIGNMENT = "LOW_EMPLOYER_BRAND_ALIGNMENT"
    MULTISITE_REPUTATION_VARIANCE = "MULTISITE_REPUTATION_VARIANCE"
    UNMONITORED_LOCAL_REVIEWS = "UNMONITORED_LOCAL_REVIEWS"
    LOW_PUBLIC_RATING = "LOW_PUBLIC_RATING"
    HEALTHY_AUTHENTIC_EVP = "HEALTHY_AUTHENTIC_EVP"

    # --- Recruiting & Funnel Signals (Pillar 2) ---
    MOBILE_PORTAL_FRICTION = "MOBILE_PORTAL_FRICTION"
    HIGH_APPLICATION_DROPOFF = "HIGH_APPLICATION_DROPOFF"
    GENERIC_BOILERPLATE_JDS = "GENERIC_BOILERPLATE_JDS"
    CHANNEL_WORKFORCE_MISMATCH = "CHANNEL_WORKFORCE_MISMATCH"
    HIGH_TIME_TO_HIRE = "HIGH_TIME_TO_HIRE"
    HIGH_EXTERNAL_AGENCY_DEPENDENCY = "HIGH_EXTERNAL_AGENCY_DEPENDENCY"
    FRAGMENTED_CANDIDATE_FEEDBACK = "FRAGMENTED_CANDIDATE_FEEDBACK"
    LOW_INBOUND_QUALIFIED_APPLICANTS = "LOW_INBOUND_QUALIFIED_APPLICANTS"
    MISSING_CANDIDATE_PERSONA_FIT = "MISSING_CANDIDATE_PERSONA_FIT"

    # --- Employee Advocacy & Content Signals (Pillar 3) ---
    LOW_CORPORATE_SOCIAL_ENGAGEMENT = "LOW_CORPORATE_SOCIAL_ENGAGEMENT"
    MANUAL_HR_SPREADSHEET_DRAG = "MANUAL_HR_SPREADSHEET_DRAG"
    MISSING_CFO_ROI_EMV_VISIBILITY = "MISSING_CFO_ROI_EMV_VISIBILITY"
    ACTIVE_ORGANIC_AMBASSADORS_PRESENT = "ACTIVE_ORGANIC_AMBASSADORS_PRESENT"
    PREMATURE_ADVOCACY_BACKLASH_RISK = "PREMATURE_ADVOCACY_BACKLASH_RISK"

    # --- Retention & Internal Climate Signals (Pillar 4) ---
    EARLY_FIRST_YEAR_ATTRITION = "EARLY_FIRST_YEAR_ATTRITION"
    WEAK_MIDDLE_MANAGEMENT = "WEAK_MIDDLE_MANAGEMENT"
    CAREER_PATH_OPACITY = "CAREER_PATH_OPACITY"
    WORKLOAD_BURNOUT = "WORKLOAD_BURNOUT"
    UNPREDICTABLE_SHIFT_SCHEDULING = "UNPREDICTABLE_SHIFT_SCHEDULING"
    HIGH_FINANCIAL_TURNOVER_RISK = "HIGH_FINANCIAL_TURNOVER_RISK"
    COHORT_OR_SITE_ASYMMETRY = "COHORT_OR_SITE_ASYMMETRY"

    # --- Healthy Baseline / Preservation Signals ---
    COMPETITIVE_COMPENSATION_HEALTHY = "COMPETITIVE_COMPENSATION_HEALTHY"
    HIGH_COHORT_RETENTION_HEALTHY = "HIGH_COHORT_RETENTION_HEALTHY"
    STRONG_OPERATIONAL_ASSETS_HEALTHY = "STRONG_OPERATIONAL_ASSETS_HEALTHY"
    STRONG_INTERNAL_CULTURE_HEALTHY = "STRONG_INTERNAL_CULTURE_HEALTHY"


class ActionCategory(str, Enum):
    """Canonical categories of HR strategy interventions (open to custom actions too)."""

    REPUTATION_AUDIT = "REPUTATION_AUDIT"
    CAREER_PORTAL_UX_AUDIT = "CAREER_PORTAL_UX_AUDIT"
    INTERNAL_360_LISTENING = "INTERNAL_360_LISTENING"
    CANDIDATE_PERSONA_CALIBRATION = "CANDIDATE_PERSONA_CALIBRATION"
    POST_INTERVIEW_SURVEY_DIGITIZATION = "POST_INTERVIEW_SURVEY_DIGITIZATION"
    MANAGER_COACHING_AND_LEVELING = "MANAGER_COACHING_AND_LEVELING"
    CAREER_PROGRESSION_FRAMEWORK = "CAREER_PROGRESSION_FRAMEWORK"
    EVP_REALIGNMENT = "EVP_REALIGNMENT"
    EVP_OVERHAUL_FROM_SCRATCH = "EVP_OVERHAUL_FROM_SCRATCH"
    MOBILE_FAST_APPLY_FLOW = "MOBILE_FAST_APPLY_FLOW"
    PERSONA_ALIGNED_JDS = "PERSONA_ALIGNED_JDS"
    TECHNICAL_LINKEDIN_STORYTELLING = "TECHNICAL_LINKEDIN_STORYTELLING"
    RETAIL_SHIFT_ROTATION = "RETAIL_SHIFT_ROTATION"
    COMPENSATION_BAND_OVERHAUL = "COMPENSATION_BAND_OVERHAUL"
    AMBASSADOR_SELECTION_ENABLEMENT = "AMBASSADOR_SELECTION_ENABLEMENT"
    AUTOMATED_AMBASSADOR_TRACKING = "AUTOMATED_AMBASSADOR_TRACKING"
    CFO_RISK_AND_EMV_DASHBOARD = "CFO_RISK_AND_EMV_DASHBOARD"
    COHORT_TARGETED_ORIGINAL_ACTION = "COHORT_TARGETED_ORIGINAL_ACTION"


class GuardrailRoute(str, Enum):
    """The 4 deterministic routing outcomes produced by Step 4 (Guardrail Check)."""

    PASS = "PASS"
    PAUSE = "PAUSE"
    BLOCKED = "BLOCKED"
    DO_NOT_TOUCH = "DO_NOT_TOUCH"


class PhaseNumber(int, Enum):
    """Sequenced implementation phases in the HR roadmap."""

    PHASE_1 = 1
    PHASE_2 = 2
    PHASE_3 = 3


# =============================================================================
# Quantitative Analytics Telemetry Models (Matches Synthetic Snapshots Schema)
# =============================================================================


class SiteRatingBreakdown(BaseModel):
    """Review volume and 1-5 rating for a single site, hub, or segment."""

    reviews: int = Field(..., ge=0, description="Number of reviews for this site/segment.")
    rating_5: float = Field(..., ge=1.0, le=5.0, description="Average star rating (1.0-5.0).")


class PublicReputationMetrics(BaseModel):
    """Channel A telemetry: Employee & candidate public review metrics."""

    reviews_analyzed: Optional[int] = Field(default=None, ge=0)
    overall_review_rating_5: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    recommend_to_friend_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    employer_review_reply_rate_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    cross_location_rating_std_dev_5: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    brand_alignment_index_100: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    external_claims_gap_stars_5: Optional[float] = Field(default=None, ge=0.0, le=4.0)
    sub_ratings_5: Dict[str, float] = Field(
        default_factory=dict,
        description="Sub-ratings (management, career_growth, work_life_balance, compensation, culture_and_values).",
    )
    segment_or_site_breakdown: Dict[str, SiteRatingBreakdown] = Field(
        default_factory=dict,
        description="Per-site or per-cohort review volume and star rating breakdown.",
    )


class CareerPortalMetrics(BaseModel):
    """Channel B telemetry: Career website UX and candidate application funnel."""

    monthly_visits: Optional[int] = Field(default=None, ge=0)
    smartphone_traffic_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    application_form_dropoff_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    applicant_conversion_rate_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    candidate_survey_completion_rate_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    portal_component_scores_100: Dict[str, float] = Field(
        default_factory=dict,
        description="Component UX/clarity scores on 0-100 scale.",
    )


class SocialVoiceMetrics(BaseModel):
    """Channel C telemetry: LinkedIn content engagement and employee advocacy."""

    model_config = ConfigDict(extra="allow")

    corporate_linkedin_er_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    quarterly_organic_impressions: Optional[int] = Field(default=None, ge=0)
    er_by_post_format_pct: Dict[str, float] = Field(default_factory=dict)
    spontaneous_employee_mentions_quarter: Optional[int] = Field(default=None, ge=0)
    positive_mention_share_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    active_organic_ambassadors_headcount: Optional[int] = Field(default=None, ge=0)
    manual_hr_tracking_hours_month: Optional[float] = Field(default=None, ge=0.0)


class HiringRetentionMetrics(BaseModel):
    """Channel D telemetry: Recruiting latency, agency spend, and attrition KPIs."""

    model_config = ConfigDict(extra="allow")

    early_first_year_attrition_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    estimated_annual_attrition_exposure_eur: Optional[int] = Field(default=None, ge=0)
    avg_time_to_hire_days: Optional[int] = Field(default=None, ge=0)
    agency_filled_roles_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class TelemetrySnapshot(BaseModel):
    """Unified 4-channel telemetry snapshot (T0 or T1) for a client or historical case."""

    public_reputation: PublicReputationMetrics = Field(default_factory=PublicReputationMetrics)
    career_portal_and_funnel: CareerPortalMetrics = Field(default_factory=CareerPortalMetrics)
    social_and_employee_voice: SocialVoiceMetrics = Field(default_factory=SocialVoiceMetrics)
    hiring_and_retention_kpis: HiringRetentionMetrics = Field(default_factory=HiringRetentionMetrics)


class SectorPeerBenchmarks(BaseModel):
    """Sector peer benchmark medians/averages used for deterministic gap analysis."""

    model_config = ConfigDict(extra="allow")

    sector_benchmark_group: Optional[str] = Field(default=None)
    overall_review_rating_5: Optional[float] = Field(default=None)
    recommend_to_friend_pct: Optional[float] = Field(default=None)
    employer_review_reply_rate_pct: Optional[float] = Field(default=None)
    cross_location_rating_std_dev_5: Optional[float] = Field(default=None)
    brand_alignment_index_100: Optional[float] = Field(default=None)
    external_claims_gap_stars_5: Optional[float] = Field(default=None)
    sub_ratings_5: Dict[str, float] = Field(default_factory=dict)
    portal_funnel: Dict[str, Any] = Field(default_factory=dict)
    social_and_advocacy: Dict[str, Any] = Field(default_factory=dict)
    hiring_and_retention: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Offline Database 1: normalized_rules.json Models
# =============================================================================


class ResearchSnippet(BaseModel):
    """Normalized empirical research finding from the 10 sandbox studies."""

    snippet_no: int = Field(..., ge=1, description="Original snippet number (1..10).")
    source: str = Field(..., description="Study title / source.")
    finding: str = Field(..., description="Plain-English quantified empirical finding.")
    related_pillars: List[HRPillar] = Field(default_factory=list)
    related_signals: List[SignalCode] = Field(default_factory=list)
    related_action_categories: List[ActionCategory] = Field(default_factory=list)
    applicable_workforces: List[WorkforceArchetype] = Field(default_factory=list)
    quantified_effect_summary: Optional[str] = Field(
        default=None,
        description="Short ROI/effect string (e.g., '2.4x higher 1st-year turnover', '-30-35% mobile bounce').",
    )


class MetricThresholdRule(BaseModel):
    """Deterministic threshold comparing a telemetry metric to absolute or benchmark values."""

    rule_id: str = Field(..., description="Unique metric rule identifier.")
    metric_path: str = Field(
        ...,
        description="Dot-path into TelemetrySnapshot (e.g., 'public_reputation.external_claims_gap_stars_5').",
    )
    comparison: Literal["gt", "gte", "lt", "lte", "above_benchmark_by", "below_benchmark_by"] = Field(
        ..., description="Comparison operator."
    )
    threshold_value: float = Field(..., description="Threshold or delta magnitude.")
    triggered_signal: SignalCode = Field(..., description="Canonical signal emitted when threshold fires.")
    is_healthy_signal: bool = Field(
        default=False,
        description="True when threshold detects a healthy baseline to preserve rather than a problem.",
    )
    supporting_snippet_nos: List[int] = Field(default_factory=list)


class RootCauseRule(BaseModel):
    """Cross-pillar rule linking surface symptoms + context to true underlying root causes."""

    rule_id: str = Field(..., description="Unique causal rule ID (e.g., 'RC_SAY_DO_GAP_CHURN').")
    source_field_note: Optional[str] = Field(default=None, description="Originating field note reference.")
    required_signals: List[SignalCode] = Field(
        default_factory=list,
        description="Signals that must all be present to fire this rule.",
    )
    supporting_signals: List[SignalCode] = Field(
        default_factory=list,
        description="Additional signals that boost diagnostic confidence when present.",
    )
    excluded_if_signals: List[SignalCode] = Field(
        default_factory=list,
        description="Signals that suppress this root cause (e.g., strong healthy culture).",
    )
    inferred_root_cause: SignalCode = Field(..., description="Underlying structural root cause code.")
    primary_pillar: HRPillar = Field(..., description="Primary HR pillar owning the root cause.")
    explained_surface_symptoms: List[SignalCode] = Field(
        default_factory=list,
        description="Downstream symptoms explained by this root cause.",
    )
    plain_english_template: str = Field(
        ...,
        description="Company-agnostic diagnostic explanation template.",
    )
    recommended_action_categories: List[ActionCategory] = Field(
        default_factory=list,
        description="Candidate universal actions triggered by this root cause.",
    )
    supporting_snippet_nos: List[int] = Field(default_factory=list)


class ScoringWeightsConfig(BaseModel):
    """Explicit transparent weights used by Step 3 formula scoring."""

    root_cause_overlap_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    workforce_fit_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    sector_fit_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    roi_evidence_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    cfo_auditability_weight: float = Field(default=0.10, ge=0.0, le=1.0)


class ScoringConditionRule(BaseModel):
    """Condition rule specifying candidate actions and score boosts/penalties for Step 3."""

    rule_id: str = Field(..., description="Unique scoring rule identifier.")
    action_category: ActionCategory = Field(..., description="Action category being evaluated.")
    default_action_title: str = Field(..., description="Canonical human-readable action title.")
    trigger_root_causes: List[SignalCode] = Field(default_factory=list)
    applicable_workforces: List[WorkforceArchetype] = Field(default_factory=list)
    applicable_sectors: List[SectorCategory] = Field(default_factory=list)
    base_impact_score: float = Field(default=0.5, ge=0.0, le=1.0)
    cfo_quantifiability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    expected_roi_hint: str = Field(
        default="",
        description="Empirical ROI range hint grounded in sandbox snippets/cases.",
    )
    supporting_snippet_nos: List[int] = Field(default_factory=list)


class GuardrailRule(BaseModel):
    """Deterministic constraint rule routing candidate actions into PASS/PAUSE/BLOCKED/DO_NOT_TOUCH."""

    rule_id: str = Field(..., description="Unique guardrail rule identifier.")
    target_action_categories: List[ActionCategory] = Field(
        ..., description="Action categories governed by this guardrail."
    )
    route: GuardrailRoute = Field(..., description="Routing outcome when rule matches.")
    trigger_if_active_signals: List[SignalCode] = Field(
        default_factory=list,
        description="Fires when any/all of these blocker or healthy signals are present.",
    )
    trigger_if_workforce_not_in: List[WorkforceArchetype] = Field(
        default_factory=list,
        description="Blocks action if client's target workforce does not intersect this allowed set.",
    )
    trigger_if_sector_not_in: List[SectorCategory] = Field(
        default_factory=list,
        description="Blocks action if client's sector is outside this allowed set.",
    )
    deferred_min_phase: Optional[PhaseNumber] = Field(
        default=None,
        description="Minimum phase allowed when route == PAUSE (e.g., Phase 3 until internal trust stabilizes).",
    )
    unlock_condition: Optional[str] = Field(
        default=None,
        description="Plain-English prerequisite required to unpause this action.",
    )
    reason_template: str = Field(
        ...,
        description="Auditable plain-English reason explaining why the action was paused, blocked, or marked do-not-touch.",
    )
    supporting_snippet_nos: List[int] = Field(default_factory=list)


class PhaseSequencingRule(BaseModel):
    """Dynamic prerequisite and readiness sequencing rule used by Step 5."""

    rule_id: str = Field(..., description="Unique phase sequencing rule identifier.")
    action_category: ActionCategory = Field(..., description="Action category being scheduled.")
    default_phase: PhaseNumber = Field(..., description="Default phase under standard conditions.")
    prerequisite_action_categories: List[ActionCategory] = Field(
        default_factory=list,
        description="Diagnostics/foundations that must run in an earlier phase if present.",
    )
    accelerate_to_phase_if_signals: Dict[PhaseNumber, List[SignalCode]] = Field(
        default_factory=dict,
        description="Optional acceleration map (e.g., accelerate advocacy when culture is healthy & organic ambassadors exist).",
    )
    defer_to_phase_if_signals: Dict[PhaseNumber, List[SignalCode]] = Field(
        default_factory=dict,
        description="Optional deferral map (e.g., defer advocacy to Phase 3 if Say-Do Gap or burnout is active).",
    )
    rationale: str = Field(default="", description="Domain rationale for sequencing logic.")


class NormalizedRulesDB(BaseModel):
    """Top-level schema for `database/normalized/normalized_rules.json`."""

    schema_version: str = Field(default="1.0.0")
    source_dataset_version: str = Field(default="")
    symptom_to_root_cause_rules: List[RootCauseRule] = Field(default_factory=list)
    metric_benchmark_thresholds: List[MetricThresholdRule] = Field(default_factory=list)
    scoring_weights: ScoringWeightsConfig = Field(default_factory=ScoringWeightsConfig)
    scoring_condition_rules: List[ScoringConditionRule] = Field(default_factory=list)
    guardrail_rules: List[GuardrailRule] = Field(default_factory=list)
    phase_sequencing_rules: List[PhaseSequencingRule] = Field(default_factory=list)
    empirical_research_snippets: List[ResearchSnippet] = Field(default_factory=list)


# =============================================================================
# Offline Database 2: normalized_cases.json Models
# =============================================================================


class CaseInterventionStep(BaseModel):
    """Single chronological intervention step extracted from a historical case study."""

    step_order: int = Field(..., ge=1)
    action_category: ActionCategory = Field(...)
    action_title: str = Field(...)
    phase_bucket: PhaseNumber = Field(..., description="Normalized phase (1, 2, or 3) where this step occurred.")


class QuantifiedROIDelta(BaseModel):
    """Measured T0 -> T1 metric delta extracted from analytics snapshots or case narrative."""

    metric_name: str = Field(..., description="Human-readable or telemetry metric name.")
    t0_value: Optional[float] = Field(default=None)
    t1_value: Optional[float] = Field(default=None)
    delta_display: str = Field(..., description="Formatted impact string (e.g., '-22% early turnover', '+76% conversion').")


class NormalizedCaseStudy(BaseModel):
    """Normalized representation of 1 historical B2B case study (11 total in sandbox)."""

    case_id: str = Field(..., description="Canonical slug ID (e.g., 'CASE_01_LOGINEXT').")
    case_name: str = Field(..., description="Exact `case_name` join key matching sandbox dataset.")
    curation_review_status: Literal["reviewed", "llm_draft"] = Field(
        default="reviewed",
        description="'llm_draft' = tags drafted by the LLM curation drafter and not yet human-reviewed.",
    )
    sector_category: SectorCategory = Field(...)
    sector_benchmark_group: Optional[str] = Field(default=None)
    workforce_archetypes: List[WorkforceArchetype] = Field(default_factory=list)
    headcount: Optional[int] = Field(default=None, ge=1)
    locations_count: Optional[int] = Field(default=None, ge=1)
    canonical_problem_tags: List[SignalCode] = Field(
        default_factory=list,
        description="Canonical problem & root-cause signals present at T0.",
    )
    healthy_starting_conditions: List[SignalCode] = Field(
        default_factory=list,
        description="Healthy baselines already present at T0 (e.g., HEALTHY_AUTHENTIC_EVP).",
    )
    intervention_steps: List[CaseInterventionStep] = Field(default_factory=list)
    measured_roi_summary: str = Field(..., description="Verified business/HR ROI narrative summary.")
    quantified_roi_deltas: List[QuantifiedROIDelta] = Field(default_factory=list)
    applicable_research_snippet_nos: List[int] = Field(default_factory=list)
    sector_peer_benchmarks: Optional[SectorPeerBenchmarks] = Field(default=None)
    t0_snapshot: Optional[TelemetrySnapshot] = Field(default=None)
    t1_snapshot: Optional[TelemetrySnapshot] = Field(default=None)


class NormalizedCasesDB(BaseModel):
    """Top-level schema for `database/normalized/normalized_cases.json`."""

    schema_version: str = Field(default="1.0.0")
    source_dataset_version: str = Field(default="")
    cases: List[NormalizedCaseStudy] = Field(default_factory=list)
