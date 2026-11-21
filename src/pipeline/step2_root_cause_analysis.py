"""Step 2: deterministic diagnosis against the active knowledge graph.

The production entrypoint is ``run_root_cause_analysis(scenario, graph, analytics)``.
It normalizes scoped intake, evaluates graph rules, and returns profile, intake,
hypotheses, and ranked hypotheses. The active rule source is
``database/knowledge/hr_knowledge_graph.json``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from fnmatch import fnmatchcase
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

def profile_for(value):
    """Return general workforce/profile tags detected by the policy utility."""
    import re

    return {tag for tag, pattern in PROFILE.items() if re.search(pattern, value, re.I)}


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


def run_root_cause_analysis(scenario, graph, analytics):
    """Build profile and intake evidence, diagnose hypotheses, and prioritize them."""
    profile = profile_for(" ".join(str(scenario.get(key, "")) for key in (
        "industry", "workforce_target", "headcount_and_footprint", "organizational_context"
    )))
    profile_tags = scenario.get("profile_tags", [])
    if not isinstance(profile_tags, list) or any(not isinstance(tag, str) for tag in profile_tags):
        raise ValueError("profile_tags must be a list of strings")
    profile.update(profile_tags)
    intake = normalize_intake(scenario, graph, analytics)
    hypotheses = diagnose(graph, intake["observations"], profile)
    ranked_hypotheses = list(prioritized(hypotheses, {row["id"]: row for row in intake["observations"]}, graph))
    return profile, intake, hypotheses, ranked_hypotheses


# Shared policy patterns and deterministic intake/knowledge-graph helpers live in Step 2.
# General HR evidence patterns, intervention policies, and precedent annotations.

# Patterns apply to evidence fields, with separate rules for requests and strengths.
FEATURES = {
    "expectation_gap": r"""[1-9](?:\.\d+)?[- ]star gap|say[- ]do gap|promis\w*[^.;]{0,60}contradict""",
    "manager_support": r"micromanagement|without management coaching|weak middle management|uncoached leads",
    "career_clarity": r"unclear promotion|career path opacity|without[^.]{0,50}career progression framework",
    "burnout": r"workload burnout|systemic burnout|management burnout|severe burnout",
    "early_attrition": r"early (?:new.hire )?attrition|leave within their first|first.year turnover",
    "mobile_friction": r"desktop[- ](?:style|first|heavy) |cv upload|multi.page desktop|mobile.{0,30}abandonment",
    "generic_ads": r"generic (?:corporate|job|hq)|corporate boilerplate",
    "local_reputation": r"rating variance|unmonitored centrally|outdated or unaddressed local profiles",
    "review_tracking": r"reviews?[^.;]{0,65}(?:manually|spreadsheet)|manually[^.;]{0,50}(?:facility|hub) reviews",
    "post_tracking": r"manually[^.;]{0,110}(?:post|sharing|ambassador)|ambassador screenshots|post screenshots",
    "feedback_fragmentation": r"(?:post.interview|career day)[^.;]{0,150}(?:disconnected|fragmented|paper sheets|ad.hoc forms)",
    "existing_advocates": r"(?:already share|organic ambassadors are already active|active organic ambassadors)",
    "culture_ready": r"employee sentiment is highly positive|employee satisfaction[^.;]{0,100}(?:strong|healthy)|high evp authenticity",
    "emv": r"earned media value|\bemv\b",
    "agency_spend": r"temporary staffing agencies|agency spend",
}

PROFILE = {
    "tech": r"software|engineer|cloud|fintech|saas",
    "freight": r"truck driver|commercial driver|warehouse|freight|interport|logistics|fulfilment",
    "care": r"clinical|healthcare|nurses|care facilit",
    "retail": r"retail|store staff|in-store|store manager",
    "early_career": r"gen.z|early.career|graduate",
    "distributed": r"multi.site|across \d+|regional|multi.country|distributed",
    "fintech": r"fintech|digital payments|cloud payments",
    "sustainability": r"b[- ]corp|esg|sustainab",
}

# Source labels identify historical records only. Tags describe transferable mechanisms.
CASE_TAGS = {
    "LogiNext": "expectation_gap review_tracking local_reputation early_attrition",
    "Solaris Tech": "culture_ready existing_advocates post_tracking emv",
    "FlowPay": "generic_ads post_tracking",
    "Global Retail Group": "mobile_friction generic_ads",
    "Alfa Group": "expectation_gap manager_support career_clarity burnout early_attrition",
    "Beta Logistica": "mobile_friction generic_ads agency_spend local_reputation",
    "Gamma Retail": "mobile_friction burnout manager_support early_attrition",
    "VitaCare Network": "local_reputation review_tracking post_tracking existing_advocates",
    "Aurea Banca Group": "feedback_fragmentation existing_advocates emv post_tracking",
    "BellaModa Retail": "mobile_friction burnout",
    "NaturaPure Group": "culture_ready feedback_fragmentation existing_advocates post_tracking emv",
}

# A rule supplies diagnosis, diagnostic work, a structural pilot, a rollout gate,
# and research references. Independent tracks can proceed in parallel.
TRACKS = {
    "expectation_gap": (
        "Recruiting promises appear to exceed day-to-day autonomy or growth. Expectation drift can drive early exits, poor reviews and weaker recruiting.",
        "Compare recruiting claims with interviews, new-hire exit reasons and reviews by affected cohort. Ask which decisions new hires can actually own.",
        "Rewrite unverified promises with team leads and publish a realistic preview of decision rights and progression.",
        "Publish new recruiting stories only after recent hires confirm that the claims match their experience.",
        (1, 5),
    ),
    "manager_support": (
        "Management support is a likely contributor to early attrition where leads lack coaching or employees report micromanagement.",
        "Run confidential 360-degree listening and compare early exits by team, manager and tenure.",
        "Pilot manager coaching and explicit delegation agreements in the affected teams. Review progress with new hires after 30 and 60 days.",
        "Extend coaching only where the pilot improves delegation feedback and early-tenure retention indicators.",
        (4,),
    ),
    "career_clarity": (
        "Unclear promotion criteria weaken the growth promise and may contribute to avoidable exits.",
        "Audit promotion decisions and interview recent hires about how they learned what advancement requires.",
        "Pilot role levels, promotion examples and a monthly career conversation with affected teams.",
        None,
        (4,),
    ),
    "burnout": (
        "Reported workload burnout suggests unsustainable capacity and is a risk to retention and advocacy readiness.",
        "Compare workload, overtime and exits by cohort. Reconcile the itemized turnover estimates with the reported total before presenting savings.",
        "Pilot workload limits and escalation for capacity shortfalls. Review workload and pulse feedback before expanding.",
        None,
        (4, 5),
    ),
    "mobile_friction": (
        "A desktop-oriented application flow creates friction for phone applicants and may prolong frontline vacancies.",
        "Instrument device-level funnel steps and test the current application on a phone with target candidates. Baseline qualified completion and time-to-hire.",
        "Pilot a short mobile application that puts eligibility first and defers account creation and CV upload where feasible. Route qualified candidates to a callback queue.",
        "Expand the pilot when qualified completion improves without lower eligibility or slower callbacks. Track time-to-hire and agency spend where available.",
        (2,),
    ),
    "generic_ads": (
        "Generic job ads hide the information the target workforce needs to decide whether to apply.",
        "Interview candidates and recruiters to verify which job details drive decisions for the target workforce.",
        "Test workforce-specific job ads using verified operational strengths and a clear preview of the role.",
        "Expand the ads after measuring qualified applications by role and channel.",
        (),
    ),
    "local_reputation": (
        "Local reputation and candidate experience vary by site, so company-wide averages can hide local problems.",
        "Audit review profiles and candidate handoffs by site. Break out stale profiles, recurring complaints and response times.",
        "Assign a local owner for profile accuracy and candidate handoffs. Pilot a response queue at the lowest-performing sites.",
        "Expand local ownership after profile coverage and handoff times improve at pilot sites.",
        (),
    ),
    "review_tracking": (
        "Manual review collection fragments site-level evidence and consumes HR reporting capacity.",
        "Inventory review sources, collection hours and site ownership. Establish a baseline for coverage and manual effort.",
        "Centralize review intake by site with source timestamps and an exception queue. Track hours saved against the baseline.",
        None,
        (8,),
    ),
    "feedback_fragmentation": (
        "Disconnected feedback collection obscures candidate drop-off and makes experience reporting difficult to audit.",
        "Map feedback collection from events and interviews through local handoffs. Compare response rates and delays by location and role.",
        "Pilot one timestamped feedback form and a follow-up owner. Use consistent questions, consent and aggregate reporting for small cohorts.",
        "Scale once response rates, handoff times and audit completeness improve.",
        (9,),
    ),
    "post_tracking": (
        "Manual post tracking limits visibility into employee-led reach and consumes HR capacity.",
        "Baseline reporting hours and define verified reach, consent and how paid-media equivalents will be calculated.",
        "Prepare reporting instrumentation with duplicate checks, documented rates and source records for CFO review.",
        None,
        (3, 8),
    ),
}


DEFAULT_GRAPH = Path(__file__).resolve().parents[2] / "database" / "knowledge" / "hr_knowledge_graph.json"
KINDS = ("signals", "sources", "rules")
SCOPE_FIELDS = ("cohort", "site", "tenure", "window")
STATES = {"present", "absent", "unknown"}
QUALITIES = {"verified", "reported", "unverified"}
ACTION_FIELDS = ("diagnostic", "pilot", "scale_gate")
ACTION_TAGS = {
    "external_advocacy", "schedule_change", "retail_schedule", "technical_linkedin", "compensation", "form_redesign",
}


def _string(value):
    return isinstance(value, str) and bool(value.strip())


def _strings(value):
    return isinstance(value, list) and all(_string(item) for item in value)


def load_graph(extra_packs=()):
    graph = {kind: {} for kind in KINDS}
    for path in (DEFAULT_GRAPH, *extra_packs):
        pack = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(pack, dict) or set(pack) - {"version", *KINDS}:
            raise ValueError(f"{path}: expected a graph pack with signals, sources and rules")
        if type(pack.get("version")) is not int or pack["version"] != 1:
            raise ValueError(f"{path}: unsupported graph pack version")
        for kind in KINDS:
            records = pack.get(kind, {})
            if not isinstance(records, dict):
                raise ValueError(f"{path}: {kind} must be an object keyed by ID")
            for key, record in records.items():
                if not _string(key) or not isinstance(record, dict) or key in graph[kind]:
                    raise ValueError(f"{path}: invalid or duplicate {kind} ID {key!r}")
                graph[kind][key] = record

    for key, signal in graph["signals"].items():
        if not all(_string(signal.get(field)) for field in ("family", "role", "meaning")):
            raise ValueError(f"Signal {key}: expected family, role and meaning")
        if signal["role"] not in {"context", "indicator", "outcome", "direct"}:
            raise ValueError(f"Signal {key}: unsupported role")
        if not _strings(signal.get("metrics", [])):
            raise ValueError(f"Signal {key}: metrics must be a list of metric paths")
        if "intake_pattern" in signal:
            try:
                re.compile(signal["intake_pattern"])
            except (re.error, TypeError) as exc:
                raise ValueError(f"Signal {key}: invalid intake pattern") from exc
    for key, source in graph["sources"].items():
        if not all(_string(source.get(field)) for field in ("kind", "url", "finding", "limitation")):
            raise ValueError(f"Source {key}: expected kind, HTTPS URL, finding and limitation")
        url = urlsplit(source["url"])
        if url.scheme != "https" or not url.hostname:
            raise ValueError(f"Source {key}: expected an HTTPS URL")
    for key, rule in graph["rules"].items():
        _validate_rule(key, rule, graph)
    return graph


def _validate_rule(key, rule, graph):
    for field in ("label", *ACTION_FIELDS):
        if not _string(rule.get(field)):
            raise ValueError(f"Rule {key}: missing {field}")
    if not _string(rule.get("kind")) or rule["kind"] not in {"mechanism", "operational", "policy"}:
        raise ValueError(f"Rule {key}: unknown kind")
    needs = rule.get("requires")
    if not isinstance(needs, list) or len(needs) < 2:
        raise ValueError(f"Rule {key}: requires at least two evidence families")
    signals = graph["signals"]
    families = set()
    for group in needs:
        if not _strings(group) or not group or set(group) - signals.keys():
            raise ValueError(f"Rule {key}: unknown or invalid required signal")
        group_families = {signals[signal]["family"] for signal in group}
        if len(group_families) != 1 or group_families & families:
            raise ValueError(f"Rule {key}: alternatives must share a family and each family is used once")
        families |= group_families
    direct = rule.get("direct")
    if type(direct) is not int or not 0 <= direct < len(needs):
        raise ValueError(f"Rule {key}: direct must index a required evidence slot")
    if not any(signals[signal]["role"] == "direct" for signal in needs[direct]):
        raise ValueError(f"Rule {key}: direct slot must contain a direct observation")
    for field, known in (("counter", signals), ("alternatives", graph["rules"]), ("sources", graph["sources"])):
        values = rule.get(field, [])
        if not _strings(values) or set(values) - known.keys() or (field == "alternatives" and key in values):
            raise ValueError(f"Rule {key}: invalid {field} references")
    if not _strings(rule.get("track_tags", [])) or not _strings(rule.get("profile_any", [])):
        raise ValueError(f"Rule {key}: invalid track tags or profile filter")
    if type(rule.get("counter_overlap", False)) is not bool:
        raise ValueError(f"Rule {key}: counter_overlap must be boolean")
    if type(rule.get("requires_verified_pilot", False)) is not bool:
        raise ValueError(f"Rule {key}: requires_verified_pilot must be boolean")
    tags = rule.get("action_tags", [])
    if not _strings(tags) or set(tags) - ACTION_TAGS:
        raise ValueError(f"Rule {key}: invalid action tags")


def observation_batches(raw, graph):
    """Group by exact cohort, site, tenure and observation window."""
    if not isinstance(raw, list):
        raise ValueError("diagnostic_observations must be a list")
    ids = set()
    batches = defaultdict(list)
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("Expected observation objects")
        key = row.get("id")
        signal = row.get("signal")
        if not _string(key) or key in ids or not _string(signal) or signal not in graph["signals"]:
            raise ValueError(f"Invalid observation ID or signal: {key!r}, {signal!r}")
        ids.add(key)
        if not _string(row.get("state")) or row["state"] not in STATES or (
            not _string(row.get("quality")) or row["quality"] not in QUALITIES
        ):
            raise ValueError(f"Observation {key}: invalid state or quality")
        if not _string(row.get("source_ref")) or not _strings(row.get("origins")) or not row["origins"]:
            raise ValueError(f"Observation {key}: expected a source reference and at least one origin")
        for field in ("population_ids", "dependency_ids"):
            if not _strings(row.get(field, [])):
                raise ValueError(f"Observation {key}: {field} must be a list of IDs")
        metric = row.get("metric_path")
        if metric is not None and (
            not _string(metric) or not any(
                fnmatchcase(metric, pattern) for pattern in graph["signals"][signal].get("metrics", [])
            )
        ):
            raise ValueError(f"Observation {key}: metric_path is not linked to signal {signal}")
        scope = row.get("scope", {})
        if not isinstance(scope, dict) or scope.keys() - set(SCOPE_FIELDS):
            raise ValueError(f"Observation {key}: invalid scope fields")
        if any(value is not None and not _string(value) for value in scope.values()):
            raise ValueError(f"Observation {key}: scope values must be strings or null")
        coordinate = tuple(scope.get(field) for field in SCOPE_FIELDS)
        batches[coordinate].append(row)
    return batches


def _origin_components(observations):
    """Overlapping lineage is treated as dependent, including indirect overlap."""
    lineage = {
        row["id"]: [f"origin:{key}" for key in row["origins"]]
        + [f"reference:{row['source_ref']}"]
        + [f"population:{key}" for key in row.get("population_ids", [])]
        + [f"dependency:{key}" for key in row.get("dependency_ids", [])]
        for row in observations
    }
    parent = {origin: origin for keys in lineage.values() for origin in keys}

    def root(origin):
        while parent[origin] != origin:
            parent[origin] = parent[parent[origin]]
            origin = parent[origin]
        return origin

    for keys in lineage.values():
        first = root(keys[0])
        for origin in keys[1:]:
            parent[root(origin)] = first
    return {key: root(tokens[0]) for key, tokens in lineage.items()}


def _overlap(left, right):
    for index, (a, b) in enumerate(zip(left, right)):
        wildcard = {None, "intake"} if SCOPE_FIELDS[index] == "window" else {None, "all"}
        if a == b or a in wildcard or b in wildcard:
            continue
        if SCOPE_FIELDS[index] != "window" and set(a.split("+")).intersection(b.split("+")):
            continue
        if SCOPE_FIELDS[index] == "window" and all("/" in value for value in (a, b)):
            a_start, a_end = a.split("/", 1)
            b_start, b_end = b.split("/", 1)
            if a_start <= b_end and b_start <= a_end:
                continue
        return False
    return True


def scope_overlaps(left, right):
    """Check whether any individuals and period could be shared."""
    return _overlap(tuple(left.get(field) for field in SCOPE_FIELDS),
                    tuple(right.get(field) for field in SCOPE_FIELDS))


def _match_slots(candidates, components):
    """Find a maximum matching of required slots to independent origins."""
    owners = {}

    def assign(slot, seen):
        for row in candidates[slot]:
            component = components[row["id"]]
            if component in seen:
                continue
            seen.add(component)
            previous = owners.get(component)
            if previous is None or assign(previous[0], seen):
                owners[component] = (slot, row)
                return True
        return False

    for slot in sorted(range(len(candidates)), key=lambda index: len(candidates[index])):
        assign(slot, set())
    return dict(owners.values())


def _evaluate(rule, rows, coordinate, graph, overlapping_counters=()):
    trustworthy = [row for row in rows if row["quality"] != "unverified" and row["state"] != "unknown"]
    tagged = defaultdict(list)
    for row in trustworthy:
        tagged[row["signal"]].append(row)
    needs = rule["requires"]
    direct = rule["direct"]
    positive = [
        sorted(
            (row for signal in options for row in tagged[signal] if row["state"] == "present"),
            key=lambda row: (row["quality"] != "verified", row["id"]),
        )
        for options in needs
    ]
    relevant = [row for slot in positive for row in slot]
    if not any(graph["signals"][row["signal"]]["role"] != "context" for row in relevant):
        return None

    components = _origin_components(trustworthy)
    matched = _match_slots(positive, components)
    verified = positive.copy()
    verified[direct] = [
        row for row in positive[direct]
        if row["quality"] == "verified" and graph["signals"][row["signal"]]["role"] == "direct"
    ]
    verified_match = _match_slots(verified, components)
    counters = [
        row for signal in rule.get("counter", [])
        for row in tagged[signal] if row["state"] == "present"
    ]
    counters.extend(overlapping_counters)
    for index, options in enumerate(needs):
        has_positive = {row["signal"] for row in positive[index]}
        absent = [row for signal in options for row in tagged[signal] if row["state"] == "absent"]
        if not has_positive and {row["signal"] for row in absent} == set(options):
            counters.extend(absent)
        else:
            counters.extend(row for row in absent if row["signal"] in has_positive)

    blockers = []
    if not all(coordinate):
        blockers.append("unresolved_scope_or_window")
    if len(matched) != len(needs):
        blockers.append("missing_or_dependent_evidence")
    if not verified[direct] or (len(matched) == len(needs) and len(verified_match) != len(needs)):
        blockers.append("verified_direct_evidence_required")
    if counters:
        status = "conflicted"
        blockers.append("counterevidence_present")
    elif not blockers:
        status = "supported"
        matched = verified_match
    else:
        status = "plausible"
    selected = sorted(row["id"] for row in matched.values())
    overlap = sorted({row["id"] for row in relevant} - set(selected))
    return {
        "status": status,
        "scope": dict(zip(SCOPE_FIELDS, coordinate)),
        "evidence_ids": selected,
        "other_matching_ids": overlap,
        "origin_components": {row["id"]: components[row["id"]] for row in relevant},
        "counterevidence_ids": sorted({row["id"] for row in counters}),
        "unmatched_families": [
            graph["signals"][options[0]]["family"] for index, options in enumerate(needs)
            if index not in matched
        ],
        "missing_families": [
            graph["signals"][options[0]]["family"] for index, options in enumerate(needs)
            if not positive[index]
        ],
        "dependent_families": [
            graph["signals"][options[0]]["family"] for index, options in enumerate(needs)
            if positive[index] and index not in matched
        ],
        "evidence_slots": [
            {
                "family": graph["signals"][options[0]]["family"],
                "expected_signals": options,
                "matching_ids": [row["id"] for row in positive[index]],
                "selected_id": matched[index]["id"] if index in matched else None,
                "direct_slot": index == direct,
            }
            for index, options in enumerate(needs)
        ],
        "limitations": blockers,
    }


def diagnose(graph, observations, profile=()):
    batches = observation_batches(observations, graph)
    hypotheses = []
    profile = set(profile)
    rules_by_signal = defaultdict(set)
    for key, rule in graph["rules"].items():
        if rule.get("profile_any") and not profile.intersection(rule["profile_any"]):
            continue
        for slot in rule["requires"]:
            for signal in slot:
                if graph["signals"][signal]["role"] != "context":
                    rules_by_signal[signal].add(key)
    for coordinate, rows in batches.items():
        candidates = {
            key
            for row in rows if row["state"] == "present" and row["quality"] != "unverified"
            for key in rules_by_signal[row["signal"]]
        }
        for key in sorted(candidates):
            rule = graph["rules"][key]
            overlapping_counters = [
                row for scope, other_rows in batches.items()
                if scope != coordinate and _overlap(scope, coordinate)
                for row in other_rows
                if row["signal"] in rule.get("counter", [])
                and row["quality"] != "unverified" and row["state"] == "present"
            ] if rule.get("counter_overlap") else ()
            result = _evaluate(rule, rows, coordinate, graph, overlapping_counters)
            if result:
                hypotheses.append({
                    "rule": key,
                    "label": rule["label"],
                    "kind": rule["kind"],
                    **result,
                    "alternatives": rule.get("alternatives", []),
                    "sources": rule.get("sources", []),
                    "next_check": rule["diagnostic"],
                })
    status_order = {"supported": 0, "plausible": 1, "conflicted": 2}
    lookup = {(row["rule"], tuple(row["scope"].values())): row["status"] for row in hypotheses}
    for row in hypotheses:
        scope = tuple(row["scope"].values())
        row["competing_hypotheses"] = [
            {"rule": key, "same_scope_status": lookup.get((key, scope), "insufficient_evidence")}
            for key in row["alternatives"]
        ]
    return sorted(hypotheses, key=lambda row: (status_order[row["status"]], row["rule"], str(row["scope"])))


def graph_export(graph):
    """Emit typed nodes and edges for diagramming or graph-database import."""
    nodes = []
    edges = []
    for kind in KINDS:
        for key, record in graph[kind].items():
            nodes.append({**record, "id": f"{kind}:{key}", "type": kind})
    for key, signal in graph["signals"].items():
        for metric in signal.get("metrics", []):
            edges.append({"from": f"metrics:{metric}", "to": f"signals:{key}", "type": "can_inform"})
    for metric_id in sorted({edge["from"] for edge in edges}):
        nodes.append({"id": metric_id, "type": "metrics"})
    for key, rule in graph["rules"].items():
        for index, group in enumerate(rule["requires"]):
            for signal in group:
                edges.append({
                    "from": f"signals:{signal}", "to": f"rules:{key}", "type": "requires",
                    "slot": index, "direct_slot": index == rule["direct"],
                })
        for field, kind, relation in (
            ("counter", "signals", "challenges"), ("sources", "sources", "grounds"),
            ("alternatives", "rules", "alternative_to"),
        ):
            for target in rule.get(field, []):
                edges.append({"from": f"{kind}:{target}", "to": f"rules:{key}", "type": relation})
    return {"version": 1, "nodes": nodes, "edges": edges}


DEFAULT_ANALYTICS = Path(__file__).resolve().parents[2] / "database" / "ingaze_synthetic_analytics_snapshots.json"
REQUEST_FIELD = "leadership_perceptions_and_requests"
STRENGTH_FIELD = "healthy_metrics_and_strengths_not_to_break"
NOISE = re.compile(r"unverified|external merchant POS pilot|raw CSV review feed|unrelated export", re.I)
NEGATION = re.compile(r"\b(?:no|zero|not|without|resolved)\s+(?:[\w-]+\s+){0,4}$", re.I)
CLAUSE = re.compile(r"(?<=[!?;])\s+|(?<=\.)\s+(?=[A-Z])")
QUANTITY = re.compile(
    r"(?P<bound><=|>=|<|>)?\s*(?P<currency>€)?(?P<number>\d[\d,]*(?:\.\d+)?)"
    r"\s*(?P<unit>%|/5\b|/100\b|stars?\b|days?\b|hours?\b(?:/(?:week|month|year))?|"
    r"months?\b|years?\b|employees?\b|locations?\b|clinics?\b|percentile\b|[kM]\b)?",
    re.I,
)
PEER_CHANNELS = {"portal_funnel": "career_portal_and_funnel",
                 "social_and_advocacy": "social_and_employee_voice",
                 "hiring_and_retention": "hiring_and_retention_kpis"}
REVIEW_COHORTS = re.compile(r"regional (?:clinics|senior care centers)|formulation labs|"
                            r"(?:core (?:platform|infrastructure)|product) (?:squads|hubs)|hq", re.I)
SIGNAL_PATTERNS = {
    "documented_broken_promise": r"gap between external recruiting claims.{0,180}(?:reviews citing|micromanagement)|promis\w*.{0,100}contradict",
    "form_obstacle_verified": r"desktop.style account registration|requires.{0,55}(?:cv upload|account creation)|upload (?:fails|failure)",
    "handoff_delay_reported": r"slow (?:candidate response|local[^.;]{0,45}interview handoffs)|interview handoff delays",
    "role_info_gap_verified": r"(?:job descriptions|job ads).{0,100}(?:omit|zero mention|fail to mention)",
    "feedback_workflow_verified": r"disconnected (?:paper sheets|forms)|ad.hoc forms|fragmented (?:feedback|survey collection)",
    "tracking_workflow_verified": r"manually (?:exporting|copying|collecting)|manual spreadsheet tracking|chasing post screenshots",
    "local_issue_verified": r"unmonitored centrally|outdated or unaddressed local profiles",
    "expectations_met": r"recruiting promises (?:are )?(?:being )?met|job matched (?:the|their) preview",
    "adequate_workload": r"workload (?:is |was )?(?:within capacity|sustainable)",
    "form_completes": r"(?:form|application).{0,45}(?:completion is high|works well|no unusual loss)",
    "mobile_friction": FEATURES["mobile_friction"] + r"|mobile application drop[- ]off",
}

# These small margins prioritize discovery. They are operational heuristics, never causal cutoffs.
PEER_SIGNALS = {
    "expectation_gap": (1, .15), "brand_misalignment": (-1, 5),
    "manager_support": (-1, .25), "career_clarity": (-1, .25),
    "early_attrition": (1, 2), "application_abandonment": (1, 3),
    "application_loss": (-1, .5), "hiring_delay": (1, 3), "agency_spend": (1, 3),
    "generic_ads": (-1, 5), "local_reputation": (1, .15), "low_survey_coverage": (-1, 3),
    "employer_reputation_weak": (-1, .25), "corporate_engagement_weak": (-1, .4),
    "culture_ready": (1, .3),
}

# Optional fields for scoped extensions. The official companion snapshot does
# not contain these stage-specific measurements.
EXTENDED_METRIC_SHAPES = {
    "qualified_applicants_per_requisition": ("count_per_requisition", "approved_requisitions", None),
    "request_to_requisition_approval_days": ("days", "resolved_hiring_requests", None),
    "request_to_fill_days": ("days", "target_roles_filled", None),
    "screen_to_interview_days": ("days", "interviewed_eligible_candidates", None),
    "offer_decline_pct": ("%", "extended_offers", None),
    "qualified_screen_rejection_pct": ("%", "qualified_applicants_reviewed", None),
    "accepted_offer_nonstart_pct": ("%", "accepted_offers_due_to_start", None),
    "voluntary_attrition_pct": ("%", "at_risk_employees", None),
}


def load_analytics(path=DEFAULT_ANALYTICS):
    if path is None:
        return {"active": {}, "cases": {}}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    result = {}
    for name, key, collection in (
        ("active", "scenario_code", "active_scenario_analytics_snapshots"),
        ("cases", "case_name", "case_study_analytics_snapshots"),
    ):
        index = {}
        for row in payload[collection]:
            identity = row[key]
            if identity in index:
                raise ValueError(f"Duplicate analytics identity: {identity}")
            index[identity] = row
        result[name] = index
    return result


def flatten_metrics(node, prefix=""):
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from flatten_metrics(value, path)
        else:
            yield path, value


def align_peers(snapshot):
    aligned = {}
    for key, value in snapshot.get("sector_peer_benchmarks", {}).items():
        if key in PEER_CHANNELS:
            aligned.update(flatten_metrics(value, PEER_CHANNELS[key]))
        elif isinstance(value, dict):
            aligned.update(flatten_metrics({key: value}, "public_reputation"))
        else:
            aligned[f"public_reputation.{key}"] = value
    return aligned


def metric_shape(path):
    """Keep source units and denominator definitions intact."""
    leaf = path.rsplit(".", 1)[-1]
    if leaf in EXTENDED_METRIC_SHAPES:
        return EXTENDED_METRIC_SHAPES[leaf]
    if "six_month" in leaf:
        return "%", "new_hires", "6_months"
    if leaf == "early_first_year_attrition_pct":
        return "%", "new_hires", "12_months"
    if leaf.endswith("annual_retention_pct"):
        return "%", "starting_cohort", "12_months"
    if leaf == "application_form_dropoff_pct":
        return "%", "application_starts", None
    if leaf == "applicant_conversion_rate_pct":
        return "%", "portal_visits", None
    if leaf == "smartphone_traffic_pct":
        return "%", "portal_visits", None
    if leaf == "candidate_survey_completion_rate_pct":
        return "%", "eligible_candidates", None
    if leaf.endswith("_pct") or "er_by_post_format_pct." in path:
        return "%", None, None
    if leaf.endswith("_5") or ".sub_ratings_5." in path:
        return "stars", None, None
    if leaf.endswith("_100"):
        return "percentile" if "percentile" in leaf else "index_100", None, None
    if leaf.endswith("_days"):
        return "days", "target_roles_filled", None
    if leaf.endswith("_eur"):
        return "EUR/year", None, "12_months"
    if leaf.endswith("_hours_month"):
        return "hours/month", None, "1_month"
    period = "1_month" if "monthly" in leaf else "3_months" if "quarter" in leaf else None
    return "count", None, period


def _number(value, unit, path=""):
    if type(value) not in (int, float) or not math.isfinite(value):
        return False
    if unit in {"%", "index_100", "percentile"}:
        return 0 <= value <= 100
    if unit == "stars":
        if path.endswith("external_claims_gap_stars_5"):
            return 0 <= value <= 4
        if path.endswith("cross_location_rating_std_dev_5"):
            return 0 <= value <= 2
        return 1 <= value <= 5
    return value >= 0


def _word_scope(scenario, clause):
    footprint = str(scenario.get("headcount_and_footprint", ""))
    locations = [
        city.strip() for group in re.findall(r"\(([^()]*)\)", footprint)
        for city in group.split(",") if city.strip().isalpha()
    ]
    sites = sorted({city.casefold() for city in locations if re.search(rf"\b{re.escape(city)}\b", clause, re.I)})
    group = REVIEW_COHORTS.search(clause)
    cohort = None
    if re.search(r"frontline|truck drivers?|C-CQC|warehouse operators?", clause, re.I):
        cohort = "frontline_workforce"
    elif re.search(r"engineers?|product squads", clause, re.I):
        cohort = "engineering_workforce"
    elif re.search(r"regional (?:clinics|senior care centers)|nurses|therapists", clause, re.I):
        cohort = "regional_clinical_workforce"
    elif re.search(r"\bHQ\b", clause):
        cohort = "hq"
    career_stage = re.search(r"newly hired|new.hire|early.career|tenured|candidates?|applicants?", clause, re.I)
    tenure = ({"candidate": "applicant", "applicant": "applicant", "tenured": "tenured"}.get(
        career_stage[0].lower().rstrip("s"), "new_or_early_tenure") if career_stage else None)
    site = "+".join(sites) if sites else group[0].casefold() if group else None
    if re.search(r"\b(?:vs\.?|whereas|compared with)\b", clause, re.I) or (
        site == "hq" and cohort != "hq"
    ):
        site = None
    return {
        "cohort": cohort, "site": site,
        "tenure": tenure, "window": "intake",
    }


def _polarity(pattern, clause):
    found = []
    for hit in re.finditer(pattern, clause, re.I):
        prefix = re.split(r"[.;!?,]", clause[:hit.start()])[-1]
        negated = NEGATION.search(prefix) or re.search(r"\b(?:no|zero)\b.{0,45}\bor\s+(?:systemic|severe|management)?\s*$", prefix, re.I)
        found.append("absent" if negated else "present")
    return sorted(set(found))


def _quantities(clause):
    values = []
    for hit in QUANTITY.finditer(clause):
        currency, unit = hit["currency"], hit["unit"]
        if not currency and not unit:
            continue
        magnitude = float(hit["number"].replace(",", ""))
        if currency:
            magnitude *= {"k": 1000, "m": 1000000}.get((unit or "").lower(), 1)
            unit = "EUR"
        values.append({"value": magnitude, "unit": unit, "bound": hit["bound"], "text": hit[0].strip()})
    return values


def normalize_narrative(scenario, graph):
    patterns = {**FEATURES, **SIGNAL_PATTERNS}
    patterns.update({key: row["intake_pattern"] for key, row in graph["signals"].items() if "intake_pattern" in row})
    rows, excluded = [], []
    for section in ("ingaze_platform_signals", "client_internal_context"):
        for field, value in scenario.get(section, {}).items():
            if field == REQUEST_FIELD or not isinstance(value, str):
                continue
            for index, clause in enumerate(CLAUSE.split(value), start=1):
                source = f"{section}.{field}#{index}"
                if NOISE.search(clause):
                    excluded.append({"source": source, "text": clause})
                    continue
                scope = _word_scope(scenario, clause)
                for signal, pattern in patterns.items():
                    if signal not in graph["signals"]:
                        continue
                    for state in _polarity(pattern, clause):
                        if field == STRENGTH_FIELD and state == "present" and signal not in {
                            "culture_ready", "existing_advocates", "expectations_met", "adequate_workload",
                        }:
                            continue
                        signal_channels = {
                            path.split(".")[0] for path in graph["signals"][signal].get("metrics", [])
                        }
                        rows.append({
                            "id": f"text:{source}:{signal}:{state}", "signal": signal, "state": state,
                            "quality": "reported", "source_ref": source,
                            "origins": ["narrative_unresolved_lineage",
                                        *(f"telemetry:{channel}" for channel in sorted(signal_channels))],
                            "scope": scope,
                            "evidence_type": "reported_observation", "text": clause,
                            "quantities": _quantities(clause),
                        })
    return rows, excluded


def _metric_scope(path):
    scope = {"cohort": "all", "site": "all", "tenure": "all", "window": "intake"}
    if ".segment_or_site_breakdown." in path:
        scope["site"] = path.split(".")[-2].lower()
        scope["cohort"] = None
    if "six_month" in path or "first_year" in path:
        scope["tenure"] = "new_hire"
    leaf = path.rsplit(".", 1)[-1]
    scoped_exit = re.fullmatch(r"six_month_new_hire_attrition_(.+)_pct", leaf)
    retention = re.fullmatch(r"(.+)_annual_retention_pct", leaf)
    if scoped_exit:
        scope["cohort"] = None
        scope["site"] = "+".join(sorted(scoped_exit[1].split("_")))
    elif retention:
        scope["cohort"] = retention[1]
        scope["tenure"] = "tenured" if retention[1].startswith("tenured_") else None
        scope["site"] = None
    elif leaf == "hq_admin_time_to_hire_days":
        scope["cohort"] = "hq_admin"
        scope["site"] = None
    return scope


def normalize_metrics(snapshot, graph, namespace):
    baseline = snapshot.get("t0_current_snapshot", snapshot.get("t0_before_intervention", {}))
    peers = align_peers(snapshot)
    observations, measurements, excluded = [], [], []
    # One channel is treated as a shared source unless records carry explicit lineage.
    signal_index = [(pattern, key) for key, signal in graph["signals"].items() for pattern in signal.get("metrics", [])]
    for path, value in flatten_metrics(baseline):
        unit, denominator, horizon = metric_shape(path)
        source = f"telemetry:{namespace}.{path}"
        if not _number(value, unit, path):
            excluded.append({"source": source, "value": value, "reason": "invalid_unit_range"})
            continue
        peer = peers.get(path)
        peer = peer if _number(peer, unit, path) else None
        scope = _metric_scope(path)
        measurement = {
            "metric_path": path, "value": value, "unit": unit, "denominator": denominator,
            "measurement_horizon": horizon, "scope": scope, "source_ref": source,
            "peer_value": peer, "peer_group": snapshot.get("sector_benchmark_group"),
            "origins": [f"telemetry:{path.split('.')[0]}"],
        }
        measurements.append(measurement)
        signals = {key for pattern, key in signal_index if fnmatchcase(path, pattern)}
        for signal in sorted(signals):
            # Significant is a product heuristic here. No p-values or causal estimates are implied.
            state = "unknown"
            if signal in PEER_SIGNALS and peer is not None:
                direction, margin = PEER_SIGNALS[signal]
                gap = direction * (value - peer)
                state = "present" if gap >= margin else "absent" if gap <= -margin else "unknown"
            elif signal == "mobile_exposure" and path.endswith("smartphone_traffic_pct"):
                state = "present" if value > 50 else "absent"
            elif signal == "manual_tracking_load" and value > 0:
                state = "present"
            elif signal == "existing_advocates" and path.endswith("active_organic_ambassadors_headcount"):
                state = "present" if value > 0 else "absent"
            observations.append({
                "id": f"metric:{signal}:{path}", "signal": signal, "state": state, "quality": "reported",
                "evidence_type": "synthetic_observation",
                **measurement,
            })
    return observations, measurements, excluded


def normalize_reviewed(row):
    if not isinstance(row, dict):
        raise ValueError("Expected structured observation objects")
    result = dict(row)
    path = row.get("metric_path")
    if path is not None and not isinstance(path, str):
        raise ValueError("metric_path must be a string")
    if "value" in row:
        unit, denominator, horizon = metric_shape(path) if path else (row.get("unit"), None, None)
        value = row["value"]
        supplied = row.get("unit", unit)
        if supplied == "fraction" and unit == "%" and type(value) in (int, float):
            value = value * 100
            supplied = "%"
        if not isinstance(unit, str) or supplied != unit or not _number(value, unit, path or ""):
            raise ValueError(f"Observation {row.get('id')}: invalid value or unit")
        result.update(value=value, unit=unit)
        result.setdefault("denominator", denominator)
        result.setdefault("measurement_horizon", horizon)
    if "period_start" in row or "period_end" in row:
        try:
            start = date.fromisoformat(row["period_start"])
            end = date.fromisoformat(row["period_end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("period_start and period_end must both be ISO dates") from exc
        if end < start:
            raise ValueError("period_end precedes period_start")
        if isinstance(row.get("scope", {}), dict):
            result["scope"] = {**row.get("scope", {}), "window": f"{start}/{end}"}
    result["evidence_type"] = "reviewed_local_observation"
    return result


def normalize_intake(scenario, graph, analytics):
    narrative, excluded = normalize_narrative(scenario, graph)
    snapshot = scenario.get("analytics") if "analytics" in scenario else analytics.get("active", {}).get(scenario["scenario_code"])
    metric_rows, measurements, issues = normalize_metrics(snapshot or {}, graph, scenario["scenario_code"])
    overrides = scenario.get("diagnostic_observations", [])
    if not isinstance(overrides, list):
        raise ValueError("diagnostic_observations must be a list")
    healthy = scenario.get("client_internal_context", {}).get(STRENGTH_FIELD, "")
    protected = [
        {"text": clause, "scope": _word_scope(scenario, clause), "quantities": _quantities(clause),
         "source_ref": f"client_internal_context.{STRENGTH_FIELD}#{index}"}
        for index, clause in enumerate(CLAUSE.split(healthy), start=1) if clause.strip()
    ] if isinstance(healthy, str) else []
    return {
        "observations": narrative + metric_rows + [normalize_reviewed(row) for row in overrides],
        "measurements": measurements, "excluded": excluded + issues, "snapshot": snapshot or {},
        "protected_baselines": protected,
    }
