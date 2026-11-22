"""Step 5: deterministic diagnostics, scoped pilots, and scaling gates.

The production entrypoint is ``build_reasoning_phase_plan``. It assembles
Phase 1 diagnostics, eligible Phase 2 pilots with prerequisites, Phase 3 scale
gates, and verification questions from Step 4 decisions.
"""

from __future__ import annotations

def tailor_pilot(key, profile, features):
    if key == "application_friction" and "freight" in profile:
        return "At one affected hub, start with a phone-accessible qualification check and offer qualified candidates a callback slot. Track qualified completions and recruiter load."
    if key == "expectation_drift" and "tech" in profile:
        return "Co-write a realistic engineering role preview with the affected teams. Ask recent hires to verify which decisions they can own and where approvals actually sit."
    if key == "feedback_coverage" and "care" in profile:
        return "Pilot a common post-interview survey with a local owner at a regional clinic. Track invitation and response coverage while preserving effective lab recruiting."
    if key == "manual_measurement" and "emv" in features:
        return "Build a source-linked ledger for eligible posts and applicant outcomes. Deduplicate posts and report staff time separately from estimated media costs."
    if key == "advocacy_pilot" and {"existing_advocates", "culture_ready"} <= set(features):
        return "Invite the employees who already post organically into a named opt-in ambassador cohort, add volunteers from the sites with the weakest local reach, and give them role-relevant content rather than corporate copy. Track reach and applicant outcomes per post in the source-linked ledger."
    return None


FAST_TRACK_PREREQUISITE = (
    "Fast track: start in parallel with Phase 1 once its specific check confirms the mechanism in this scope."
)


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
        fast_track = key in guardrails.get("fast_track_rules", ())
        pilot = {"action": rule["pilot"], "scope": scope, "rule": key, "decision": "conditional",
                 "prerequisite": FAST_TRACK_PREREQUISITE if fast_track else prerequisite}
        if fast_track:
            pilot["fast_track"] = True
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
