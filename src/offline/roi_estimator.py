"""Precedent-grounded ROI ranges and pilot target metrics.

Method (deterministic, no LLM, no scenario-specific logic):

* Client baseline: the client's own T0 telemetry plus quantities stated in the
  intake text (e.g. "EUR 190k/quarter" agency spend, "150 hours/year").
* Lever: the relative T0 -> T1 change of the same metric in the matched
  precedents (only improving deltas count).
* Estimate: baseline x [smallest, largest] precedent change -> a range, never a
  point forecast. No matching precedent -> no number, only a verification note.

Every figure carries the baseline source and the precedent cases it came from.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from src.offline.database_loader import load_normalized_cases

DEFAULT_NORMALIZED_CASES = Path(__file__).resolve().parents[2] / "database" / "normalized" / "normalized_cases.json"

# Metrics where a decrease is an improvement.
LOWER_IS_BETTER = {
    "application_form_dropoff_pct", "early_first_year_attrition_pct", "avg_time_to_hire_days",
    "agency_filled_roles_pct", "cross_location_rating_std_dev_5", "external_claims_gap_stars_5",
    "manual_hr_tracking_hours_month", "estimated_annual_attrition_exposure_eur",
}

METRIC_LABELS = {
    "application_form_dropoff_pct": ("Application form drop-off", "%"),
    "applicant_conversion_rate_pct": ("Applicant conversion rate", "%"),
    "early_first_year_attrition_pct": ("First-year attrition", "%"),
    "avg_time_to_hire_days": ("Time-to-hire", " days"),
    "agency_filled_roles_pct": ("Agency-filled roles", "%"),
    "cross_location_rating_std_dev_5": ("Cross-site rating spread (std dev)", " stars"),
    "external_claims_gap_stars_5": ("Say-Do gap (claims vs reviews)", " stars"),
    "manual_hr_tracking_hours_month": ("Manual HR tracking", " h/month"),
    "candidate_survey_completion_rate_pct": ("Candidate survey completion", "%"),
    "quarterly_organic_impressions": ("Quarterly organic impressions", ""),
    "overall_review_rating_5": ("Employer review rating", " stars"),
    "brand_alignment_index_100": ("Brand alignment index", " pts"),
}

# Domain mapping: which outcome metric a rule's pilot is meant to move.
RULE_TARGET_METRIC = {
    "application_friction": "application_form_dropoff_pct",
    "role_information": "applicant_conversion_rate_pct",
    "expectation_drift": "external_claims_gap_stars_5",
    "management_practice": "early_first_year_attrition_pct",
    "onboarding_clarity": "early_first_year_attrition_pct",
    "manual_measurement": "manual_hr_tracking_hours_month",
    "recruiter_handoff": "avg_time_to_hire_days",
    "interview_capacity": "avg_time_to_hire_days",
    "qualified_applicant_supply": "avg_time_to_hire_days",
    "external_staffing_dependency": "agency_filled_roles_pct",
    "reputation_location": "cross_location_rating_std_dev_5",
    "feedback_coverage": "candidate_survey_completion_rate_pct",
    "advocacy_pilot": "quarterly_organic_impressions",
}

_PERIOD_FACTOR = {"week": 52, "month": 12, "quarter": 4, "year": 1}


def _leaf_values(tree, prefix="") -> Dict[str, float]:
    values = {}
    for key, value in (tree or {}).items():
        if isinstance(value, dict):
            values.update(_leaf_values(value, f"{prefix}{key}."))
        elif type(value) in (int, float):
            values.setdefault(key, float(value))
    return values


def _client_values(diagnosis_state) -> Dict[str, Dict[str, Optional[float]]]:
    """Leaf metric -> {value, peer} from the client's T0 intake measurements."""
    result = {}
    for row in diagnosis_state.get("intake", {}).get("measurements", []):
        leaf = str(row.get("metric_path", "")).rsplit(".", 1)[-1]
        if leaf and leaf not in result and type(row.get("value")) in (int, float):
            result[leaf] = {"value": float(row["value"]), "peer": row.get("peer_value"),
                            "source": row.get("source_ref")}
    snapshot = diagnosis_state.get("intake", {}).get("snapshot") or {}
    peers = _leaf_values(snapshot.get("sector_peer_benchmarks"))
    for leaf, value in _leaf_values(snapshot.get("t0_current_snapshot")).items():
        result.setdefault(leaf, {"value": value, "peer": None, "source": f"telemetry:{leaf}"})
        if result[leaf]["peer"] is None and leaf in peers:
            result[leaf]["peer"] = peers[leaf]
    return result


