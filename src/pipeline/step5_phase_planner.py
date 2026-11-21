"""
Module: step5_phase_planner.py
Stage: Step 5 — Dynamic Phase Planner (Phase 1 -> 2 -> 3)
Execution Type: Formula

Description:
    Takes ONLY the `PASS` and `PAUSE` actions from Step 4 (`GuardrailResult`)
    alongside `DiagnosisResult` and `rules_db.phase_sequencing_rules`, and
    deterministically assigns each action to `phase_1_actions`, `phase_2_actions`,
    or `phase_3_actions` based on diagnostic prerequisites and client cultural
    readiness (e.g., accelerating advocacy when internal trust is healthy and
    organic ambassadors exist, or deferring it to Phase 3 when blocked).

Input:
    - guardrails (GuardrailResult): Contains `passed_actions` and `paused_actions`
      from Step 4 (blocked and do-not-touch items are excluded from phase planning).
    - diagnosis (DiagnosisResult): Cultural readiness profile, active blockers,
      and confirmed signals from Step 2.
    - rules_db (NormalizedRulesDB): Declarative `phase_sequencing_rules` from
      `normalized_rules.json`.

Output:
    - phase_plan (PhasePlan): Sequenced `phase_1_actions`, `phase_2_actions`,
      `phase_3_actions`, and `sequencing_rationale` consumed by Step 6
      (`step6_hr_proposal.py`).

TODO:
    1. Implement `resolve_action_phase` honoring `default_phase`, `accelerate_to_phase_if_signals`,
       `defer_to_phase_if_signals`, and any Step 4 `deferred_min_phase` floor on `PAUSE` actions.
    2. Implement prerequisite dependency enforcement (`enforce_prerequisite_ordering`):
       if action B lists diagnostic action A in `prerequisite_action_categories` and A
       is scheduled in Phase P, guarantee B is scheduled in `max(phase(B), P + 1)`.
    3. Guard against degenerate plans (e.g., dumping all actions into Phase 1 with empty
       Phase 2/3) and record clear, CFO-auditable `sequencing_rationale` explaining why
       phases are ordered or accelerated for this client's readiness profile.
"""

from __future__ import annotations

from typing import List

from src.schemas.domain_models import NormalizedRulesDB
from src.schemas.pipeline_models import (
    DiagnosisResult,
    GuardrailResult,
    PhasePlan,
    PlannedAction,
    RoutedAction,
)


def resolve_action_phase(
    routed_action: RoutedAction,
    diagnosis: DiagnosisResult,
    rules_db: NormalizedRulesDB,
) -> PlannedAction:
    """
    Determine the initial target phase (`PHASE_1`, `PHASE_2`, or `PHASE_3`) for
    a single `PASS` or `PAUSE` action using `rules_db.phase_sequencing_rules`
    and `diagnosis.cultural_readiness`.
    """
    # TODO: 1. Look up matching `PhaseSequencingRule` for `routed_action.action.action_category`.
    # TODO: 2. Apply acceleration rules if readiness/healthy signals match (only when not PAUSEd),
    #          or deferral rules if blocker signals match.
    # TODO: 3. Enforce `assigned_phase >= routed_action.deferred_min_phase` for PAUSEd items.
    raise NotImplementedError("TODO: Implement resolve_action_phase")


def enforce_prerequisite_ordering(
    planned_actions: List[PlannedAction],
    rules_db: NormalizedRulesDB,
) -> List[PlannedAction]:
    """
    Topologically verify prerequisite dependencies across planned actions so no
    downstream redesign, JD rewrite, or automation runs before its required
    foundational diagnostic or cultural stabilization step.
    """
    # TODO: 1. Map active `ActionCategory -> assigned_phase` across `planned_actions`.
    # TODO: 2. For each action with prerequisites present in the plan, push its phase
    #          strictly after all prerequisite phases (capped at `PHASE_3`).
    # TODO: 3. Update `sequencing_reason` whenever an action is shifted by a dependency.
    raise NotImplementedError("TODO: Implement enforce_prerequisite_ordering")


def build_phase_plan(
    guardrails: GuardrailResult,
    diagnosis: DiagnosisResult,
    rules_db: NormalizedRulesDB,
) -> PhasePlan:
    """
    Step 5 entrypoint: schedule all `passed_actions` and `paused_actions` into
    `phase_1_actions`, `phase_2_actions`, and `phase_3_actions`.
    """
    # TODO: 1. Combine `guardrails.passed_actions + guardrails.paused_actions` (ignore blocked/do_not_touch).
    # TODO: 2. Resolve initial phases via `resolve_action_phase(...)` and run `enforce_prerequisite_ordering(...)`.
    # TODO: 3. Bucket into `phase_1_actions`, `phase_2_actions`, `phase_3_actions`, sort each bucket
    #          by descending `total_score`, and populate `sequencing_rationale` + `trace_log`.
    raise NotImplementedError("TODO: Implement Step 5 (build_phase_plan)")
