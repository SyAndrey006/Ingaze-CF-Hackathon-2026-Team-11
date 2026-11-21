"""Deterministic checks and compact audit traces for pipeline outputs."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

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


def _data(value: Any) -> Any:
    """Return a JSON-compatible representation of Pydantic and enum values."""
    if hasattr(value, "model_dump"):
        return _data(value.model_dump(mode="json"))
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_data(item) for item in value]
    return value


def _entries(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _action_identity(action: Any) -> Tuple[str, str]:
    item = _data(action)
    if not isinstance(item, dict):
        return str(item), ""
    nested = item.get("action") if isinstance(item.get("action"), dict) else item
    return str(nested.get("action_title", nested.get("title", ""))), str(
        nested.get("action_id", nested.get("id", ""))
    )


def _text(value: Any) -> str:
    value = _data(value)
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return str(value or "")


def _fold(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _phase_rows(phase_plan: PhasePlan) -> List[Tuple[int, Any]]:
    output = []
    for phase_number, field in (
        (1, "phase_1_actions"),
        (2, "phase_2_actions"),
        (3, "phase_3_actions"),
    ):
        for item in getattr(phase_plan, field, []):
            output.append((phase_number, item))
    return output


def build_reasoning_trace(
    client_input: NormalizedClientInput,
    diagnosis: DiagnosisResult,
    scored: ScoredCandidates,
    guardrails: GuardrailResult,
    phase_plan: PhasePlan,
) -> Dict[str, Any]:
    """Summarize the evidence and decisions made by Steps 1 through 5."""
    routes = {}
    routed_rows = []
    for field, route in (
        ("passed_actions", "PASS"),
        ("paused_actions", "PAUSE"),
        ("blocked_actions", "BLOCKED"),
        ("do_not_touch_items", "DO_NOT_TOUCH"),
    ):
        actions = getattr(guardrails, field, [])
        routes[route] = len(actions)
        for item in actions:
            title, action_id = _action_identity(item)
            routed_rows.append({
                "action_id": action_id,
                "action_title": title,
                "route": route,
                "reason": getattr(item, "reason", ""),
                "deferred_min_phase": _data(getattr(item, "deferred_min_phase", None)),
                "unlock_condition": getattr(item, "unlock_condition", None),
            })

    phase_rows = []
    for phase, action in _phase_rows(phase_plan):
        title, action_id = _action_identity(action)
        phase_rows.append({"phase": phase, "action_id": action_id, "action_title": title})

    return {
        "scenario_code": client_input.scenario_code,
        "step1": {
            "company_name": client_input.company_name,
            "signals": [
                {
                    "signal_code": _data(signal.signal_code),
                    "evidence_quote": signal.evidence_quote,
                    "source_stream": signal.source_stream,
                    "affected_cohorts": list(signal.affected_cohorts),
                }
                for signal in client_input.canonical_signals
            ],
            "filtered_noise_items": _data(client_input.filtered_noise_items),
            "healthy_baselines": _data(client_input.healthy_baselines),
        },
        "step2": {
            "root_causes": _data(diagnosis.inferred_root_causes),
            "active_blockers": _data(diagnosis.active_blockers),
            "surface_symptoms_explained": _data(diagnosis.surface_symptoms_explained),
            "open_data_hypotheses": list(diagnosis.open_data_hypotheses),
            "trace_log": list(diagnosis.trace_log),
        },
        "step3": {
            "ranked_actions": _data(scored.ranked_actions),
            "top_matched_cases": _data(scored.top_matched_cases),
            "selected_research_snippets": _data(scored.selected_research_snippets),
            "trace_log": list(scored.trace_log),
        },
        "step4": {
            "route_counts": routes,
            "routed_actions": routed_rows,
            "filtered_noise_traps": _data(guardrails.filtered_noise_traps),
            "trace_log": list(guardrails.trace_log),
        },
        "step5": {
            "phases": phase_rows,
            "sequencing_rationale": list(phase_plan.sequencing_rationale),
            "trace_log": list(phase_plan.trace_log),
        },
    }


def verify_scenario_submission(
    submission: ScenarioSubmission,
    client_input: NormalizedClientInput,
    diagnosis: DiagnosisResult,
    scored: ScoredCandidates,
    guardrails: GuardrailResult,
    phase_plan: PhasePlan,
    cases_db: NormalizedCasesDB,
) -> VerificationReport:
    """Check submission bounds and ensure blocked inputs do not enter roadmap phases."""
    errors: List[str] = []
    warnings: List[str] = []
    if submission.scenario_code != client_input.scenario_code:
        errors.append("Submission scenario_code does not match the normalized client input.")
    if len(submission.diagnosed_root_causes) > 6:
        errors.append("Submission contains more than six root-cause hypotheses.")
    if len(submission.matched_case_studies) > 3:
        errors.append("Submission contains more than three historical case precedents.")

    case_names = {case.case_name.casefold() for case in cases_db.cases}
    for entry in submission.matched_case_studies:
        rendered = _fold(_text(entry))
        if rendered and not any(_fold(name) in rendered for name in case_names):
            warnings.append(f"Matched case entry does not name a case in normalized_cases.json: {_text(entry)}")

    phase_text = {
        field: [_fold(_text(entry)) for entry in _entries(getattr(submission, field))]
        for field in ("phase_1_actions", "phase_2_actions", "phase_3_actions")
    }
    all_phase_text = [text for values in phase_text.values() for text in values]
    blocked = list(guardrails.blocked_actions) + list(guardrails.do_not_touch_items)
    for action in blocked:
        title, action_id = _action_identity(action)
        tokens = _fold(title)
        if tokens and any(tokens in text for text in all_phase_text):
            errors.append(f"Blocked or DO_NOT_TOUCH action leaked into a roadmap phase: {title}.")
        if action_id and any(action_id.casefold() in text for text in all_phase_text):
            errors.append(f"Blocked action ID leaked into a roadmap phase: {action_id}.")

    for noise in guardrails.filtered_noise_traps:
        noise_text = _fold(getattr(noise, "raw_excerpt", ""))
        if len(noise_text.split()) >= 4 and any(noise_text in text for text in all_phase_text):
            errors.append("A quarantined noise excerpt leaked into a roadmap phase.")

    phase_by_action = {}
    for phase, planned in _phase_rows(phase_plan):
        title, action_id = _action_identity(planned)
        if action_id:
            phase_by_action[action_id] = phase
    for action in guardrails.paused_actions:
        _, action_id = _action_identity(action)
        minimum = getattr(action, "deferred_min_phase", None)
        if action_id in phase_by_action and minimum is not None:
            minimum_phase = int(_data(minimum))
            if phase_by_action[action_id] < minimum_phase:
                errors.append(
                    f"Paused action {action_id} is scheduled in Phase {phase_by_action[action_id]} "
                    f"before its minimum Phase {minimum_phase}."
                )

    trace = build_reasoning_trace(client_input, diagnosis, scored, guardrails, phase_plan)
    return VerificationReport(
        scenario_code=submission.scenario_code,
        passed=not errors,
        errors=errors,
        warnings=warnings,
        reasoning_trace=trace,
    )
