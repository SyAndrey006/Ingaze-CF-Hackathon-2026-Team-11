"""
Module: __init__.py
Stage: Schemas Package
Execution Type: Schema

Description:
    Re-exports all canonical domain models, inter-step pipeline contracts, and
    hackathon submission output schemas so downstream offline and online modules
    can import typed Pydantic models from a single namespace.

Input:
    - Model definitions from `domain_models.py`, `pipeline_models.py`, and `submission_models.py`.

Output:
    - Re-exported Pydantic classes and Enums for `src/offline/*`, `src/pipeline/*`, `src/utils/*`, and `tests/*`.

"""

from src.schemas.domain_models import (
    ActionCategory,
    CareerPortalMetrics,
    GuardrailRoute,
    GuardrailRule,
    HiringRetentionMetrics,
    HRPillar,
    MetricThresholdRule,
    NormalizedCasesDB,
    NormalizedCaseStudy,
    NormalizedRulesDB,
    PhaseNumber,
    PhaseSequencingRule,
    PublicReputationMetrics,
    QuantifiedROIDelta,
    ResearchSnippet,
    RootCauseRule,
    ScoringConditionRule,
    ScoringWeightsConfig,
    SectorCategory,
    SectorPeerBenchmarks,
    SignalCode,
    SiteRatingBreakdown,
    SocialVoiceMetrics,
    TelemetrySnapshot,
    WorkforceArchetype,
)
from src.schemas.pipeline_models import (
    BenchmarkDeviation,
    CohortSiteAsymmetry,
    CulturalReadinessAssessment,
    DiagnosedRootCause,
    DiagnosisResult,
    ExtractedSignal,
    FilteredNoiseItem,
    GuardrailResult,
    HealthyBaseline,
    LeadershipRequest,
    MatchedCaseScore,
    NormalizedClientInput,
    PhasePlan,
    PlannedAction,
    RawScenarioBundle,
    RoutedAction,
    ScoredAction,
    ScoredCandidates,
    VerificationReport,
)
from src.schemas.submission_models import (
    ScenarioSubmission,
    SubmissionPayload,
)

__all__ = [
    # Domain Models
    "ActionCategory",
    "CareerPortalMetrics",
    "GuardrailRoute",
    "GuardrailRule",
    "HiringRetentionMetrics",
    "HRPillar",
    "MetricThresholdRule",
    "NormalizedCasesDB",
    "NormalizedCaseStudy",
    "NormalizedRulesDB",
    "PhaseNumber",
    "PhaseSequencingRule",
    "PublicReputationMetrics",
    "QuantifiedROIDelta",
    "ResearchSnippet",
    "RootCauseRule",
    "ScoringConditionRule",
    "ScoringWeightsConfig",
    "SectorCategory",
    "SectorPeerBenchmarks",
    "SignalCode",
    "SiteRatingBreakdown",
    "SocialVoiceMetrics",
    "TelemetrySnapshot",
    "WorkforceArchetype",
    # Pipeline I/O Contracts
    "BenchmarkDeviation",
    "CohortSiteAsymmetry",
    "CulturalReadinessAssessment",
    "DiagnosedRootCause",
    "DiagnosisResult",
    "ExtractedSignal",
    "FilteredNoiseItem",
    "GuardrailResult",
    "HealthyBaseline",
    "LeadershipRequest",
    "MatchedCaseScore",
    "NormalizedClientInput",
    "PhasePlan",
    "PlannedAction",
    "RawScenarioBundle",
    "RoutedAction",
    "ScoredAction",
    "ScoredCandidates",
    "VerificationReport",
    # Submission Contract
    "ScenarioSubmission",
    "SubmissionPayload",
]
