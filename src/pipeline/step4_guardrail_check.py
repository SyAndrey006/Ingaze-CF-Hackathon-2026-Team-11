"""Step 4: deterministic guardrail decisions for graph-driven candidates.

The production entrypoint is ``evaluate_guardrails``. It checks scored diagnosis
hypotheses against active blockers, protected scopes, workforce fit, evidence
quality, and the minimum evidence score. Decisions and guardrails are passed to
Step 5 and the final report.
"""

from __future__ import annotations

from src.pipeline.step2_root_cause_analysis import SCOPE_FIELDS, scope_overlaps
BLOCKERS = {"expectation_gap", "manager_support", "burnout"}


def protected_intervention(scope, protected, rule):
    """Treat unresolved target scope as potentially overlapping a protected one."""
    return any(
        (not entry.get("rules") or rule in entry["rules"])
        and scope_overlaps(scope, entry["scope"])
        for entry in protected
    )


def action_fit(rule, hypothesis, profile, reported, blockers):
    tags = set(rule.get("action_tags", []))
    pilot = rule["pilot"].lower()
    if "retail_schedule" in tags or ("retail store" in pilot and "shift" in pilot):
        if "retail" not in profile:
            return "Retail store scheduling requires a retail store workforce."
    if "technical_linkedin" in tags or ("linkedin" in pilot and "engineering storytelling" in pilot):
        if "tech" not in profile or "freight" in profile and hypothesis["scope"]["cohort"] in (
            None, "all", "frontline_workforce",
        ):
            return "Technical LinkedIn content requires a verified technical target workforce."
    if "external_advocacy" in tags:
        if hypothesis["rule"] != "advocacy_pilot":
            return "External advocacy must be planned through the target-cohort readiness gate."
        if hypothesis["status"] != "supported" and (
            blockers or not {"culture_ready", "existing_advocates"} <= reported
        ):
            return "Verify target-cohort readiness, account for workload or trust blockers, and confirm participation."
    if "schedule_change" in tags and hypothesis["status"] != "supported":
        return "Verify shift-based work and a roster problem within the same target scope."
    if "compensation" in tags and hypothesis["status"] != "supported":
        return "Verify a comparable-role pay discrepancy before proposing a compensation change."
    return None