def _precedent_changes(case_ids: Sequence[str], metric: str, cases_by_id) -> List[dict]:
    """Improving relative T0 -> T1 changes of ``metric`` in the matched cases."""
    changes = []
    for case_id in case_ids:
        case = cases_by_id.get(case_id)
        if case is None:
            continue
        for delta in case.quantified_roi_deltas:
            if delta.metric_name != metric or not delta.t0_value:
                continue
            relative = (delta.t1_value - delta.t0_value) / delta.t0_value
            improving = relative < 0 if metric in LOWER_IS_BETTER else relative > 0
            if improving:
                changes.append({"case_id": case.case_id, "case_name": case.case_name.split(" (")[0],
                                "relative_change": relative})
    return changes


def _fmt(value: float, unit: str) -> str:
    if unit == "%":
        return f"{value:.1f}%"
    if unit == " stars":
        return f"{value:.2f} stars"
    if abs(value) >= 1000:
        return f"{value:,.0f}{unit}"
    return f"{value:.1f}{unit}" if value % 1 else f"{value:.0f}{unit}"


def _eur(value: float) -> str:
    return f"EUR {value / 1e6:.2f}M" if value >= 1e6 else f"EUR {value / 1e3:.0f}k"


def pilot_target(rule_id: str, client: dict, case_ids: Sequence[str], cases_by_id) -> Optional[dict]:
    """Target for one pilot: client T0 -> precedent-implied value, with peer benchmark."""
    metric = RULE_TARGET_METRIC.get(rule_id)
    if metric is None or metric not in client:
        return None
    changes = _precedent_changes(case_ids, metric, cases_by_id)
    if not changes:
        return None
    baseline = client[metric]["value"]
    peer = client[metric]["peer"]
    span = sorted(row["relative_change"] for row in changes)
    middle = len(span) // 2
    median = span[middle] if len(span) % 2 else (span[middle - 1] + span[middle]) / 2
    target = baseline * (1 + median)
    label, unit = METRIC_LABELS.get(metric, (metric.replace("_", " "), ""))
    direction = "≤" if metric in LOWER_IS_BETTER else "≥"
    span_text = f"{span[0]:+.0%}" if len(span) == 1 else f"{span[0]:+.0%} to {span[-1]:+.0%}"
    text = (f"{label} {_fmt(baseline, unit)} → {direction} {_fmt(target, unit)} "
            f"(median matched-precedent change {median:+.0%}, range {span_text}"
            + (f"; sector peers {_fmt(float(peer), unit)}" if type(peer) in (int, float) else "") + ")")
    gate_text = f"{label} {direction} {_fmt(target, unit)} in the pilot scope, with protected baselines unchanged"
    return {"metric": metric, "baseline": baseline, "target": round(target, 2), "peer": peer,
            "precedent_changes": changes, "text": text, "gate_text": gate_text}


def _stated_amounts(observations: Iterable[dict], signals: set, unit: str) -> List[dict]:
    """Annualized quantities stated in intake text for the given signals."""
    found, seen = [], set()
    for row in observations:
        if row.get("signal") not in signals or row.get("state") != "present":
            continue
        for quantity in row.get("quantities", []) or []:
            if quantity.get("unit") != unit and not (unit == "hours" and "hour" in str(quantity.get("unit"))):
                continue
            text = row.get("text", "")
            period = re.search(rf"{re.escape(quantity['text'])}\s*(?:/|per\s+|a\s+)(week|month|quarter|year)",
                               text, re.I)
            unit_period = re.search(r"/(week|month|quarter|year)", str(quantity.get("unit")))
            period_name = (period[1] if period else unit_period[1] if unit_period else None)
            if period_name is None:
                continue
            annual = quantity["value"] * _PERIOD_FACTOR[period_name.lower()]
            key = (round(annual, 2), row.get("source_ref"))
            if key not in seen:
                seen.add(key)
                found.append({"annual_value": annual, "text": quantity["text"], "period": period_name,
                              "source_ref": row.get("source_ref")})
    return found


