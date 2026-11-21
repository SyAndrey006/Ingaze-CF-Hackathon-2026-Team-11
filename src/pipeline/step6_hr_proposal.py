"""Step 6: deterministic, auditable HR proposal formatting.

The JSON submission is assembled independently. This module renders the approved
Steps 2 through 5 state as Markdown and optionally polishes only the summary.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, Optional

from pydantic import BaseModel, Field

from src.utils.llm_client import StructuredLLMClient

LOGGER = logging.getLogger(__name__)


class _ExecutiveSummaryPolish(BaseModel):
    """Structured LLM response constrained to a single optional summary field."""

    executive_summary: str = Field(..., min_length=1, max_length=600)


def assemble_recommendation(scenario, graph, diagnosis_state, scored_state, guardrail_state, phase_state):
    """Assemble the final deterministic response from the verified stage outputs."""
    result = {
        "scenario_code": scenario["scenario_code"],
        "diagnosed_root_causes": phase_state["diagnosed_root_causes"],
        "blocked_traps_and_guardrails": guardrail_state["guards"],
        "phase_1_actions": phase_state["phase_1_actions"],
        "phase_2_actions": phase_state["phase_2_actions"],
        "phase_3_actions": phase_state["phase_3_actions"],
        "matched_case_studies": scored_state["matched_case_studies"],
        "supporting_research_snippets": scored_state["supporting_research_snippets"],
        "strategic_focus_and_do_not_touch": (
            [phase_state["strengths"]] if phase_state["strengths"] else []
        ),
        "cohort_specific_strategies": (
            [phase_state["cohort"]] if phase_state["cohort"] else []
        ),
        "open_questions_and_hypotheses_for_client": (
            phase_state["open_questions_and_hypotheses_for_client"]
        ),
    }
    trace = {
        "scenario_code": scenario["scenario_code"],
        "profile": diagnosis_state["profile"],
        "excluded_noise": diagnosis_state["intake"]["excluded"],
        "diagnostic_hypotheses": diagnosis_state["diagnostic_hypotheses"],
        "diagnostic_observations": diagnosis_state["intake"]["observations"],
        "normalized_measurements": diagnosis_state["intake"]["measurements"],
        "action_decisions": guardrail_state["decisions"],
        "guardrails": guardrail_state["guards"],
        "protected_scopes": guardrail_state["protected"],
        "case_ranking": scored_state["matched_case_studies"],
        "candidate_action_scores": scored_state["ranked_candidates"],
        "normalized_case_matches": scored_state.get("normalized_case_matches", []),
        "case_informed_action_candidates": scored_state.get(
            "case_informed_action_candidates", []
        ),
        "mandatory_constraint_source": graph["sources"]["ingaze_policy"]["url"],
        "protected_baselines": diagnosis_state["intake"]["protected_baselines"],
        "research": scored_state["supporting_research_snippets"],
        "advocacy_ready_for_pilot": guardrail_state["advocacy_ready"],
        "advocacy_blockers": guardrail_state["blockers"],
        "operational_assumptions": [
            "Peer-gap margins prioritize review and have no statistical or causal interpretation.",
            "A conditional pilot requires verification and Phase 3 requires evaluated results.",
            "Historical ranking weights are retrieval heuristics. T1 is displayed after ranking.",
        ],
        "evidence": {
            signal: [
                row["source_ref"]
                for row in guardrail_state["present"]
                if row["signal"] == signal
            ]
            for signal in sorted(guardrail_state["features"])
        },
    }
    return result, trace


def generate_hr_proposal(
    client_input: Any,
    diagnosis: Any,
    scored: Any,
    guardrails: Any,
    phase_plan: Any,
    llm_client: Optional[StructuredLLMClient] = None,
) -> str:
    """Render upstream decisions as Markdown; optionally polish its summary only.

    Inputs accept Pydantic stage models or the dictionaries produced by the
    current orchestrator. Roadmap actions and guardrails are copied from Steps
    2–5; this formatter does not create or modify decisions.
    """
    client = _to_data(client_input)
    diagnosis_data = _to_data(diagnosis)
    scored_data = _to_data(scored)
    guardrail_data = _to_data(guardrails)
    plan_data = _to_data(phase_plan)

    scenario_code = str(
        client.get("scenario_code") or diagnosis_data.get("scenario_code") or "scenario"
    )
    company = str(client.get("company_name") or client.get("company") or scenario_code)
    industry = client.get("industry_raw") or client.get("industry") or "Unspecified"
    roots = _first_list(plan_data, "diagnosed_root_causes") or _first_list(
        diagnosis_data, "inferred_root_causes", "prioritized_hypotheses", "diagnostic_hypotheses"
    )
    symptoms = _surface_symptoms(diagnosis_data, guardrail_data)
    guards = _first_list(guardrail_data, "guards", "blocked_traps_and_guardrails")
    decisions = _first_list(guardrail_data, "decisions")
    deferred = [
        entry for entry in decisions
        if isinstance(entry, dict)
        and str(entry.get("decision", "")).lower() in {"deferred", "blocked", "paused"}
    ]
    baselines = _healthy_baselines(client, plan_data, diagnosis_data, guardrail_data)
    cohort = client.get("cohort_site_asymmetries") or plan_data.get("cohort")
    noise = _filtered_noise(client, diagnosis_data)
    phase_lists = {
        "Phase 1 — Diagnostics": _first_list(plan_data, "phase_1_actions"),
        "Phase 2 — Scoped Pilots": _first_list(plan_data, "phase_2_actions"),
        "Phase 3 — Scaling Gates": _first_list(plan_data, "phase_3_actions"),
    }
    cases = _first_list(scored_data, "matched_case_studies", "top_matched_cases")[:3]
    research = _first_list(scored_data, "supporting_research_snippets", "selected_research_snippets")
    questions = _first_list(
        plan_data, "open_questions_and_hypotheses_for_client", "open_data_hypotheses"
    ) or _first_list(diagnosis_data, "open_data_hypotheses")

    summary = _deterministic_summary(company, roots, phase_lists, guards)
    if llm_client is not None:
        summary = _polish_summary(
            llm_client,
            summary,
            {
                "company": company,
                "diagnosis": roots,
                "guardrails": guards,
                "phases": phase_lists,
                "approved_precedents": cases,
            },
        )

    lines = [
        f"# HR Proposal — {company}",
        "",
        f"**Scenario:** `{scenario_code}`  ",
        f"**Industry:** {industry}",
        "",
        "## Executive Diagnosis",
        "",
        summary,
        "",
        "### Root-cause hypotheses",
    ]
    lines.extend(_bullet_lines(roots, empty="No root-cause hypotheses were recorded."))
    lines.extend(["", "### Observed surface signals and evidence"])
    lines.extend(_bullet_lines(symptoms, empty="No supported surface observations were recorded."))

    lines.extend(["", '## Guardrails & “Do Not Touch”', "", "### Blocked traps and guardrails"])
    lines.extend(_bullet_lines(guards, empty="No additional guardrails were recorded."))
    lines.extend(["", "### Deferred requests and decisions"])
    lines.extend(_bullet_lines(deferred, empty="No Step 4 decisions were marked deferred."))
    if isinstance(client.get("leadership_requests"), list):
        lines.extend(["", "### Leadership requests captured at intake"])
        lines.extend(_bullet_lines(client["leadership_requests"]))
    elif isinstance(client.get("client_internal_context"), dict):
        request_text = client["client_internal_context"].get("leadership_perceptions_and_requests")
        if request_text:
            lines.extend(["", "### Leadership requests captured at intake", "", f"- {request_text}"])
    lines.extend(["", "### Healthy baselines to preserve"])
    lines.extend(_bullet_lines(baselines, empty="No healthy baseline was recorded."))
    if cohort:
        lines.extend(["", "### Cohort and site asymmetries", "", f"- {_format_entry(cohort)}"])
    if noise:
        lines.extend(["", "### Filtered or quarantined input", ""])
        lines.extend(_bullet_lines(noise))

    lines.extend(["", "## Three-Phase Action Roadmap", ""])
    for heading, actions in phase_lists.items():
        lines.extend([f"### {heading}"])
        lines.extend(_bullet_lines(actions, empty="No actions were scheduled in this phase."))
        lines.append("")

    lines.extend(["## Evidence & Precedents", "", "### Historical case precedents"])
    if cases:
        for case in cases:
            case_data = _to_data(case)
            name = case_data.get("case") or case_data.get("case_name") or "Historical case"
            roi = case_data.get("historical_roi") or case_data.get("measured_roi_summary")
            score = case_data.get("score") or case_data.get("similarity_score")
            reason = case_data.get("transfer_scope") or case_data.get("match_reason")
            lines.append(f"- **{name}**" + (f" (match score: {score})" if score is not None else ""))
            if roi:
                lines.append(f"  - Historical outcome: {roi}")
            if reason:
                lines.append(f"  - Transfer note: {reason}")
    else:
        lines.append("- No historical case matches were returned.")

    lines.extend(["", "### Supporting research"])
    for item in research[:8]:
        item_data = _to_data(item)
        label = item_data.get("source") or item_data.get("title") or item_data.get("source_id") or "Research source"
        finding = item_data.get("finding") or item_data.get("summary") or ""
        url = item_data.get("url")
        lines.append(f"- **{label}:** {finding}" + (f" ([source]({url}))" if url else ""))
    if not research:
        lines.append("- No supporting research snippets were returned.")

    lines.extend(["", "### Open client verification questions"])
    lines.extend(_bullet_lines(questions, empty="No open questions were recorded."))
    lines.extend([
        "",
        "---",
        "This proposal reports deterministic pipeline decisions. Historical outcomes are precedents, not forecasts; scale only after the stated measures and guardrails are verified.",
        "",
    ])
    return "\n".join(lines)


def _to_data(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _to_data(value.model_dump(mode="json"))
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _to_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_data(item) for item in value]
    return value


def _first_list(data: dict, *keys: str) -> list:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def _format_scope(scope: Any) -> str:
    if not isinstance(scope, dict):
        return ""
    labels = []
    for key in ("cohort", "site", "tenure", "window"):
        value = scope.get(key)
        if value not in (None, "", "all", "intake"):
            labels.append(f"{key}: {value}")
    return "; ".join(labels)


def _format_entry(entry: Any) -> str:
    data = _to_data(entry)
    if isinstance(data, str):
        return data
    if not isinstance(data, dict):
        return str(data)
    title = next((data.get(key) for key in (
        "action", "verify", "condition", "hypothesis", "label", "plain_english_summary", "text", "name"
    ) if data.get(key)), None)
    if not title:
        title = data.get("case") or data.get("case_name") or data.get("source") or data.get("finding")
    if not title and data.get("rule"):
        title = str(data["rule"]).replace("_", " ").capitalize()
    title = str(title or json.dumps(data, ensure_ascii=False, sort_keys=True))
    details = []
    for key, label in (
        ("status", "status"), ("decision", "decision"), ("reason", "reason"),
        ("prerequisite", "prerequisite"), ("pilot_design", "pilot design"),
        ("condition", "scale gate"), ("unlock_condition", "unlock condition"),
    ):
        value = data.get(key)
        if value and str(value) != title:
            details.append(f"{label}: {value}")
    scope = _format_scope(data.get("scope"))
    if scope:
        details.append(f"scope: {scope}")
    for key in ("preserve_baselines", "missing_families", "dependent_families"):
        value = data.get(key)
        if value:
            details.append(f"{key.replace('_', ' ')}: {', '.join(map(str, value))}")
    return title + (" — " + "; ".join(details) if details else "")


def _short_entry(entry: Any) -> str:
    """Return the approved decision's main label without its supporting details."""
    data = _to_data(entry)
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in (
            "action", "hypothesis", "condition", "verify", "label",
            "plain_english_summary", "text", "name", "case", "case_name",
        ):
            if data.get(key):
                return str(data[key])
        if data.get("rule"):
            return str(data["rule"]).replace("_", " ")
    return _format_entry(entry)