def evaluate_guardrails(
    scenario, graph, intake, hypotheses, ranked_hypotheses, profile, scored_state=None
):
    """Evaluate scoped hypotheses and return auditable routing and guardrail state."""
    context = scenario.get("client_internal_context", {})
    strengths = context.get("healthy_metrics_and_strengths_not_to_break")
    requests = str(context.get("leadership_perceptions_and_requests", "")).lower()
    protected = scenario.get("protected_scopes", [])
    if not isinstance(protected, list) or any(
        not isinstance(entry, dict) or not isinstance(entry.get("scope"), dict)
        or not entry["scope"] or entry["scope"].keys() - set(SCOPE_FIELDS)
        or any(not isinstance(value, str) or not value for value in entry["scope"].values())
        or not isinstance(entry.get("rules", []), list)
        or any(not isinstance(key, str) for key in entry.get("rules", []))
        for entry in protected
    ):
        raise ValueError("protected_scopes must contain scope objects and optional rule IDs")

    observations = {row["id"]: row for row in intake["observations"]}
    present = [row for row in observations.values() if row["quality"] != "unverified" and row["state"] == "present"]
    features = {row["signal"] for row in present}
    reported = {row["signal"] for row in present if row.get("evidence_type") != "synthetic_observation"}
    blockers = sorted(reported & (BLOCKERS | {"documented_broken_promise", "manager_practice_verified"}))
    decisions = []
    evaluations = []
    ranked_tags, source_ids = set(), set()
    target = scenario.get("workforce_target")
    hiring_stage_leads = set()
    hiring_stage_families = {"hire_latency", "form_exit", "screening_progression", "offer_progression"}
    ranked_candidates = (scored_state or {}).get("ranked_candidates", [])
    score_checks = []
    precedent_idea_actions = (scored_state or {}).get("case_informed_action_candidates", [])

    for hypothesis in ranked_hypotheses:
        key, scope, status = hypothesis["rule"], hypothesis["scope"], hypothesis["status"]
        score_entry = next((entry for entry in ranked_candidates
                            if entry.get("rule") == key and entry.get("scope") == scope), None)
        candidate_score = score_entry.get("score") if score_entry else None
        rule = graph["rules"][key]
        source_ids.update(rule.get("sources", []))
        if status != "conflicted":
            ranked_tags.update(rule.get("track_tags", []))

        direct = next(slot for slot in hypothesis["evidence_slots"] if slot["direct_slot"])
        if any(slot["family"] in hiring_stage_families for slot in hypothesis["evidence_slots"]) and (
            hypothesis["status"] != "conflicted" and direct["matching_ids"]
        ):
            hiring_stage_leads.add(key)
        narrative_lead = any(observations[item].get("evidence_type") == "reported_observation"
                             for item in direct["matching_ids"])

        reason = None
        if status == "conflicted":
            reason = "Resolve counterevidence before selecting a pilot."
        elif protected_intervention(scope, protected, key):
            reason = "The proposed intervention overlaps an explicitly protected scope."
        else:
            reason = action_fit(rule, hypothesis, profile, reported, blockers)
        if not reason and rule.get("requires_verified_pilot") and status != "supported":
            reason = "Verify the mechanism with independent evidence in the target scope before proposing a pilot."
        if not reason and status != "supported" and not narrative_lead:
            reason = "More scoped evidence is required before proposing this intervention."
        if not reason and candidate_score is None:
            reason = "No Step 3 evidence score was supplied for this diagnosis candidate."
        if not reason and candidate_score < 0.35:
            reason = (
                f"Step 3 evidence score {candidate_score:.3f} is below the 0.350 minimum; "
                "collect more scoped evidence before selecting a pilot."
            )
        score_checks.append({
            "candidate_id": score_entry.get("candidate_id") if score_entry else None,
            "action_title": score_entry.get("action_title") if score_entry else None,
            "rule": key,
            "scope": scope,
            "score": candidate_score,
            "score_breakdown": score_entry.get("score_breakdown") if score_entry else None,
            "minimum_score": 0.35,
            "passed": candidate_score is not None and candidate_score >= 0.35,
        })

        prerequisite = None
        if not reason:
            prerequisite = "Complete the diagnostic and verify the proposed mechanism in this exact scope."
            if status != "supported":
                prerequisite += " Confirm missing or dependent observations against independent records."
            if strengths:
                prerequisite += " Specify the affected group and preserve the documented healthy baseline."
            decisions.append({"rule": key, "scope": scope, "decision": "conditional", "reason": prerequisite})
        else:
            decisions.append({"rule": key, "scope": scope, "decision": "deferred", "reason": reason})
        evaluations.append({
            "hypothesis": hypothesis,
            "rule_id": key,
            "rule": rule,
            "reason": reason,
            "narrative_lead": narrative_lead,
            "prerequisite": prerequisite,
            "target": target,
            "has_strengths": bool(strengths),
        })

    advocacy_ready = any(
        row["rule_id"] == "advocacy_pilot" and row["reason"] is None
        for row in evaluations
    )
    guards = []
    company_advocacy_veto = any(
        entry["scope"] == {"cohort": "all"} and "advocacy_pilot" in entry.get("rules", [])
        and entry.get("source_ref")
        for entry in protected
    )
    if company_advocacy_veto:
        guards.append("Block public employee advocacy under the client's explicit restriction.")
    elif "advoc" in requests or "ambassador" in requests or blockers and "post_tracking" in reported:
        if advocacy_ready:
            guards.append("Limit advocacy to an opt-in cohort pilot after readiness and reporting checks. Defer broad automation.")
        else:
            guards.append("Defer external advocacy until target-cohort readiness, participation and trust are verified.")
    if "freight" in profile and "linkedin" in requests:
        guards.append("Exclude technical LinkedIn storytelling as the primary driver channel. Preserve proven HQ hiring channels.")
    if "retail" not in profile and (
        "retail" in requests and "shift" in requests
        or any("shift" in row.get("text", "").lower() for row in intake["excluded"])
    ):
        guards.append("Exclude retail store shift rotation for this non-retail workforce.")
    if "fast-apply" in requests:
        guards.append("Defer fast-apply deployment until a scoped form audit and pilot establish the benefit.")
    if strengths:
        guards.append("Preserve documented strengths. Measure pilot outcomes in the affected group before widening rollout.")
        if "salary bands" in requests:
            guards.append("Defer salary changes pending verified compensation problems in comparable roles.")
        if "evp overhaul" in requests and "culture_ready" in features:
            guards.append("Preserve the healthy employer proposition. Validate local messaging before considering an overhaul.")

    return {
        "context": context,
        "strengths": strengths,
        "cohort": context.get("cohort_and_site_asymmetries"),
        "requests": requests,
        "protected": protected,
        "observations": observations,
        "present": present,
        "features": features,
        "reported": reported,
        "blockers": blockers,
        "decisions": decisions,
        "evaluations": evaluations,
        "guards": guards,
        "advocacy_ready": advocacy_ready,
        "ranked_tags": ranked_tags,
        "source_ids": source_ids,
        "target": target,
        "hiring_stage_leads": hiring_stage_leads,
        "hiring_stage_families": hiring_stage_families,
        "score_checks": score_checks,
        "precedent_idea_actions": precedent_idea_actions,
        "precedent_idea_policy": (
            "Case actions are precedent ideas only; they do not bypass the live diagnosis, "
            "score threshold, or deterministic guardrails."
        ),
    }
