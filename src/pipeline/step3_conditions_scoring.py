"""Step 3: deterministic candidate scoring and precedent/research retrieval.

The production orchestrator calls ``score_diagnostic_candidates`` with Step 2
hypotheses, the active graph, the sandbox narratives, and the reviewed normalized
case store. It scores supported diagnosis candidates, retrieves evidence-backed
cases and research, and returns results consumed by Steps 4 and 6. Live
universal rules are read from the knowledge graph and Python formulas.
"""

from __future__ import annotations

import math
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from src.pipeline.step2_root_cause_analysis import (
    FEATURES, PEER_SIGNALS, PROFILE, TRACKS, load_graph, normalize_metrics,
    normalize_narrative, profile_for,
)

from src.schemas.pipeline_models import NormalizedClientInput

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NORMALIZED_CASES = REPO_ROOT / "database" / "normalized" / "normalized_cases.json"
DEFAULT_NORMALIZED_RULES = REPO_ROOT / "database" / "normalized" / "normalized_rules.json"


MECHANISM_WEIGHT = {
    "expectation_gap": 4, "manager_support": 4, "career_clarity": 4,
    "burnout": 3, "mobile_friction": 4, "feedback_fragmentation": 4,
}


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
            tags = precedent_signals(case, graph, snapshot)
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


