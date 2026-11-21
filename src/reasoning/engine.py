#!/usr/bin/env python3
"""Run the Ingaze HR planning prototype and export a judge-ready submission."""

import argparse
import json
import math
import re
from pathlib import Path

from .hr_evidence import load_library, search_library
from .hr_intake import (
    DEFAULT_ANALYTICS, PEER_SIGNALS, REQUEST_FIELD, STRENGTH_FIELD, load_analytics,
    normalize_intake, normalize_metrics, normalize_narrative,
)
from .hr_knowledge_graph import SCOPE_FIELDS, diagnose, graph_export, load_graph, scope_overlaps
from .hr_policy import CASE_TAGS, PROFILE, TRACKS
from starter_baseline_and_validator import validate_submission

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "database" / "ingaze_sandbox_dataset.json"
BLOCKERS = {"expectation_gap", "manager_support", "burnout"}
MECHANISM_WEIGHT = {
    "expectation_gap": 4, "manager_support": 4, "career_clarity": 4,
    "burnout": 3, "mobile_friction": 4, "feedback_fragmentation": 4,
}


def profile_for(value):
    return {tag for tag, pattern in PROFILE.items() if re.search(pattern, value, re.I)}


def precedent_signals(case, graph, snapshot):
    """Associate novel cases with mechanisms using only their starting conditions."""
    intake = {"ingaze_platform_signals": {"initial_challenge": case.get("initial_challenge", "")}}
    text_rows, _ = normalize_narrative(intake, graph)
    metric_rows, _, _ = normalize_metrics(snapshot, graph, case["case_name"])
    tags = {row["signal"] for row in text_rows + metric_rows if row["state"] == "present"}
    for rule in graph["rules"].values():
        if tags.intersection(rule["requires"][rule["direct"]]):
            tags.update(rule.get("track_tags", []))
    return tags


def baseline_fit(client_rows, snapshot, graph, mechanisms):
    if not snapshot or not mechanisms:
        return 0.0, []
    _, measurements, _ = normalize_metrics(snapshot, graph, "historical_t0")
    comparable = {row["metric_path"]: row for row in measurements}
    matches = {}
    for signal in sorted(mechanisms & PEER_SIGNALS.keys()):
        direction, margin = PEER_SIGNALS[signal]
        family = graph["signals"][signal]["family"]
        for path in graph["signals"][signal].get("metrics", []):
            active, previous = client_rows.get(path), comparable.get(path)
            if not active or not previous or any(row["peer_value"] is None for row in (active, previous)):
                continue
            if active["scope"] != previous["scope"] or None in active["scope"].values():
                continue
            if any(active[field] != previous[field] for field in ("unit", "denominator", "measurement_horizon")):
                continue
            current_gap, prior_gap = [
                direction * (row["value"] - row["peer_value"]) for row in (active, previous)
            ]
            shape = 1 - min(abs(current_gap - prior_gap) / (3 * margin), 2)
            evidence = {"metric_path": path, "family": family, "unit": active["unit"],
                        "client_peer_gap": round(current_gap, 4), "case_t0_peer_gap": round(prior_gap, 4),
                        "direction": "adverse is positive" if signal != "culture_ready" else "favorable is positive"}
            if family not in matches or shape < matches[family][0]:
                matches[family] = (shape, evidence)
    score = 3 * sum(value[0] for value in matches.values()) / len(matches) if matches else 0.0
    return score, [value[1] for value in matches.values()]


