"""Normalize narrative and telemetry without promoting proxy measurements to facts."""

import json
import math
import re
from datetime import date
from fnmatch import fnmatchcase
from pathlib import Path

from .hr_knowledge_graph import SCOPE_FIELDS
from .hr_policy import FEATURES

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
