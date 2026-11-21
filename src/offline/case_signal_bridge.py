"""
Module: case_signal_bridge.py
Stage: Shared helper for Step 3 (Conditions & Scoring)
Execution Type: Formula (pure, deterministic, company-agnostic)

Description:
    Translates the deterministic Step 2 vocabulary (knowledge-graph `track_tags`
    and profile tags) into the canonical enums of the normalized case store
    (`SignalCode`, `WorkforceArchetype`, `SectorCategory`).

    This lets Step 3 rank precedents with `rank_top_cases` for every client,
    including runs without the Step 1 LLM, instead of relying on a hand-kept tag
    list per historical case name.

    The tables map concept to concept only. They never contain company, case or
    scenario names. Track tags without a case-store equivalent are listed
    explicitly in `UNMAPPED_TRACK_TAGS` so a new graph tag cannot be silently
    dropped (see tests/test_case_signal_bridge.py).
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from src.schemas.domain_models import SectorCategory, SignalCode, WorkforceArchetype

S = SignalCode

# Knowledge-graph track tag -> canonical case-store problem signals.
TRACK_TAG_TO_SIGNALS: Dict[str, Tuple[SignalCode, ...]] = {
    "expectation_gap": (S.SAY_DO_GAP,),
    "manager_support": (S.WEAK_MIDDLE_MANAGEMENT,),
    "career_clarity": (S.CAREER_PATH_OPACITY,),
    "burnout": (S.WORKLOAD_BURNOUT,),
    "early_attrition": (S.EARLY_FIRST_YEAR_ATTRITION,),
    "mobile_friction": (S.MOBILE_PORTAL_FRICTION, S.HIGH_APPLICATION_DROPOFF),
    "generic_ads": (S.GENERIC_BOILERPLATE_JDS,),
    "local_reputation": (S.MULTISITE_REPUTATION_VARIANCE, S.UNMONITORED_LOCAL_REVIEWS),
    "review_tracking": (S.UNMONITORED_LOCAL_REVIEWS, S.MANUAL_HR_SPREADSHEET_DRAG),
    "post_tracking": (S.MANUAL_HR_SPREADSHEET_DRAG, S.MISSING_CFO_ROI_EMV_VISIBILITY),
    "feedback_fragmentation": (S.FRAGMENTED_CANDIDATE_FEEDBACK,),
    "emv": (S.MISSING_CFO_ROI_EMV_VISIBILITY,),
    "campaign_attribution_gap": (S.MISSING_CFO_ROI_EMV_VISIBILITY,),
    "agency_spend": (S.HIGH_EXTERNAL_AGENCY_DEPENDENCY,),
    "hiring_delay": (S.HIGH_TIME_TO_HIRE,),
    "channel_reach_mismatch": (S.CHANNEL_WORKFORCE_MISMATCH,),
    "screening_mismatch": (S.MISSING_CANDIDATE_PERSONA_FIT,),
    "existing_advocates": (S.ACTIVE_ORGANIC_AMBASSADORS_PRESENT,),
    "culture_ready": (S.STRONG_INTERNAL_CULTURE_HEALTHY,),
}

# Graph track tags that describe mechanisms the case store does not encode (yet).
UNMAPPED_TRACK_TAGS: FrozenSet[str] = frozenset({
    "internal_mobility",
    "interview_capacity",
    "offer_acceptance",
    "prestart_withdrawal",
    "qualified_supply_verified",
    "requisition_approval",
    "review_sample_shift",
    "speak_up_barriers",
    "work_location_flexibility",
})

# Step 2 profile tag -> workforce archetype. "distributed" describes site spread,
# not a workforce; it only maps to MIXED_DISTRIBUTED when no concrete archetype
# was detected (otherwise every frontline client would look half-mismatched).
PROFILE_TO_WORKFORCE: Dict[str, WorkforceArchetype] = {
    "tech": WorkforceArchetype.DESK_BASED_TECH_SPECIALIST,
    "fintech": WorkforceArchetype.DESK_BASED_TECH_SPECIALIST,
    "freight": WorkforceArchetype.DESKLESS_FRONTLINE_LOGISTICS,
    "retail": WorkforceArchetype.DESKLESS_FRONTLINE_RETAIL,
    "care": WorkforceArchetype.MULTISITE_CLINICAL_HEALTHCARE,
    "early_career": WorkforceArchetype.EARLY_CAREER_GEN_Z,
}
FALLBACK_DISTRIBUTED_TAG = "distributed"

# Step 2 profile tag -> sector, in priority order (most specific first).
PROFILE_TO_SECTOR_PRIORITY: Tuple[Tuple[str, SectorCategory], ...] = (
    ("fintech", SectorCategory.FINTECH_PAYMENTS),
    ("care", SectorCategory.HEALTHCARE_CLINICAL),
    ("freight", SectorCategory.LOGISTICS_FREIGHT),
    ("retail", SectorCategory.RETAIL_OMNICHANNEL),
    ("sustainability", SectorCategory.CLEANTECH_SUSTAINABILITY_BCORP),
    ("tech", SectorCategory.B2B_TECH_SAAS),
)


def signals_for_track_tags(track_tags: Iterable[str]) -> Set[SignalCode]:
    """Canonical signals for a set of graph track tags (unknown tags are ignored)."""
    return {signal for tag in track_tags for signal in TRACK_TAG_TO_SIGNALS.get(tag, ())}


def workforce_for_profile(profile: Iterable[str]) -> List[WorkforceArchetype]:
    tags = set(profile)
    workforce = {PROFILE_TO_WORKFORCE[tag] for tag in tags if tag in PROFILE_TO_WORKFORCE}
    if not workforce and FALLBACK_DISTRIBUTED_TAG in tags:
        workforce.add(WorkforceArchetype.MIXED_DISTRIBUTED)
    return sorted(workforce, key=lambda w: w.value)


def sector_for_profile(profile: Iterable[str]) -> Optional[SectorCategory]:
    tags = set(profile)
    return next((sector for tag, sector in PROFILE_TO_SECTOR_PRIORITY if tag in tags), None)


def client_match_profile(
    track_tags: Iterable[str], profile: Iterable[str]
) -> Tuple[List[SignalCode], List[WorkforceArchetype], Optional[SectorCategory]]:
    """`(signals, workforce, sector)` for `rank_top_cases` from Step 2 output."""
    signals = sorted(signals_for_track_tags(track_tags), key=lambda s: s.value)
    profile = list(profile)
    return signals, workforce_for_profile(profile), sector_for_profile(profile)
