"""Step 6: deterministic, auditable HR proposal formatting.

The JSON submission is assembled independently. This module renders approved
Steps 2 through 5 decisions as an executive-readable Markdown proposal.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.utils.llm_client import StructuredLLMClient

LOGGER = logging.getLogger(__name__)


class _ExecutiveProposalPolish(BaseModel):
    """Structured response containing a polished proposal, not new decisions."""

    proposal_markdown: str = Field(..., min_length=1, max_length=30000)


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
    """Format approved Steps 2–5 decisions; optionally polish the whole brief."""
    client, diagnosis_data = _as_dict(client_input), _as_dict(diagnosis)
    scored_data, guardrail_data, plan_data = map(_as_dict, (scored, guardrails, phase_plan))
    scenario_code = str(client.get("scenario_code") or diagnosis_data.get("scenario_code") or "scenario")
    company = str(client.get("company_name") or client.get("company") or scenario_code)
    industry = _clean_text(client.get("industry_raw") or client.get("industry") or "")
    roots = _first_list(plan_data, "diagnosed_root_causes") or _first_list(
        diagnosis_data, "inferred_root_causes", "prioritized_hypotheses", "diagnostic_hypotheses"
    )
    symptoms = _surface_symptoms(diagnosis_data, guardrail_data)
    guards = _first_list(guardrail_data, "guards", "blocked_traps_and_guardrails")
    decisions = _first_list(guardrail_data, "decisions")
    deferred = [row for row in decisions if isinstance(row, dict) and str(row.get("decision", "")).casefold() in {"deferred", "blocked", "paused"}]
    baselines = _healthy_baselines(client, plan_data, diagnosis_data, guardrail_data)
    asymmetries = _asymmetries(client, plan_data)
    noise = _filtered_noise(client, diagnosis_data, guardrail_data)
    phases = {
        "Phase 1 — Diagnostics": _first_list(plan_data, "phase_1_actions"),
        "Phase 2 — Scoped Pilots": _first_list(plan_data, "phase_2_actions"),
        "Phase 3 — Scaling Gates": _first_list(plan_data, "phase_3_actions"),
    }
    cases = _first_list(scored_data, "matched_case_studies", "top_matched_cases")[:3]
    research = _first_list(scored_data, "supporting_research_snippets", "selected_research_snippets")
    questions = _verification_questions(
        _first_list(plan_data, "open_questions_and_hypotheses_for_client", "open_data_hypotheses")
        or _first_list(diagnosis_data, "open_data_hypotheses"), phases["Phase 1 — Diagnostics"]
    )
    leadership = _first_list(client, "leadership_requests")
    approved = {
        "company": company, "industry": industry, "root_causes": roots, "signals": symptoms,
        "guardrails": guards, "deferred_decisions": deferred, "healthy_baselines": baselines,
        "asymmetries": asymmetries, "filtered_noise": noise, "leadership_requests": leadership,
        "phase_actions": phases, "matched_cases": cases, "research": research, "questions": questions,
    }
    draft = _render_proposal(
        company, scenario_code, industry, roots, symptoms, guards, deferred, baselines,
        asymmetries, noise, leadership, phases, cases, research, questions,
    )
    if llm_client is None:
        return draft
    return _polish_proposal(llm_client, draft, approved) or draft


def _to_data(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="json")
        except TypeError:
            dumped = value.model_dump()
        if isinstance(dumped, (dict, list, tuple, set, frozenset)):
            return _to_data(dumped)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _to_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_data(item) for item in value]
    return value


def _as_dict(value: Any) -> dict:
    data = _to_data(value)
    return data if isinstance(data, dict) else {}


def _first_list(data: dict, *keys: str) -> list:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (list, tuple)) and value:
            return list(value)
    return []


def _humanize(value: Any) -> str:
    text = str(value or "").replace("_", " ").replace("-", " ")
    return " ".join(word if word.isupper() else word.capitalize() for word in text.split())


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"/client_intake_case/[^\s,;:]+:?", "", text, flags=re.I)
    text = re.sub(r"\bclient_internal_context\.[\w.#/-]+", "", text, flags=re.I)
    text = re.sub(r"\b(?:missing|dependent) families\s*:\s*[^.;]+[.;]?", "", text, flags=re.I)
    text = re.sub(r"\bpreserve baselines\s*:\s*[^.;]+[.;]?", "", text, flags=re.I)
    text = re.sub(r"\b(?:status|decision)\s*:\s*(?:plausible|conditional|supported|deferred|blocked|paused)\b", "", text, flags=re.I)
    text = re.sub(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", lambda match: _humanize(match.group()), text)
    return re.sub(r"\s+([,.;:])", r"\1", re.sub(r"\s{2,}", " ", text)).strip(" ;,-")


def _format_scope(scope: Any) -> str:
    if not isinstance(scope, dict):
        return ""
    parts = []
    for key in ("site", "cohort", "tenure"):
        value = scope.get(key)
        if not value or str(value).casefold() in {"all", "intake"}:
            continue
        if key == "tenure":
            value = {"new_or_early_tenure": "new hires", "early_tenure": "new hires", "applicant": "applicants"}.get(str(value).casefold(), _humanize(value))
        else:
            value = _humanize(value)
            if key == "cohort":
                value = re.sub(r"\bWorkforce\b", "", value).strip()
        if value and value not in parts:
            parts.append(value)
    if len(parts) > 1:
        return f"{parts[0]} — {', '.join(parts[1:])}"
    return ", ".join(parts)


def _format_baseline(entry: Any) -> str:
    data = _to_data(entry)
    if not isinstance(data, dict):
        return _clean_text(data)
    name = data.get("asset_or_cohort_name") or data.get("name") or data.get("baseline") or "Healthy baseline"
    evidence = data.get("evidence") or data.get("summary") or data.get("metric") or data.get("value") or ""
    preserve = data.get("do_not_touch_scope") or data.get("protected_scope") or "Preserve this strength"
    line = f"**{_clean_text(name)}:** {_clean_text(evidence)}" if evidence else f"**{_clean_text(name)}**"
    return line + (f" — *Action: {_clean_text(preserve)}*" if preserve else "")


def _format_noise(entry: Any) -> str:
    data = _to_data(entry)
    if not isinstance(data, dict):
        return _clean_text(data)
    topic = data.get("inferred_mismatched_action_or_topic") or data.get("topic") or data.get("label") or data.get("raw_excerpt") or "Unverified item"
    reason = data.get("reason_filtered") or data.get("reason") or "Excluded during input review."
    topic = _humanize(topic)
    topic = topic[:1].upper() + topic[1:] if topic else "Unverified item"
    return f"**{_clean_text(topic)} (excluded):** {_clean_text(reason)}"


def _format_entry(entry: Any) -> str:
    data = _to_data(entry)
    if not isinstance(data, dict):
        return _clean_text(data)
    if "asset_or_cohort_name" in data or "do_not_touch_scope" in data:
        return _format_baseline(data)
    if "reason_filtered" in data or "inferred_mismatched_action_or_topic" in data:
        return _format_noise(data)
    if "struggling_segment" in data or "healthy_comparison_segment" in data:
        return _format_asymmetry(data)
    title = next((data.get(key) for key in (
        "action", "verify", "condition", "hypothesis", "plain_english_summary", "label", "text", "name", "reason", "finding", "summary"
    ) if data.get(key)), None)
    if title is None:
        title = _humanize(data.get("rule")) if data.get("rule") else "Recorded item"
    text = _clean_text(title)
    scope = _format_scope(data.get("scope"))
    return f"{text} ({scope})" if scope else text


def _format_asymmetry(entry: Any) -> str:
    data = _to_data(entry)
    if not isinstance(data, dict):
        return _clean_text(data)
    struggling = data.get("struggling_segment") or data.get("struggling_cohort")
    healthy = data.get("healthy_comparison_segment") or data.get("healthy_segment")
    if struggling and healthy:
        return (f"**Needs attention — {_clean_text(struggling)}:** {_clean_text(data.get('struggling_evidence', ''))} "
                f"**Healthy comparison — {_clean_text(healthy)}:** {_clean_text(data.get('healthy_evidence', ''))}")
    return _format_entry(data)


def _format_action(entry: Any, phase: int) -> str:
    data = _to_data(entry)
    if not isinstance(data, dict):
        return _format_entry(data)
    title = data.get("action") or data.get("condition") or data.get("verify") or data.get("hypothesis")
    text = _clean_text(title or "Approved action")
    scope = _format_scope(data.get("scope"))
    if scope:
        text += f" ({scope})"
    if phase == 2 and data.get("pilot_design"):
        text += f" *Pilot design:* {_clean_text(data['pilot_design'])}"
    return text


def _format_leadership(entry: Any) -> str:
    data = _to_data(entry)
    if not isinstance(data, dict):
        return _clean_text(data)
    role = _clean_text(data.get("stakeholder_role") or "Leadership")
    action = _clean_text(data.get("requested_action_text") or data.get("action") or "Request recorded")
    category = data.get("inferred_action_category")
    return f"**{role}:** {action}" + (f" (category: {_humanize(category)})" if category else "")


def _surface_symptoms(diagnosis: dict, guardrails: dict) -> list:
    intake = diagnosis.get("intake", {}) if isinstance(diagnosis.get("intake"), dict) else {}
    observations = intake.get("observations") or diagnosis.get("diagnostic_observations") or guardrails.get("present", [])
    result, seen = [], set()
    for item in observations if isinstance(observations, list) else []:
        if not isinstance(item, dict) or item.get("state", "present") != "present" or item.get("quality") == "unverified":
            continue
        label = _humanize(item.get("signal") or item.get("signal_code") or "Reported observation")
        scope = _format_scope(item.get("scope"))
        evidence = item.get("text") or item.get("evidence_quote")
        if scope:
            label += f" ({scope})"
        if evidence:
            label += f": {_clean_text(evidence)}"
        if label.casefold() not in seen:
            result.append(label)
            seen.add(label.casefold())
        if len(result) == 8:
            break
    if not result:
        result = [_humanize(item) for item in diagnosis.get("surface_symptoms_explained", [])]
    return result


def _healthy_baselines(client: dict, plan: dict, diagnosis: dict, guardrails: dict) -> list:
    intake = diagnosis.get("intake", {}) if isinstance(diagnosis.get("intake"), dict) else {}
    sources = (client.get("healthy_baselines"), plan.get("strengths"), diagnosis.get("locked_healthy_baselines"), intake.get("protected_baselines"), guardrails.get("strengths"))
    result, seen = [], set()
    for source in sources:
        if not source:
            continue
        for entry in source if isinstance(source, list) else [source]:
            data = _to_data(entry)
            if isinstance(data, dict) and data.get("source_ref") and not any(data.get(key) for key in ("evidence", "asset_or_cohort_name", "baseline", "summary", "metric", "value")):
                continue
            text = _format_baseline(data)
            identity = data.get("evidence") or data.get("summary") or text if isinstance(data, dict) else text
            key = re.sub(r"\W+", " ", str(identity).casefold()).strip()
            if text and key not in seen:
                result.append(text)
                seen.add(key)
    return result


def _asymmetries(client: dict, plan: dict) -> list:
    values = client.get("cohort_site_asymmetries") or plan.get("cohort")
    result, seen = [], set()
    for entry in values if isinstance(values, list) else ([values] if values else []):
        text = _format_asymmetry(entry)
        if text and text.casefold() not in seen:
            result.append(text)
            seen.add(text.casefold())
    return result


def _filtered_noise(client: dict, diagnosis: dict, guardrails: dict) -> list:
    intake = diagnosis.get("intake", {}) if isinstance(diagnosis.get("intake"), dict) else {}
    values = _first_list(client, "filtered_noise_items") or _first_list(guardrails, "filtered_noise_traps") or _first_list(intake, "excluded") or _first_list(diagnosis, "excluded_noise")
    result, seen = [], set()
    for entry in values:
        text = _format_noise(entry)
        if text and text.casefold() not in seen:
            result.append(text)
            seen.add(text.casefold())
    return result


def _verification_questions(questions: list, phase_one: list) -> list:
    actions = [_format_action(item, 1).casefold() for item in phase_one]
    family_prompts = {
        "employee_exits": "Confirm comparable exit records by cohort and tenure.",
        "hire_latency": "Confirm stage-to-stage hiring and interview timing for the targeted roles.",
        "screening_progression": "Confirm screening progression by role and candidate cohort.",
        "offer_progression": "Confirm offer acceptance and decline reasons for the targeted roles.",
    }
    result, seen = [], set()
    for item in questions:
        data = _to_data(item)
        candidates = []
        if isinstance(data, dict):
            if data.get("verify"):
                candidates.append(_clean_text(data["verify"]))
            for family in (data.get("missing_families", []) or []) + (data.get("dependent_families", []) or []):
                if str(family) in family_prompts:
                    candidates.append(family_prompts[str(family)])
        elif item:
            candidates.append(_clean_text(item))
        for text in candidates:
            if isinstance(data, dict):
                covered_family = any(
                    family == "employee_exits" and any(
                        "exit" in action and any(word in action for word in ("compare", "review", "reconcile"))
                        for action in actions
                    )
                    or family == "hire_latency" and any(
                        "interview" in action and any(word in action for word in ("scheduling", "timing", "measure"))
                        for action in actions
                    )
                    for family in (data.get("missing_families", []) or []) + (data.get("dependent_families", []) or [])
                )
                if covered_family and text in family_prompts.values():
                    continue
            key = re.sub(r"\W+", " ", text.casefold()).strip()
            words = {word for word in key.split() if len(word) > 3}
            covered = any(key in action or (words and len(words & set(action.split())) / len(words) >= .7) for action in actions)
            if key and key not in seen and not covered:
                result.append(text)
                seen.add(key)
    return result


def _shared_gate(actions: list) -> str:
    gates = []
    for action in actions:
        data = _to_data(action)
        if isinstance(data, dict):
            gate = data.get("prerequisite") or data.get("unlock_condition")
            if gate:
                concise = re.split(r"(?<=[.!?])\s+", _clean_text(gate), maxsplit=1)[0]
                if concise and concise.casefold() not in {item.casefold() for item in gates}:
                    gates.append(concise)
    return " ".join(gates[:2])


def _render_proposal(company, scenario_code, industry, roots, symptoms, guards, deferred,
                     baselines, asymmetries, noise, leadership, phases, cases, research, questions) -> str:
    root = _format_entry(roots[0]) if roots else "the concerns reported by the client"
    audit = _format_action(phases["Phase 1 — Diagnostics"][0], 1) if phases["Phase 1 — Diagnostics"] else "a focused diagnostic review"
    root = root[:1].lower() + root[1:] if root else root
    summary = f"The leading hypothesis is that {root}. Begin with this diagnostic: {audit}. Use the findings to decide whether a scoped pilot is justified; expand only after its agreed measures are reviewed."
    lines = [f"# HR Proposal — {_clean_text(company)}", "", f"**Scenario:** `{_clean_text(scenario_code)}`"]
    if industry:
        lines.append(f"**Industry:** {industry}")
    _section(lines, "Executive Summary", [summary])

    problems = []
    if roots:
        problems += ["### Root-cause hypotheses", ""] + [f"- {_format_entry(item)}" for item in roots]
    if symptoms:
        if problems:
            problems += ["", "### Reported signals", ""]
        else:
            problems += ["### Reported signals", ""]
        problems += [f"- {item}" for item in symptoms]
    _section(lines, "Key Problems", problems)

    protect = []
    if guards:
        protect += ["### Guardrails", ""] + [f"- {_format_entry(item)}" for item in guards]
    if deferred:
        protect += (["", "### Deferred requests", ""] if protect else ["### Deferred requests", ""])
        protect += [f"- {_format_deferred(item)}" for item in deferred]
    if leadership:
        protect += (["", "### Leadership requests" , ""] if protect else ["### Leadership requests", ""])
        protect += [f"- {_format_leadership(item)}" for item in leadership]
    if baselines:
        protect += (["", "### Strengths to protect", ""] if protect else ["### Strengths to protect", ""])
        protect += [f"- {item}" for item in baselines]
    if asymmetries:
        protect += ["", "### Cohort and site differences", ""] + [f"- {item}" for item in asymmetries]
    if noise:
        protect += ["", "### Excluded input", ""] + [f"- {item}" for item in noise]
    _section(lines, "What NOT to Do / Strengths to Protect", protect)

    plan = []
    for number, (heading, actions) in enumerate(phases.items(), start=1):
        if not actions:
            continue
        if plan:
            plan.append("")
        plan += [f"### {heading}", ""]
        if number in (2, 3):
            gate = _shared_gate(actions)
            if gate:
                plan += [f"*Shared gate: {gate}*", ""]
        plan += [f"- {_format_action(action, number)}" for action in actions]
    _section(lines, "Three-Phase Action Plan", plan)

    evidence = []
    if cases:
        evidence += ["### Historical case precedents", ""]
        for case in cases:
            row = _as_dict(case)
            name = row.get("case") or row.get("case_name") or row.get("name") or "Historical case"
            outcome = row.get("historical_roi") or row.get("measured_roi_summary") or row.get("roi_summary")
            text = f"- **{_clean_text(name)}**" + (f" — {_clean_text(outcome)}" if outcome else "")
            evidence.append(text)
    if research:
        evidence += (["", "### Supporting research", ""] if evidence else ["### Supporting research", ""])
        for item in research[:8]:
            row = _as_dict(item)
            source = _humanize(row.get("source") or row.get("title") or row.get("source_id") or "Research source")
            finding = row.get("finding") or row.get("summary") or row.get("text")
            url = row.get("url")
            evidence.append(
                f"- **{_clean_text(source)}**"
                + (f": {_clean_text(finding)}" if finding else "")
                + (f" ([source]({url}))" if url else "")
            )
    if questions:
        evidence += (["", "### Questions for HR to confirm", ""] if evidence else ["### Questions for HR to confirm", ""])
        evidence += [f"- {_clean_text(item)}" for item in questions]
    _section(lines, "Precedents & Next Steps", evidence)
    lines += ["", "---", "Historical results are reference points, not forecasts. Consider wider rollout only after reviewing agreed pilot measures.", ""]
    return "\n".join(lines)


def _section(lines: list, heading: str, content: list) -> None:
    content = list(content)
    while content and not content[0].strip():
        content.pop(0)
    while content and not content[-1].strip():
        content.pop()
    if content:
        lines += ["", f"## {heading}", "", *content]


def _format_deferred(entry: Any) -> str:
    data = _to_data(entry)
    if not isinstance(data, dict):
        return _format_entry(data)
    name = _humanize(data.get("rule") or "Request")
    return f"**{name}:** {_clean_text(data.get('reason') or data.get('unlock_condition') or 'Hold until the evidence is verified.')}"


def _polish_proposal(llm_client: StructuredLLMClient, draft: str, approved: Dict[str, Any]) -> Optional[str]:
    system_prompt = (
        "Rewrite the complete deterministic draft as a concise, jargon-free HR executive brief with its "
        "Executive Summary, Key Problems, What NOT to Do / Strengths to Protect, 3-Phase Action Plan, and "
        "Precedents & Next Steps sections where relevant. The approved Steps 2–5 payload and draft are the "
        "only factual sources. Do not invent or add any actions, metrics, root causes, case outcomes, "
        "recommendations, scope, prerequisites, or evidence. Preserve all approved decisions and meaning. "
        "Do not include raw JSON, internal IDs, routing labels, or implementation metadata. Keep all "
        "percentages and currency amounts grounded in the approved data. Use temperature 0.0."
    )
    prompt = json.dumps({"deterministic_draft": draft, "approved_steps_2_to_5_payload": approved}, ensure_ascii=False, indent=2)
    try:
        response = llm_client.generate_structured(system_prompt=system_prompt, user_prompt=prompt, response_model=_ExecutiveProposalPolish)
        data = _to_data(response)
        candidate = str(data.get("proposal_markdown", "")).strip() if isinstance(data, dict) else ""
    except Exception as exc:
        LOGGER.info("Step 6 used deterministic Markdown because optional LLM polish failed: %s", exc)
        return None
    if not _is_grounded_polish(candidate, approved):
        LOGGER.info("Step 6 ignored optional LLM polish that failed grounding checks.")
        return None
    return candidate


_PERCENT_RE = re.compile(r"(?<![\w.])([+-]?\d+(?:[.,]\d+)?)\s*(%|percent(?:age)?\b)", re.I)
_CURRENCY_RE = re.compile(r"(?<!\w)(?:€|\$|£|EUR\s*|USD\s*|GBP\s*)([+-]?\d[\d, .]*(?:\d)?)(?:\s*(?:k|m|million|thousand))?(?!\w)", re.I)


def _grounded_amounts(text: str) -> set:
    values = set()
    for match in _PERCENT_RE.finditer(text):
        values.add(("percent", match.group(1).replace(",", ".")))
    for match in _CURRENCY_RE.finditer(text):
        amount = re.sub(r"[ ,]", "", match.group(1)).replace(",", ".")
        phrase = match.group(0).casefold()
        currency = "eur" if "€" in phrase or "eur" in phrase else "usd" if "$" in phrase or "usd" in phrase else "gbp"
        values.add((currency, amount))
    return values


def _is_grounded_polish(candidate: str, approved_data: Any) -> bool:
    """Require readable text and ensure all percentages/money are already approved."""
    if not isinstance(candidate, str) or not candidate.strip() or "{" in candidate or "}" in candidate:
        return False
    try:
        approved_text = json.dumps(_to_data(approved_data), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        approved_text = str(approved_data)
    return _grounded_amounts(candidate) <= _grounded_amounts(approved_text)
