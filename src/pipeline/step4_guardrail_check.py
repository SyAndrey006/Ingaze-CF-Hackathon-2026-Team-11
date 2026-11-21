"""
Module: step4_guardrail_check.py
Stage: Step 4 — Guardrail Check & 4-Way Routing
Execution Type: Formula

Description:
    Deterministically evaluates every ranked candidate action and executive
    request from Step 3 against `rules_db.guardrail_rules`, `diagnosis` active
    blockers, `locked_healthy_baselines`, and client sector/workforce fit.
    Routes every candidate into exactly one of 4 paths:
      - `PASS` -> goes to Step 5 (Phase Plan)
      - `PAUSE` (deferred due to active blocker e.g. Say-Do Gap/burnout) -> goes to Step 5 (Phase Plan)
      - `BLOCKED` (wrong industry/workforce mismatch or noisy trap) -> goes directly to Step 6 (HR Proposal)
      - `DO_NOT_TOUCH` (redundant overhaul of already-healthy baseline/cohort) -> goes directly to Step 6 (HR Proposal)

Input:
    - scored (ScoredCandidates): Ranked candidate actions & executive requests from Step 3.
    - client_input (NormalizedClientInput): Client sector, workforce archetypes,
      filtered noise traps, and healthy baselines from Step 1.
    - diagnosis (DiagnosisResult): Active blockers, cultural readiness, and locked
      healthy baselines from Step 2.
    - rules_db (NormalizedRulesDB): Declarative guardrail rules from `normalized_rules.json`.

Output:
    - guardrail_result (GuardrailResult): Four partitioned action lists
      (`passed_actions`, `paused_actions`, `blocked_actions`, `do_not_touch_items`)
      plus carried-forward `filtered_noise_traps`. `PASS` + `PAUSE` go to Step 5;
      `BLOCKED` + `DO_NOT_TOUCH` + `filtered_noise_traps` go directly to Step 6.

TODO:
    1. Implement strict rule-precedence routing (`BLOCKED` > `DO_NOT_TOUCH` > `PAUSE` > `PASS`)
       so a wrong-industry action is never merely paused and a healthy-baseline overhaul
       is explicitly captured as `DO_NOT_TOUCH`.
    2. Enforce workforce/channel and sector guardrails (e.g., physical retail shift
       rotation blocked for digital tech; B2B LinkedIn technical blogs blocked for
       frontline deskless drivers) purely via `WorkforceArchetype` and `SectorCategory`
       rules—zero company-name checks.
    3. Enforce cultural readiness and diagnostic prerequisite guardrails (e.g., pause
       external advocacy when Say-Do Gap or burnout is active; pause premature rebuilds
       when prerequisite audits have not run; route redundant EVP/pay overhauls to
       `DO_NOT_TOUCH` when baselines are already healthy).
"""

from __future__ import annotations

from src.schemas.domain_models import NormalizedRulesDB
from src.schemas.pipeline_models import (
    DiagnosisResult,
    GuardrailResult,
    NormalizedClientInput,
    RoutedAction,
    ScoredAction,
    ScoredCandidates,
)


def evaluate_action_guardrails(
    candidate: ScoredAction,
    client_input: NormalizedClientInput,
    diagnosis: DiagnosisResult,
    rules_db: NormalizedRulesDB,
) -> RoutedAction:
    """
    Evaluate a single `ScoredAction` against all matching `GuardrailRule` entries
    and assign one deterministic `GuardrailRoute` (`PASS`, `PAUSE`, `BLOCKED`, or
    `DO_NOT_TOUCH`) with an auditable reason.
    """
    # TODO: 1. Find all `rules_db.guardrail_rules` whose `target_action_categories`
    #          include `candidate.action_category`.
    # TODO: 2. Check workforce mismatch (`trigger_if_workforce_not_in`), sector mismatch
    #          (`trigger_if_sector_not_in`), healthy-baseline conflict (`DO_NOT_TOUCH`),
    #          and active blocker signals (`PAUSE` with `deferred_min_phase` & `unlock_condition`).
    # TODO: 3. Resolve precedence (`BLOCKED` > `DO_NOT_TOUCH` > `PAUSE` > `PASS`) and return `RoutedAction`.
    raise NotImplementedError("TODO: Implement evaluate_action_guardrails")


def apply_guardrail_checks(
    scored: ScoredCandidates,
    client_input: NormalizedClientInput,
    diagnosis: DiagnosisResult,
    rules_db: NormalizedRulesDB,
) -> GuardrailResult:
    """
    Step 4 entrypoint: route every candidate action and executive request into
    `passed_actions`, `paused_actions`, `blocked_actions`, or `do_not_touch_items`,
    and carry forward `client_input.filtered_noise_items`.
    """
    # TODO: 1. Loop through `scored.ranked_actions` and call `evaluate_action_guardrails(...)`.
    # TODO: 2. Partition results strictly into the 4 lists on `GuardrailResult`.
    # TODO: 3. Copy `client_input.filtered_noise_items` into `filtered_noise_traps`,
    #          write auditable `trace_log` entries, and return `GuardrailResult`.
    raise NotImplementedError("TODO: Implement Step 4 (apply_guardrail_checks)")
