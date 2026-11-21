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


def tailor_pilot(key, profile, features):
    if key == "application_friction" and "freight" in profile:
        return "At one affected hub, start with a phone-accessible qualification check and offer qualified candidates a callback slot. Track qualified completions and recruiter load."
    if key == "expectation_drift" and "tech" in profile:
        return "Co-write a realistic engineering role preview with the affected teams. Ask recent hires to verify which decisions they can own and where approvals actually sit."
    if key == "feedback_coverage" and "care" in profile:
        return "Pilot a common post-interview survey with a local owner at a regional clinic. Track invitation and response coverage while preserving effective lab recruiting."
    if key == "manual_measurement" and "emv" in features:
        return "Build a source-linked ledger for eligible posts and applicant outcomes. Deduplicate posts and report staff time separately from estimated media costs."
    return None


def build_reasoning_phase_plan(scenario, intake, guardrails, profile):
    """Assemble engine root causes, phase actions, and client verification questions."""
    strengths = guardrails["strengths"]
    target = guardrails["target"]
    features = guardrails["features"]
    requests = guardrails["requests"]
    roots, audit, pilots, scaling, questions = [], [], [], [], []

    for evaluation in guardrails["evaluations"]:
        hypothesis = evaluation["hypothesis"]
        key, scope, status = evaluation["rule_id"], hypothesis["scope"], hypothesis["status"]
        rule = evaluation["rule"]
        if rule["kind"] != "policy":
            roots.append({"hypothesis": rule["label"], "status": status, "rule": key, "scope": scope,
                          "evidence_ids": hypothesis["evidence_ids"]})
        audit.append({"action": rule["diagnostic"], "scope": scope, "rule": key})
        if status != "supported":
            questions.append({"rule": key, "scope": scope, "verify": rule["diagnostic"],
                              "missing_families": hypothesis["missing_families"],
                              "dependent_families": hypothesis["dependent_families"],
                              "counterevidence_ids": hypothesis["counterevidence_ids"]})
        if evaluation["reason"]:
            continue

        prerequisite = evaluation["prerequisite"]
        pilot = {"action": rule["pilot"], "scope": scope, "rule": key, "decision": "conditional",
                 "prerequisite": prerequisite}
        if isinstance(target, str) and scope["cohort"] in (None, "all"):
            pilot["target_to_verify"] = target
        if intake["protected_baselines"]:
            pilot["preserve_baselines"] = [item["source_ref"] for item in intake["protected_baselines"]]
        design = tailor_pilot(key, profile, features)
        if design:
            pilot["pilot_design"] = design
        pilots.append(pilot)
        scaling.append({"condition": rule["scale_gate"], "scope": scope, "rule": key,
                        "prerequisite": "Complete the scoped pilot and verify improvements and guard metrics."})

    if "finance" in requests or "emv" in features:
        audit.append({"action": "Agree auditable outcome definitions with Finance. Separate staff time, hiring outcomes and estimated media cost."})
    if features.intersection({"hiring_delay", "vacancy_delay"}) and not guardrails["hiring_stage_leads"]:
        audit.append({
            "action": "Separate request-to-approval, qualified applicant supply, form completion, recruiter response, interviews and offers. Identify the stage and affected roles before selecting a pilot.",
            "decision": "stage_unknown",
        })
    if not audit:
        audit.append({"action": "Collect observations from independent origins within the same cohort and assessment window."})

    return {
        "diagnosed_root_causes": roots,
        "phase_1_actions": audit,
        "phase_2_actions": pilots,
        "phase_3_actions": scaling,
        "open_questions_and_hypotheses_for_client": questions,
        "strengths": strengths,
        "cohort": guardrails["cohort"],
    }


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
