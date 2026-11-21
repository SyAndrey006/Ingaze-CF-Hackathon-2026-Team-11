"""
Module: case_matching.py
Stage: Shared helper for Step 3 (Conditions & Scoring)
Execution Type: Formula (pure, deterministic, company-agnostic)

Description:
    Pure functions over `NormalizedCasesDB` that Step 3 uses to
      1. collect candidate actions from historical precedents
         (`candidate_actions_from_cases`), and
      2. rank the Top-K most similar historical cases with a transparent score
         breakdown and a human-readable reason (`rank_top_cases`).

    Nothing in here references company names, case names or scenario codes:
    matching works purely on canonical enums (signals, workforce, sector, actions).

Scoring (all components in [0, 1], combined with `ScoringWeightsConfig` from
`normalized_rules.json`, normalized by the weight sum):
    - root_cause_overlap: Dice overlap between client problem signals and the case's
      canonical problem tags -> 2*|A n B| / (|A| + |B|). Rewards precision and coverage.
    - workforce_fit: share of the client's workforce archetypes present in the case.
      Hard exclusions first: a case must share >= 1 root cause with the client,
      and a desk-based case is never matched to a frontline client and vice versa
      (unless they share an archetype).
    - sector_fit: 1.0 same sector, 0.5 adjacent sector, 0.0 otherwise.
    - roi_evidence: amount of measured T0->T1 evidence (number of quantified deltas,
      saturating at 6), blended 50/50 with the share of the client's planned actions
      that the case actually executed (if planned actions are given).
    - cfo_auditability: 0.5 for T0+T1 telemetry snapshots, +0.25 if the measured ROI
      summary is quantified (contains digits), +0.25 if the case shipped a CFO
      risk/EMV dashboard.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set, Tuple, Union

from src.schemas.domain_models import (
    ActionCategory,
    NormalizedCasesDB,
    NormalizedCaseStudy,
    PhaseNumber,
    ScoringWeightsConfig,
    SectorCategory,
    SignalCode,
    WorkforceArchetype,
)
from src.schemas.pipeline_models import MatchedCaseScore, ScoreBreakdown

# Workforce families used for the hard exclusion rule (desk vs. deskless/frontline).
DESK_BASED_WORKFORCES: Set[WorkforceArchetype] = {
    WorkforceArchetype.DESK_BASED_TECH_SPECIALIST,
    WorkforceArchetype.CORPORATE_HQ_ADMIN,
}
FRONTLINE_WORKFORCES: Set[WorkforceArchetype] = {
    WorkforceArchetype.DESKLESS_FRONTLINE_LOGISTICS,
    WorkforceArchetype.DESKLESS_FRONTLINE_RETAIL,
    WorkforceArchetype.MULTISITE_CLINICAL_HEALTHCARE,
}

# Adjacent sectors earn partial sector fit (symmetric).
ADJACENT_SECTORS: Set[frozenset] = {
    frozenset({SectorCategory.B2B_TECH_SAAS, SectorCategory.FINTECH_PAYMENTS}),
    frozenset({SectorCategory.FINTECH_PAYMENTS, SectorCategory.BANKING_FINANCIAL_SERVICES}),
    frozenset({SectorCategory.LOGISTICS_FREIGHT, SectorCategory.RETAIL_OMNICHANNEL}),
}

ROI_DELTA_SATURATION = 6
TOP_DELTA_LINES = 3

SignalLike = Union[SignalCode, str]
WorkforceLike = Union[WorkforceArchetype, str]
SectorLike = Union[SectorCategory, str, None]
ActionLike = Union[ActionCategory, str]


@dataclass(frozen=True)
class RankedCase:
    """One ranked precedent: the pipeline-contract match plus a plain-English reason."""

    match: MatchedCaseScore
    reason: str


# -----------------------------------------------------------------------------
# Input coercion
# -----------------------------------------------------------------------------

def _signals(values: Iterable[SignalLike]) -> Set[SignalCode]:
    return {SignalCode(v) for v in values}


def _workforces(values: Iterable[WorkforceLike]) -> Set[WorkforceArchetype]:
    return {WorkforceArchetype(v) for v in values}


def _sector(value: SectorLike) -> Optional[SectorCategory]:
    return SectorCategory(value) if value is not None else None


def _actions(values: Optional[Iterable[ActionLike]]) -> Set[ActionCategory]:
    return {ActionCategory(v) for v in (values or [])}


# -----------------------------------------------------------------------------
# Component scores
# -----------------------------------------------------------------------------

def is_workforce_mismatch(
    client_workforce: Set[WorkforceArchetype], case_workforce: Set[WorkforceArchetype]
) -> bool:
    """True if one side is desk-based and the other frontline with no shared archetype."""
    if client_workforce & case_workforce:
        return False
    client_desk = bool(client_workforce & DESK_BASED_WORKFORCES)
    client_front = bool(client_workforce & FRONTLINE_WORKFORCES)
    case_desk = bool(case_workforce & DESK_BASED_WORKFORCES)
    case_front = bool(case_workforce & FRONTLINE_WORKFORCES)
    return (client_desk and case_front) or (client_front and case_desk)


def _root_cause_overlap(client: Set[SignalCode], case_tags: Set[SignalCode]) -> float:
    if not client or not case_tags:
        return 0.0
    return 2 * len(client & case_tags) / (len(client) + len(case_tags))


def _workforce_fit(client: Set[WorkforceArchetype], case_wf: Set[WorkforceArchetype]) -> float:
    if not client:
        return 0.0
    return len(client & case_wf) / len(client)


def _sector_fit(client: Optional[SectorCategory], case_sector: SectorCategory) -> float:
    if client is None:
        return 0.0
    if client == case_sector:
        return 1.0
    if frozenset({client, case_sector}) in ADJACENT_SECTORS:
        return 0.5
    return 0.0


def _roi_evidence(case: NormalizedCaseStudy, planned: Set[ActionCategory]) -> float:
    delta_score = min(1.0, len(case.quantified_roi_deltas) / ROI_DELTA_SATURATION)
    if not planned:
        return delta_score
    case_actions = {s.action_category for s in case.intervention_steps}
    action_score = len(planned & case_actions) / len(planned)
    return 0.5 * delta_score + 0.5 * action_score


def _cfo_auditability(case: NormalizedCaseStudy) -> float:
    score = 0.0
    if case.t0_snapshot is not None and case.t1_snapshot is not None:
        score += 0.5
    if re.search(r"\d", case.measured_roi_summary or ""):
        score += 0.25
    if any(s.action_category == ActionCategory.CFO_RISK_AND_EMV_DASHBOARD for s in case.intervention_steps):
        score += 0.25
    return score


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def load_scoring_weights(rules_path: Path) -> ScoringWeightsConfig:
    """Read only the `scoring_weights` block from `normalized_rules.json`."""
    with Path(rules_path).open(encoding="utf-8") as fh:
        raw = json.load(fh)
    return ScoringWeightsConfig.model_validate(raw.get("scoring_weights", {}))


def candidate_actions_from_cases(
    cases_db: NormalizedCasesDB,
    client_signals: Iterable[SignalLike],
    workforce: Iterable[WorkforceLike],
    sector: SectorLike = None,
) -> List[Tuple[ActionCategory, str, PhaseNumber]]:
    """
    Return `(ActionCategory, case_id, phase_bucket)` for every intervention step of
    cases whose problem tags overlap the client's signals AND whose workforce
    archetypes intersect the client's workforce.

    Order: same-sector cases first, then by number of overlapping signals (desc),
    then case_id, then step order. Duplicate (action, case) pairs are dropped.
    """
    signals, wf, sec = _signals(client_signals), _workforces(workforce), _sector(sector)

    eligible = []
    for case in cases_db.cases:
        overlap = len(signals & set(case.canonical_problem_tags))
        if overlap and wf & set(case.workforce_archetypes):
            eligible.append((case.sector_category != sec, -overlap, case.case_id, case))
    eligible.sort(key=lambda t: t[:3])

    out: List[Tuple[ActionCategory, str, PhaseNumber]] = []
    seen: Set[Tuple[ActionCategory, str]] = set()
    for *_, case in eligible:
        for step in sorted(case.intervention_steps, key=lambda s: s.step_order):
            key = (step.action_category, case.case_id)
            if key in seen:
                continue
            seen.add(key)
            out.append((step.action_category, case.case_id, step.phase_bucket))
    return out


def rank_top_cases(
    cases_db: NormalizedCasesDB,
    client_signals: Iterable[SignalLike],
    workforce: Iterable[WorkforceLike],
    sector: SectorLike = None,
    planned_actions: Optional[Iterable[ActionLike]] = None,
    weights: Optional[ScoringWeightsConfig] = None,
    k: int = 3,
    min_shared_root_causes: int = 1,
) -> List[RankedCase]:
    """
    Rank historical cases by weighted similarity to the client profile.

    Hard exclusions before scoring: workforce mismatches (desk-based vs. frontline
    without shared archetype) and cases sharing fewer than `min_shared_root_causes`
    problem signals with the client (same sector alone is not a precedent).
    Ties are broken by `case_id` for determinism.
    """
    signals, wf, sec = _signals(client_signals), _workforces(workforce), _sector(sector)
    planned = _actions(planned_actions)
    w = weights or ScoringWeightsConfig()
    weight_sum = (
        w.root_cause_overlap_weight
        + w.workforce_fit_weight
        + w.sector_fit_weight
        + w.roi_evidence_weight
        + w.cfo_auditability_weight
    ) or 1.0

    ranked: List[RankedCase] = []
    for case in cases_db.cases:
        case_wf = set(case.workforce_archetypes)
        if is_workforce_mismatch(wf, case_wf):
            continue

        case_tags = set(case.canonical_problem_tags)
        if len(signals & case_tags) < min_shared_root_causes:
            continue
        breakdown = ScoreBreakdown(
            root_cause_overlap_score=round(_root_cause_overlap(signals, case_tags), 4),
            workforce_fit_score=round(_workforce_fit(wf, case_wf), 4),
            sector_fit_score=round(_sector_fit(sec, case.sector_category), 4),
            roi_evidence_score=round(_roi_evidence(case, planned), 4),
            cfo_auditability_score=round(_cfo_auditability(case), 4),
        )
        total = (
            w.root_cause_overlap_weight * breakdown.root_cause_overlap_score
            + w.workforce_fit_weight * breakdown.workforce_fit_score
            + w.sector_fit_weight * breakdown.sector_fit_score
            + w.roi_evidence_weight * breakdown.roi_evidence_score
            + w.cfo_auditability_weight * breakdown.cfo_auditability_score
        ) / weight_sum

        matched = [t for t in case.canonical_problem_tags if t in signals]
        match = MatchedCaseScore(
            case_id=case.case_id,
            case_name=case.case_name,
            sector_category=case.sector_category,
            similarity_score=round(min(1.0, max(0.0, total)), 4),
            score_breakdown=breakdown,
            matched_problem_tags=matched,
            measured_roi_summary=case.measured_roi_summary,
            quantified_roi_highlights=[d.delta_display for d in case.quantified_roi_deltas[:TOP_DELTA_LINES]],
        )
        ranked.append(RankedCase(match=match, reason=_reason(case, signals, wf, sec, planned, matched)))

    ranked.sort(key=lambda r: (-r.match.similarity_score, r.match.case_id))
    return ranked[:k]


def _reason(
    case: NormalizedCaseStudy,
    signals: Set[SignalCode],
    wf: Set[WorkforceArchetype],
    sec: Optional[SectorCategory],
    planned: Set[ActionCategory],
    matched: Sequence[SignalCode],
) -> str:
    parts = [f"{len(matched)}/{len(signals)} root causes match"]

    shared_wf = wf & set(case.workforce_archetypes)
    if wf and shared_wf == wf:
        parts.append("same workforce")
    elif shared_wf:
        parts.append(f"partial workforce overlap ({len(shared_wf)}/{len(wf)})")
    else:
        parts.append("different workforce")

    sector_fit = _sector_fit(sec, case.sector_category)
    if sector_fit == 1.0:
        parts.append("same sector")
    elif sector_fit > 0:
        parts.append("adjacent sector")

    if planned:
        done = planned & {s.action_category for s in case.intervention_steps}
        parts.append(f"{len(done)}/{len(planned)} planned actions have precedent")

    if case.quantified_roi_deltas:
        parts.append(f"{len(case.quantified_roi_deltas)} measured T0->T1 deltas")
    return ", ".join(parts)