def case_matches(cases, features, profile, *, graph=None, active=None, case_analytics=None):
    graph = graph or load_graph()
    active = active or {}
    case_analytics = case_analytics or {}
    _, measurements, _ = normalize_metrics(active, graph, "active_t0")
    client_rows = {row["metric_path"]: row for row in measurements}
    ranked = []
    for case in cases:
        name = case["case_name"].split(" (")[0]
        snapshot = case_analytics.get(case["case_name"], {})
        tags = case.get("mechanism_tags")
        if tags is None:
            tags = set(CASE_TAGS.get(name, "").split()) or precedent_signals(case, graph, snapshot)
        elif not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ValueError(f"{name}: mechanism_tags must be a list of strings")
        mechanisms = features.intersection(tags)
        case_profile = profile_for(case["sector_and_profile"])
        shared_context = profile & case_profile
        score = sum(MECHANISM_WEIGHT.get(tag, 2) for tag in mechanisms)
        score += sum(1 if tag == "distributed" else 2 for tag in shared_context)
        if "retail" in case_profile and "retail" not in profile:
            # Mobile funnel design can transfer across deskless roles. Store
            # scheduling and store-specific retention outcomes cannot.
            if "mobile_friction" not in mechanisms:
                score -= 8
        if not mechanisms:
            score -= 10
        quantitative, comparisons = baseline_fit(client_rows, snapshot, graph, mechanisms)
        scale = {}
        for field in ("headcount", "locations_count"):
            actual, historical = active.get(field), snapshot.get(field)
            if type(actual) in (int, float) and type(historical) in (int, float) and actual > 0 and historical > 0:
                scale[field] = round(historical / actual, 3)
        if scale and mechanisms:
            score += sum(max(-1, 1 - abs(math.log2(ratio))) for ratio in scale.values()) / len(scale)
        ranked.append({
            "case": case["case_name"],
            "historical_roi": case["measured_roi"],
            "score": round(score + quantitative, 3),
            "shared_mechanisms": sorted(mechanisms),
            "shared_context": sorted(shared_context),
            "comparable_t0_metrics": comparisons,
            "case_to_client_scale_ratios": scale,
            "outcome_use": "Historical sandbox outcome for context. Challenge telemetry is synthetic and this score is a retrieval heuristic.",
            "transfer_scope": (
                "Use as mobile funnel precedent only. Exclude store scheduling and retail retention outcomes."
                if "retail" in case_profile - profile and "mobile_friction" in mechanisms else
                "Transfer the shared mechanisms. Check workforce and site fit before adapting interventions."
                if mechanisms else "Context only; verify a comparable mechanism before applying."
            ),
        })
    top = sorted(ranked, key=lambda row: (-row["score"], row["case"]))[:3]
    for row in top:
        snapshot = case_analytics.get(row["case"], {})
        _, before, _ = normalize_metrics(snapshot, graph, "historical_t0")
        _, after, _ = normalize_metrics(
            {"t0_current_snapshot": snapshot.get("t1_after_12_months", {})}, graph, "historical_t1"
        )
        baseline = {value["metric_path"]: value for value in before}
        follow_up = {value["metric_path"]: value for value in after}
        row["observed_t0_t1"] = [
            {"metric_path": path, "unit": baseline[path]["unit"], "t0": baseline[path]["value"],
             "t1": follow_up[path]["value"]}
            for comparison in row["comparable_t0_metrics"]
            for path in [comparison["metric_path"]] if path in baseline and path in follow_up
        ]
    return top


def plan(scenario, dataset, evidence_library=(), graph=None, analytics=None):
    if graph is None:
        graph = load_graph()
    analytics = analytics if analytics is not None else {"active": {}, "cases": {}}
    profile = profile_for(" ".join(str(scenario.get(key, "")) for key in (
        "industry", "workforce_target", "headcount_and_footprint", "organizational_context"
    )))
    profile_tags = scenario.get("profile_tags", [])
    if not isinstance(profile_tags, list) or any(not isinstance(tag, str) for tag in profile_tags):
        raise ValueError("profile_tags must be a list of strings")
    profile.update(profile_tags)
    intake = normalize_intake(scenario, graph, analytics)
    hypotheses = diagnose(graph, intake["observations"], profile)
    return plan_from_graph(scenario, dataset, evidence_library, graph, intake, hypotheses, profile, analytics)


def prioritized(hypotheses, observations, graph):
    """Keep supported scopes and the strongest provisional observation per rule."""
    def priority(hypothesis):
        direct = next(slot for slot in hypothesis["evidence_slots"] if slot["direct_slot"])
        evidence = [observations[item] for item in direct["matching_ids"]]
        return (
            hypothesis["status"] == "supported",
            any(graph["signals"][row["signal"]]["role"] == "direct" for row in evidence),
            any(row.get("evidence_type") == "reported_observation" for row in evidence),
            hypothesis["status"] != "conflicted",
            len(hypothesis["evidence_slots"]) - len(hypothesis["missing_families"]),
            sum(value not in (None, "all") for value in hypothesis["scope"].values()),
        )

    seen = set()
    for hypothesis in sorted(hypotheses, key=priority, reverse=True):
        key = hypothesis["rule"]
        if key in seen and hypothesis["status"] != "supported":
            continue
        direct = next(slot for slot in hypothesis["evidence_slots"] if slot["direct_slot"])
        # Keep all hypotheses in the trace. Recommend audits for leads with a
        # mechanism indicator instead of listing every symptom-only alternative.
        if hypothesis["status"] == "supported" or direct["matching_ids"]:
            yield hypothesis
            seen.add(key)


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