def score_diagnostic_candidates(
    diagnosis_state, dataset, library, graph, analytics, normalized_client_input=None
):
    """Score Step 2's diagnosis candidates and retrieve supporting precedents.

    The evidence score is deliberately independent of company identity. It makes
    the diagnosis-to-guardrail handoff auditable while retaining the legacy
    graph rule ranking as the stable tie-break order.
    """
    profile = set(diagnosis_state["profile"])
    intake = diagnosis_state["intake"]
    hypotheses = diagnosis_state["diagnostic_hypotheses"]
    ranked_hypotheses = diagnosis_state["prioritized_hypotheses"]
    observations = {row["id"]: row for row in intake["observations"]}

    evidence_scores = []
    for diagnosis_rank, hypothesis in enumerate(ranked_hypotheses, start=1):
        slots = hypothesis.get("evidence_slots", [])
        matched_slots = [slot for slot in slots if slot.get("matching_ids")]
        direct_slots = [slot for slot in slots if slot.get("direct_slot")]
        direct_ids = [
            observation_id
            for slot in direct_slots
            for observation_id in slot.get("matching_ids", [])
        ]
        status_score = {"supported": 1.0, "plausible": 0.55, "conflicted": 0.0}.get(
            hypothesis.get("status"), 0.0
        )
        slot_coverage = len(matched_slots) / len(slots) if slots else 0.0
        direct_evidence = 1.0 if direct_ids else 0.0
        reported_evidence = 1.0 if any(
            observations.get(observation_id, {}).get("evidence_type") == "reported_observation"
            for observation_id in direct_ids
        ) else 0.0
        scope = hypothesis.get("scope", {})
        specific_values = sum(value not in (None, "", "all") for value in scope.values())
        scope_specificity = specific_values / max(1, len(scope))
        evidence_components = {
            "status_support": round(status_score, 4),
            "evidence_slot_coverage": round(slot_coverage, 4),
            "direct_evidence": round(direct_evidence, 4),
            "reported_evidence": round(reported_evidence, 4),
            "scope_specificity": round(scope_specificity, 4),
        }
        total_score = (
            0.40 * status_score
            + 0.25 * slot_coverage
            + 0.15 * direct_evidence
            + 0.15 * reported_evidence
            + 0.05 * scope_specificity
        )
        evidence_scores.append({
            "rule": hypothesis["rule"],
            "scope": scope,
            "status": hypothesis["status"],
            "diagnosis_rank": diagnosis_rank,
            "evidence_score": round(total_score, 4),
            "evidence_score_breakdown": evidence_components,
            "matched_evidence_ids": sorted({
                observation_id
                for slot in slots
                for observation_id in slot.get("matching_ids", [])
            }),
        })

    ranked_tags, source_ids = set(), set()
    for hypothesis in ranked_hypotheses:
        rule = graph["rules"][hypothesis["rule"]]
        source_ids.update(rule.get("sources", []))
        if hypothesis["status"] != "conflicted":
            ranked_tags.update(rule.get("track_tags", []))

    from src.offline.case_matching import (
        candidate_actions_from_cases,
        load_scoring_weights,
        rank_top_cases,
    )
    from src.offline.case_signal_bridge import client_match_profile, signals_for_track_tags
    from src.offline.database_loader import load_normalized_cases

    # Client profile for precedent matching: Step 1 canonical signals when present,
    # otherwise a concept-level translation of the deterministic Step 2 diagnosis.
    client_input = (
        NormalizedClientInput.model_validate(normalized_client_input)
        if normalized_client_input is not None else None
    )
    if client_input is not None and client_input.canonical_signals:
        client_signals = [signal.signal_code for signal in client_input.canonical_signals]
        client_workforce = list(client_input.workforce_archetypes)
        client_sector = client_input.sector_category
        case_match_input_source = "step1_canonical_signals"
    else:
        client_signals, client_workforce, client_sector = client_match_profile(
            ranked_tags, profile, ranked_hypotheses, diagnosis_state.get("workforce_target")
        )
        case_match_input_source = "step2_track_tags_via_case_signal_bridge"

    normalized_case_matches = []
    normalized_case_candidate_actions = []
    cases_by_id = {}
    if client_signals:
        cases_db = load_normalized_cases(DEFAULT_NORMALIZED_CASES)
        reviewed_cases = [
            case for case in cases_db.cases
            if case.curation_review_status == "reviewed"
        ]
        if not reviewed_cases:
            raise ValueError(
                f"{DEFAULT_NORMALIZED_CASES} has no human-reviewed cases; "
                "Step 3 will not use unreviewed case drafts as precedents."
            )
        # The supplied dataset decides which precedents are available (e.g. the
        # historical replay withholds the company under test and its outcomes).
        available_names = {case["case_name"] for case in dataset.get("raw_case_study_narratives", [])}
        reviewed_cases = [case for case in reviewed_cases if case.case_name in available_names]
        cases_db = cases_db.model_copy(update={"cases": reviewed_cases})
        cases_by_id = {case.case_id: case for case in reviewed_cases}
        weights = load_scoring_weights(DEFAULT_NORMALIZED_RULES)
        ranked_normalized = rank_top_cases(
            cases_db,
            client_signals=client_signals,
            workforce=client_workforce,
            sector=client_sector,
            weights=weights,
        )
        normalized_case_matches = [
            {
                **ranked.match.model_dump(mode="json"),
                "match_reason": ranked.reason,
                "curation_review_status": cases_by_id[ranked.match.case_id].curation_review_status,
                "match_input_source": case_match_input_source,
            }
            for ranked in ranked_normalized
        ]
        action_candidates = candidate_actions_from_cases(
            cases_db,
            client_signals=client_signals,
            workforce=client_workforce,
            sector=client_sector,
        )
        normalized_case_candidate_actions = [
            {
                "action_category": action.value,
                "case_id": case_id,
                "case_name": cases_by_id[case_id].case_name,
                "phase_bucket": int(phase),
                "use": "precedent_idea_for_review",
            }
            for action, case_id, phase in action_candidates
        ]

    legacy_cases, research = score_cases_and_research(
        dataset,
        library,
        graph,
        intake,
        profile,
        analytics,
        ranked_tags,
        source_ids,
        include_legacy_cases=not bool(normalized_case_matches),
    )
    recommendation_case_rows = legacy_cases
    if normalized_case_matches:
        recommendation_case_rows = []
        client_snapshot = intake.get("snapshot") or {}
        for match_record in normalized_case_matches:
            case = cases_by_id[match_record["case_id"]]
            shared_context = sorted(
                {w.value for w in case.workforce_archetypes} & {getattr(w, "value", w) for w in client_workforce}
            )
            if client_sector is not None and case.sector_category == client_sector:
                shared_context.append(case.sector_category.value)
            scale = {}
            for field in ("headcount", "locations_count"):
                actual, historical = client_snapshot.get(field), getattr(case, field)
                if type(actual) in (int, float) and type(historical) in (int, float) and actual > 0 and historical > 0:
                    scale[field] = round(historical / actual, 3)
            compatibility_row = dict(match_record)
            compatibility_row.update({
                "case": match_record["case_name"],
                "historical_roi": match_record["measured_roi_summary"],
                "score": match_record["similarity_score"],
                "shared_mechanisms": match_record["matched_problem_tags"],
                "shared_context": shared_context,
                "comparable_t0_metrics": [],
                "case_to_client_scale_ratios": scale,
                "outcome_use": (
                    "Historical sandbox outcome for context; this is a precedent, "
                    "not a causal guarantee."
                ),
                "transfer_scope": match_record["match_reason"],
            })
            recommendation_case_rows.append(compatibility_row)

    ranked_candidates = []
    for candidate in evidence_scores:
        rule = graph["rules"][candidate["rule"]]
        track_tags = set(rule.get("track_tags", []))
        if normalized_case_matches:
            # Same semantics as the legacy branch, on canonical signals: the share of
            # this candidate's mechanisms that a top precedent actually faced.
            candidate_signals = signals_for_track_tags(track_tags)
            precedent_fit = max((
                len(candidate_signals.intersection(cases_by_id[match["case_id"]].canonical_problem_tags))
                / len(candidate_signals)
                for match in normalized_case_matches
            ), default=0.0) if candidate_signals else 0.0
            matched_case_names = [
                match["case_name"] for match in normalized_case_matches
                if candidate_signals.intersection(cases_by_id[match["case_id"]].canonical_problem_tags)
            ]
        else:
            precedent_fit = max((
                len(track_tags.intersection(case.get("shared_mechanisms", []))) / len(track_tags)
                for case in legacy_cases
            ), default=0.0) if track_tags else 0.0
            matched_case_names = [
                case["case"] for case in legacy_cases
                if track_tags.intersection(case.get("shared_mechanisms", []))
            ]
        total_score = 0.85 * candidate["evidence_score"] + 0.15 * precedent_fit
        ranked_candidates.append({
            "candidate_id": f"{candidate['rule']}:{candidate['diagnosis_rank']}",
            "rule": candidate["rule"],
            "scope": candidate["scope"],
            "status": candidate["status"],
            "action_title": rule.get("pilot") or rule.get("diagnostic") or rule["label"],
            "diagnosis_rank": candidate["diagnosis_rank"],
            "score": round(total_score, 4),
            "score_breakdown": {
                "status_support": round(0.34 * candidate["evidence_score_breakdown"]["status_support"], 4),
                "evidence_slot_coverage": round(0.2125 * candidate["evidence_score_breakdown"]["evidence_slot_coverage"], 4),
                "direct_evidence": round(0.1275 * candidate["evidence_score_breakdown"]["direct_evidence"], 4),
                "reported_evidence": round(0.1275 * candidate["evidence_score_breakdown"]["reported_evidence"], 4),
                "scope_specificity": round(0.0425 * candidate["evidence_score_breakdown"]["scope_specificity"], 4),
                "historical_case_mechanism_fit": round(0.15 * precedent_fit, 4),
            },
            "matched_evidence_ids": candidate["matched_evidence_ids"],
            "matched_case_names": matched_case_names,
        })
    ranked_candidates.sort(key=lambda row: (-row["score"], row["diagnosis_rank"], row["candidate_id"]))
    for score_rank, candidate in enumerate(ranked_candidates, start=1):
        candidate["score_rank"] = score_rank

    return {
        "scenario_code": diagnosis_state["scenario_code"],
        "scoring_formula": {
            "status_support": 0.34,
            "evidence_slot_coverage": 0.2125,
            "direct_evidence": 0.1275,
            "reported_evidence": 0.1275,
            "scope_specificity": 0.0425,
            "historical_case_mechanism_fit": 0.15,
            "guardrail_minimum_score": 0.35,
        },
        "ranked_candidates": ranked_candidates,
        "matched_case_studies": recommendation_case_rows,
        "normalized_case_matches": normalized_case_matches,
        "case_informed_action_candidates": normalized_case_candidate_actions,
        "legacy_case_rankings": legacy_cases if not normalized_case_matches else [],
        "supporting_research_snippets": research,
        "ranked_track_tags": sorted(ranked_tags),
        "supporting_source_ids": sorted(source_ids),
    }