def _range_line(name, baseline, baseline_text, changes, money=True):
    reductions = sorted(abs(row["relative_change"]) for row in changes)
    low, high = baseline * reductions[0], baseline * reductions[-1]
    cases = ", ".join(dict.fromkeys(row["case_name"] for row in changes))
    value = (f"{_eur(low)}–{_eur(high)} per year" if money else f"{low:.0f}–{high:.0f} hours per year")
    if len(reductions) == 1 or abs(high - low) < 1e-9:
        value = f"{_eur(low)} per year" if money else f"{low:.0f} hours per year"
    return {
        "lever": name, "baseline": baseline_text, "estimate": value,
        "low": round(low, 2), "high": round(high, 2), "unit": "EUR/year" if money else "hours/year",
        "precedent_reductions": [round(r, 4) for r in reductions], "precedent_cases": cases,
        "text": (f"**{name}:** baseline {baseline_text} × precedent reduction "
                 f"{reductions[0]:.0%}" + (f"–{reductions[-1]:.0%}" if len(reductions) > 1 else "")
                 + f" ({cases}) → **{value}**"),
    }


def estimate_roi(diagnosis_state: dict, scored_state: dict, cases=None) -> dict:
    """Return pilot targets per rule and annual ROI ranges for the CFO view."""
    cases = cases if cases is not None else load_normalized_cases(DEFAULT_NORMALIZED_CASES).cases
    cases_by_id = {case.case_id: case for case in cases}
    case_ids = [row.get("case_id") for row in scored_state.get("matched_case_studies", []) if row.get("case_id")]
    client = _client_values(diagnosis_state)
    observations = diagnosis_state.get("intake", {}).get("observations", [])
    lines, gaps = [], []

    exposure = client.get("estimated_annual_attrition_exposure_eur")
    if exposure:
        changes = _precedent_changes(case_ids, "estimated_annual_attrition_exposure_eur", cases_by_id)
        if changes:
            lines.append(_range_line("Attrition risk exposure", exposure["value"],
                                     f"{_eur(exposure['value'])}/year (client estimate)", changes))
        else:
            gaps.append("Attrition exposure is stated but no matched precedent measured its change.")

    agency = _stated_amounts(observations, {"agency_spend"}, "EUR")
    if agency:
        changes = _precedent_changes(case_ids, "agency_filled_roles_pct", cases_by_id)
        stated = max(agency, key=lambda row: row["annual_value"])
        baseline_text = f"{_eur(stated['annual_value'])}/year (stated {stated['text']}/{stated['period']})"
        if changes:
            lines.append(_range_line("Temporary agency spend", stated["annual_value"], baseline_text, changes))
        else:
            gaps.append("Agency spend is stated but no matched precedent measured agency reliance.")

    hours = _stated_amounts(observations, {"manual_tracking_load", "review_tracking", "post_tracking"}, "hours")
    manual = client.get("manual_hr_tracking_hours_month")
    changes = _precedent_changes(case_ids, "manual_hr_tracking_hours_month", cases_by_id)
    if changes and (hours or manual):
        if hours:
            stated = max(hours, key=lambda row: row["annual_value"])
            baseline, baseline_text = stated["annual_value"], f"{stated['annual_value']:.0f} h/year (stated)"
        else:
            baseline = manual["value"] * 12
            baseline_text = f"{baseline:.0f} h/year ({manual['value']:.1f} h/month telemetry)"
        lines.append(_range_line("HR time reclaimed", baseline, baseline_text, changes, money=False))

    targets = {}
    for rule_id in RULE_TARGET_METRIC:
        target = pilot_target(rule_id, client, case_ids, cases_by_id)
        if target:
            targets[rule_id] = target

    return {
        "method": ("Client baseline (current telemetry or an amount stated in the brief) x the smallest and "
                   "largest measured before/after improvement of the same metric in the matched precedents. "
                   "Ranges, not forecasts; "
                   "lines can overlap and are not additive; hours are not converted to EUR because no hourly "
                   "cost is supplied."),
        "roi_lines": lines,
        "not_quantified": gaps,
        "pilot_targets": targets,
    }


def attach_targets(phase_state: dict, roi_state: dict) -> dict:
    """Add the target metric to Phase 2 pilots and Phase 3 scaling gates of each rule."""
    targets = roi_state.get("pilot_targets", {})
    for phase in ("phase_2_actions", "phase_3_actions"):
        for action in phase_state.get(phase, []):
            target = targets.get(action.get("rule"))
            if target:
                action["target_metric"] = {
                    **{key: target[key] for key in ("metric", "baseline", "target", "peer")},
                    "text": target["text"] if phase == "phase_2_actions" else target["gate_text"],
                }
    return phase_state
