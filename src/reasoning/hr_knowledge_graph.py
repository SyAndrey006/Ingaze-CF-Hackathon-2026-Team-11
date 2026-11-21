"""Evaluate versionable HR graph packs against scoped, provenance-bearing observations."""

import json
import re
from collections import defaultdict
from fnmatch import fnmatchcase
from pathlib import Path
from urllib.parse import urlsplit

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