def score_cases_and_research(
    dataset, library, graph, intake, profile, analytics, ranked_tags, source_ids,
    phase_plan=None, include_legacy_cases=True,
):
    """Retrieve comparable precedents and source-linked research for active mechanisms."""
    retrieval_tags = set(ranked_tags)
    if phase_plan:
        for phase_name in ("phase_2_actions", "phase_3_actions"):
            for action in phase_plan.get(phase_name, []):
                rule_id = action.get("rule")
                if rule_id in graph["rules"]:
                    retrieval_tags.update(graph["rules"][rule_id].get("track_tags", []))
    cases = case_matches(
        dataset["raw_case_study_narratives"], retrieval_tags, profile, graph=graph,
        active=intake["snapshot"], case_analytics=analytics.get("cases", {}),
    ) if include_legacy_cases else []
    research = [
        {"source_id": key, **graph["sources"][key], "evidence_class": source_class(graph["sources"][key]["kind"])}
        for key in sorted(source_ids)
    ]
    sandbox_ids = {snippet for tag in retrieval_tags if tag in TRACKS for snippet in TRACKS[tag][4]}
    research.extend({
        "evidence_class": "organizer_reference", **entry,
        "limitation": "Supplied sandbox reference. Verify the magnitude and applicability independently.",
    } for entry in dataset["raw_empirical_research_snippets"] if entry["snippet_no"] in sandbox_ids)
    research.extend({**entry, "evidence_class": "published_reference"}
                    for entry in search_library(library, topics=retrieval_tags))
    return cases, research