def plan_from_graph(scenario, dataset, library, graph, intake, hypotheses, profile, analytics):
    context = scenario.get("client_internal_context", {})
    strengths = context.get(STRENGTH_FIELD)
    cohort = context.get("cohort_and_site_asymmetries")
    requests = str(context.get(REQUEST_FIELD, "")).lower()
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
    guards, decisions = [], []
    roots, audit, pilots, scaling, questions = [], [], [], [], []
    ranked_tags, source_ids = set(), set()
    target = scenario.get("workforce_target")
    hiring_stage_leads = set()
    hiring_stage_families = {"hire_latency", "form_exit", "screening_progression", "offer_progression"}

    for hypothesis in prioritized(hypotheses, observations, graph):
        key, scope, status = hypothesis["rule"], hypothesis["scope"], hypothesis["status"]
        rule = graph["rules"][key]
        source_ids.update(rule.get("sources", []))
        if rule["kind"] != "policy":
            roots.append({"hypothesis": rule["label"], "status": status, "rule": key, "scope": scope,
                          "evidence_ids": hypothesis["evidence_ids"]})
        audit.append({"action": rule["diagnostic"], "scope": scope, "rule": key})
        if status != "supported":
            questions.append({"rule": key, "scope": scope, "verify": rule["diagnostic"],
                              "missing_families": hypothesis["missing_families"],
                              "dependent_families": hypothesis["dependent_families"],
                              "counterevidence_ids": hypothesis["counterevidence_ids"]})
        direct = next(slot for slot in hypothesis["evidence_slots"] if slot["direct_slot"])
        if any(slot["family"] in hiring_stage_families for slot in hypothesis["evidence_slots"]) and (
            hypothesis["status"] != "conflicted" and direct["matching_ids"]
        ):
            hiring_stage_leads.add(key)
        narrative_lead = any(observations[item].get("evidence_type") == "reported_observation"
                             for item in direct["matching_ids"])
        if status != "conflicted":
            ranked_tags.update(rule.get("track_tags", []))

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
        if reason:
            decisions.append({"rule": key, "scope": scope, "decision": "deferred", "reason": reason})
            continue

        prerequisite = "Complete the diagnostic and verify the proposed mechanism in this exact scope."
        if status != "supported":
            prerequisite += " Confirm missing or dependent observations against independent records."
        if strengths:
            prerequisite += " Specify the affected group and preserve the documented healthy baseline."
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
        decisions.append({"rule": key, "scope": scope, "decision": "conditional", "reason": prerequisite})

    advocacy_ready = any(row["rule"] == "advocacy_pilot" for row in pilots)
    if "advoc" in requests or "ambassador" in requests or blockers and "post_tracking" in reported:
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
    if "finance" in requests or "emv" in features:
        audit.append({"action": "Agree auditable outcome definitions with Finance. Separate staff time, hiring outcomes and estimated media cost."})
    if strengths:
        guards.append("Preserve documented strengths. Measure pilot outcomes in the affected group before widening rollout.")
        if "salary bands" in requests:
            guards.append("Defer salary changes pending verified compensation problems in comparable roles.")
        if "evp overhaul" in requests and "culture_ready" in features:
            guards.append("Preserve the healthy employer proposition. Validate local messaging before considering an overhaul.")
    if features.intersection({"hiring_delay", "vacancy_delay"}) and not hiring_stage_leads:
        audit.append({
            "action": "Separate request-to-approval, qualified applicant supply, form completion, recruiter response, interviews and offers. Identify the stage and affected roles before selecting a pilot.",
            "decision": "stage_unknown",
        })
    if not audit:
        audit.append({"action": "Collect observations from independent origins within the same cohort and assessment window."})

    cases = case_matches(
        dataset["raw_case_study_narratives"], ranked_tags, profile, graph=graph,
        active=intake["snapshot"], case_analytics=analytics.get("cases", {}),
    )
    research = [
        {"source_id": key, **graph["sources"][key], "evidence_class": source_class(graph["sources"][key]["kind"])}
        for key in sorted(source_ids)
    ]
    sandbox_ids = {snippet for tag in ranked_tags if tag in TRACKS for snippet in TRACKS[tag][4]}
    research.extend({
        "evidence_class": "organizer_reference", **entry,
        "limitation": "Supplied sandbox reference. Verify the magnitude and applicability independently.",
    } for entry in dataset["raw_empirical_research_snippets"] if entry["snippet_no"] in sandbox_ids)
    research.extend({**entry, "evidence_class": "published_reference"}
                    for entry in search_library(library, topics=ranked_tags))
    result = {
        "scenario_code": scenario["scenario_code"], "diagnosed_root_causes": roots,
        "blocked_traps_and_guardrails": guards, "phase_1_actions": audit, "phase_2_actions": pilots,
        "phase_3_actions": scaling, "matched_case_studies": cases, "supporting_research_snippets": research,
        "strategic_focus_and_do_not_touch": [strengths] if strengths else [],
        "cohort_specific_strategies": [cohort] if cohort else [],
        "open_questions_and_hypotheses_for_client": questions,
    }
    trace = {
        "scenario_code": scenario["scenario_code"], "profile": sorted(profile), "excluded_noise": intake["excluded"],
        "diagnostic_hypotheses": hypotheses, "diagnostic_observations": intake["observations"],
        "normalized_measurements": intake["measurements"], "action_decisions": decisions,
        "guardrails": guards, "protected_scopes": protected, "case_ranking": cases,
        "mandatory_constraint_source": graph["sources"]["ingaze_policy"]["url"],
        "protected_baselines": intake["protected_baselines"],
        "research": research, "advocacy_ready_for_pilot": advocacy_ready, "advocacy_blockers": blockers,
        "operational_assumptions": [
            "Peer-gap margins prioritize review and have no statistical or causal interpretation.",
            "A conditional pilot requires verification and Phase 3 requires evaluated results.",
            "Historical ranking weights are retrieval heuristics. T1 is displayed after ranking.",
        ],
        "evidence": {signal: [row["source_ref"] for row in present if row["signal"] == signal]
                     for signal in sorted(features)},
    }
    return result, trace