def _bullet_lines(items: Iterable[Any], empty: Optional[str] = None) -> list:
    values = list(items or [])
    if not values:
        return [f"- {empty}"] if empty else []
    return [f"- {_format_entry(item)}" for item in values]


def _surface_symptoms(diagnosis: dict, guardrails: dict) -> list:
    intake = diagnosis.get("intake", {}) if isinstance(diagnosis.get("intake"), dict) else {}
    observations = intake.get("observations") or diagnosis.get("diagnostic_observations")
    if not isinstance(observations, list):
        observations = guardrails.get("present", [])
    rows = []
    seen = set()
    for item in observations:
        if not isinstance(item, dict) or item.get("state", "present") != "present":
            continue
        if item.get("quality") == "unverified":
            continue
        signal = item.get("signal") or item.get("signal_code")
        scope = _format_scope(item.get("scope"))
        text = item.get("text") or item.get("evidence_quote") or ""
        key = (signal, scope, text)
        if key in seen:
            continue
        seen.add(key)
        label = str(signal or "Reported observation")
        if scope:
            label += f" ({scope})"
        if text:
            label += f": {text}"
        rows.append(label)
        if len(rows) >= 8:
            break
    explained = diagnosis.get("surface_symptoms_explained")
    if not rows and isinstance(explained, list):
        rows.extend(str(item) for item in explained)
    return rows