# Provenance-checked evidence-library utilities are colocated with case/research scoring.
"""Load provenance-bearing evidence packs and rank entries by topic."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

BUILTIN_LIBRARY = Path(__file__).resolve().parents[2] / "database" / "knowledge" / "hr_evidence_library.json"
TEXT_FIELDS = ("id", "kind", "title", "url", "finding", "applicability")


def load_library(extra_packs=()):
    entries = {}
    for path in (BUILTIN_LIBRARY, *extra_packs):
        records = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(records, list):
            raise ValueError(f"{path}: expected a list of evidence records")
        for index, record in enumerate(records, start=1):
            location = f"{path}, record {index}"
            if not isinstance(record, dict) or any(
                not isinstance(record.get(key), str) or not record[key].strip()
                for key in TEXT_FIELDS
            ):
                raise ValueError(f"{location}: expected non-empty fields {', '.join(TEXT_FIELDS)}")
            url = urlsplit(record["url"])
            if url.scheme != "https" or not url.hostname:
                raise ValueError(f"{location}: expected an HTTPS source URL")
            topics = record.get("topics")
            if not isinstance(topics, list) or not topics or any(
                not isinstance(topic, str) or not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", topic)
                for topic in topics
            ):
                raise ValueError(f"{location}: expected non-empty snake_case topics")
            if record["id"] in entries:
                raise ValueError(f"{location}: duplicate evidence ID {record['id']}")
            entries[record["id"]] = record
    return list(entries.values())


def search_library(entries, topics=(), query="", limit=3):
    """Rank topic matches first, then matches in the title and finding."""
    query_words = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored = []
    for entry in entries:
        matched_topics = sorted(set(topics).intersection(entry["topics"]))
        topic_words = set(re.findall(r"[a-z0-9]+", " ".join(entry["topics"])))
        body_words = set(re.findall(r"[a-z0-9]+", f"{entry['title']} {entry['finding']}".lower()))
        score = 4 * len(matched_topics)
        score += 2 * len(query_words & topic_words) + len(query_words & body_words)
        if score:
            scored.append({**entry, "matched_topics": matched_topics, "score": score})
    return sorted(scored, key=lambda entry: (-entry["score"], entry["id"]))[:limit]