def source_class(kind):
    if kind == "hackathon_policy":
        return "mandatory_constraint"
    if kind in {"empirical_study", "vendor_observation"}:
        return "observational_or_context_specific_finding"
    if kind in {"design_guidance", "industry_standard"}:
        return "operational_guidance"
    if kind in {"meta_analysis", "systematic_review", "field_experiment", "quasi_experiment"}:
        return "published_scientific_finding"
    return "unclassified_reference"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--analytics", type=Path, help="Optional companion telemetry file")
    parser.add_argument("--no-analytics", action="store_true", help="Skip loading the companion telemetry file")
    parser.add_argument("--out", type=Path, default=Path("submission.json"))
    parser.add_argument("--trace", action="store_true", help="Print source paths and planning decisions")
    parser.add_argument("--trace-out", type=Path, help="Write the reasoning trace as JSON")
    parser.add_argument("--graph-out", type=Path, help="Write the graph's typed nodes and edges as JSON")
    parser.add_argument("--graph-pack", type=Path, action="append", default=[],
                        help="Load an additional graph JSON pack. May be repeated.")
    parser.add_argument("--observations", type=Path, help="Load scoped observations keyed by scenario code")
    parser.add_argument("--evidence-pack", type=Path, action="append", default=[],
                        help="Load an additional JSON evidence pack. May be repeated.")
    parser.add_argument("--search-evidence", metavar="QUERY", help="Search the evidence library without generating a plan")
    args = parser.parse_args()
    try:
        evidence_library = load_library(args.evidence_pack)
        graph = load_graph(args.graph_pack)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.search_evidence is not None:
        print(json.dumps(search_library(evidence_library, query=args.search_evidence), indent=2, ensure_ascii=False))
        return
    try:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8-sig"))
        scenarios = dataset["company_scenarios_to_diagnose"]
        if args.observations:
            overrides = json.loads(args.observations.read_text(encoding="utf-8-sig"))
            codes = {scenario["scenario_code"] for scenario in scenarios}
            if not isinstance(overrides, dict) or overrides.keys() - codes:
                raise ValueError("Observation file must use scenario codes in the input dataset")
            scenarios = [
                {**scenario, "diagnostic_observations": overrides[scenario["scenario_code"]]}
                if scenario["scenario_code"] in overrides else scenario
                for scenario in scenarios
            ]
        analytics_path = args.analytics or (DEFAULT_ANALYTICS if args.dataset.resolve() == DEFAULT_DATA else None)
        analytics = load_analytics(None if args.no_analytics else analytics_path)
        plans = [plan(scenario, dataset, evidence_library, graph, analytics) for scenario in scenarios]
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    payload = {
        "team_name": "Team 11",
        "chosen_architecture_paradigm": "Evidence extraction, deterministic HR policy and weighted case-based reasoning",
        "scenarios": [result for result, _ in plans],
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    errors, warnings = validate_submission(args.out, dataset, scenarios)
    traces = [trace for _, trace in plans]
    if args.graph_out:
        args.graph_out.write_text(json.dumps(graph_export(graph), indent=2, ensure_ascii=False) + "\n",
                                  encoding="utf-8")
    if args.trace_out:
        args.trace_out.write_text(json.dumps(traces, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.trace:
        print(json.dumps(traces, indent=2, ensure_ascii=False))
    for warning in warnings:
        print(f"Warning: {warning}")
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    print(f"Wrote {args.out} with {len(plans)} scenario plans and {len(warnings)} validation warnings.")


if __name__ == "__main__":
    main()