def _healthy_baselines(client: dict, plan: dict, diagnosis: dict, guardrails: dict) -> list:
    values = []
    source_refs = []
    sources = [
        client.get("healthy_baselines"),
        plan.get("strengths"),
        diagnosis.get("locked_healthy_baselines"),
    ]
    intake = diagnosis.get("intake", {}) if isinstance(diagnosis.get("intake"), dict) else {}
    sources.append(intake.get("protected_baselines"))
    sources.append(guardrails.get("strengths"))
    for source in sources:
        if not source:
            continue
        entries = source if isinstance(source, list) else [source]
        for item in entries:
            if isinstance(item, dict) and item.get("source_ref") and not any(
                item.get(key)
                for key in (
                    "evidence", "asset_or_cohort_name", "baseline", "summary", "metric", "value"
                )
            ):
                source_refs.append(str(item["source_ref"]))
                continue
            else:
                rendered = _format_entry(item)
            if rendered and rendered not in values:
                values.append(rendered)
    return values or source_refs


def _filtered_noise(client: dict, diagnosis: dict) -> list:
    values = _first_list(client, "filtered_noise_items")
    if values:
        return values
    intake = diagnosis.get("intake", {}) if isinstance(diagnosis.get("intake"), dict) else {}
    return _first_list(intake, "excluded") or _first_list(diagnosis, "excluded_noise")


def _deterministic_summary(company: str, roots: list, phases: dict, guards: list) -> str:
    first_root = _short_entry(roots[0]) if roots else "the reported workforce and hiring concerns"
    phase_one = phases["Phase 1 — Diagnostics"]
    phase_two = phases["Phase 2 — Scoped Pilots"]
    first_audit = _short_entry(phase_one[0]) if phase_one else "a scoped diagnostic review"
    first_pilot = _short_entry(phase_two[0]) if phase_two else "a pilot after evidence is verified"
    summary = (
        f"For {company}, the leading diagnosis is {first_root}. Start with {first_audit}; "
        f"advance to {first_pilot} only under its stated prerequisite."
    )
    if guards:
        summary += f" Preserve the listed guardrails, including: {_format_entry(guards[0])}."
    return summary


def _polish_summary(llm_client: StructuredLLMClient, summary: str, approved: Dict[str, Any]) -> str:
    system_prompt = (
        "Polish only the supplied executive summary for clarity. The supplied Step 2–5 JSON is approved and "
        "is the only source of facts. Do not add, remove, or broaden diagnoses, requests, actions, prerequisites, "
        "guardrails, metrics, names, or outcomes. Return one concise paragraph with no headings or bullets."
    )
    user_prompt = json.dumps(
        {"approved_deterministic_summary": summary, "approved_step_2_to_5_data": approved},
        ensure_ascii=False,
        indent=2,
    )
    try:
        response = llm_client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=_ExecutiveSummaryPolish,
        )
    except (RuntimeError, ValueError, TypeError) as exc:
        LOGGER.info("Step 6 used deterministic summary because optional LLM polish was unavailable: %s", exc)
        return summary
    response_data = _to_data(response)
    polished = str(response_data.get("executive_summary", "")).strip()
    if not _is_grounded_polish(polished, summary):
        LOGGER.info("Step 6 ignored optional LLM polish that did not stay close to the approved summary.")
        return summary
    return polished


def _is_grounded_polish(candidate: str, approved_summary: str) -> bool:
    if not candidate or len(candidate) > 600 or "\n" in candidate or re.search(r"^\s*[-*#\d]+[.) ]", candidate):
        return False
    approved_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", approved_summary.casefold()))
    candidate_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", candidate.casefold()))
    if not candidate_tokens:
        return False
    overlap = len(candidate_tokens & approved_tokens) / len(candidate_tokens)
    approved_numbers = set(re.findall(r"\d+(?:\.\d+)?%?", approved_summary))
    candidate_numbers = set(re.findall(r"\d+(?:\.\d+)?%?", candidate))
    return overlap >= 0.8 and candidate_tokens <= approved_tokens and candidate_numbers <= approved_numbers
