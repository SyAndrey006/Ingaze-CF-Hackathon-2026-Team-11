"""
Module: case_normalizer.py
Stage: Offline Indexing (Runs Once)
Execution Type: Formula (deterministic) on top of a human-reviewed curation file

Description:
    Builds `database/normalized/normalized_cases.json` (NormalizedCasesDB) from:
      1. `database/ingaze_sandbox_dataset.json` -> raw_case_study_narratives (any number of cases)
      2. `database/ingaze_synthetic_analytics_snapshots.json` -> case_study_analytics_snapshots
         (joined 1:1 on exact `case_name`; optional per case)
      3. `database/curation/case_curation.json` -> AI-assisted mapping of each narrative to
         canonical enums (sector, workforce, signals, action steps, snippets). Every signal
         carries an exact source quote and an evidence level (stated / inferred), and every
         entry a `review_status` (`reviewed` / `llm_draft`).

    Why curation + formula instead of a live LLM call:
      - reproducible: same input -> same JSON, no API key needed at demo time
      - auditable: every tag points to a verbatim quote that is checked here
      - new cases are drafted by `case_curation_drafter.py` (LLM), then reviewed by a human.
        Unreviewed drafts are built with a warning and flagged in the output.

    Anti-hardcoding: never reads company_scenarios_to_diagnose or
    active_scenario_analytics_snapshots. Only completed historical cases.

Usage:
    python -m src.offline.case_normalizer            # build + verify + write
    python -m src.offline.case_normalizer --check    # verify only, no write
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Collection, Dict, List, Optional, Set, Tuple

from src.schemas.domain_models import (
    ActionCategory,
    CaseInterventionStep,
    NormalizedCasesDB,
    NormalizedCaseStudy,
    QuantifiedROIDelta,
    SectorCategory,
    SectorPeerBenchmarks,
    SignalCode,
    TelemetrySnapshot,
    WorkforceArchetype,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SANDBOX = REPO_ROOT / "database" / "ingaze_sandbox_dataset.json"
DEFAULT_SNAPSHOTS = REPO_ROOT / "database" / "ingaze_synthetic_analytics_snapshots.json"
DEFAULT_CURATION = REPO_ROOT / "database" / "curation" / "case_curation.json"
DEFAULT_OUTPUT = REPO_ROOT / "database" / "normalized" / "normalized_cases.json"

# Telemetry metrics used for T0 -> T1 ROI deltas: (dot path, label, unit)
ROI_METRICS: List[Tuple[str, str, str]] = [
    ("public_reputation.overall_review_rating_5", "Employer review rating", "stars"),
    ("public_reputation.brand_alignment_index_100", "Employer Brand Alignment Index", "pts"),
    ("public_reputation.external_claims_gap_stars_5", "Say-Do Gap (claims vs reviews)", "stars"),
    ("public_reputation.cross_location_rating_std_dev_5", "Cross-site rating variance (std dev)", "stars"),
    ("career_portal_and_funnel.application_form_dropoff_pct", "Application form drop-off", "%"),
    ("career_portal_and_funnel.applicant_conversion_rate_pct", "Applicant conversion rate", "%"),
    ("career_portal_and_funnel.candidate_survey_completion_rate_pct", "Candidate survey completion", "%"),
    ("social_and_employee_voice.corporate_linkedin_er_pct", "Corporate LinkedIn engagement rate", "%"),
    ("social_and_employee_voice.quarterly_organic_impressions", "Quarterly organic impressions", ""),
    ("social_and_employee_voice.manual_hr_tracking_hours_month", "Manual HR tracking", "h/month"),
    ("hiring_and_retention_kpis.early_first_year_attrition_pct", "Early first-year attrition", "%"),
    ("hiring_and_retention_kpis.estimated_annual_attrition_exposure_eur", "Annual attrition exposure", "EUR"),
    ("hiring_and_retention_kpis.avg_time_to_hire_days", "Time-to-Hire", "days"),
    ("hiring_and_retention_kpis.agency_filled_roles_pct", "Agency-filled roles", "%"),
]

_VALID_SIGNALS = {s.value for s in SignalCode}
_VALID_ACTIONS = {a.value for a in ActionCategory}
_VALID_SECTORS = {s.value for s in SectorCategory}
_VALID_WORKFORCES = {w.value for w in WorkforceArchetype}
REVIEW_STATUSES = ("reviewed", "llm_draft")
DRAFT_STATUS = "llm_draft"


class UnreviewedCurationWarning(UserWarning):
    """Emitted when the case store is built from LLM drafts that no human has reviewed yet."""


def research_snippet_nos(raw_sandbox_data: Dict[str, Any]) -> Set[int]:
    """Snippet numbers that actually exist in the sandbox (no hardcoded 1..10 range)."""
    return {int(s["snippet_no"]) for s in raw_sandbox_data.get("raw_empirical_research_snippets", [])}


def draft_case_ids(curation: Dict[str, Any]) -> List[str]:
    return [e["case_id"] for e in curation.get("cases", []) if e.get("review_status") == DRAFT_STATUS]


# -----------------------------------------------------------------------------
# Loading
# -----------------------------------------------------------------------------

def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _raw_case_text(raw_case: Dict[str, Any]) -> str:
    return " ".join(str(v) for v in raw_case.values())


def _get_path(obj: Optional[Dict[str, Any]], dot_path: str) -> Optional[float]:
    cur: Any = obj
    for part in dot_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if isinstance(cur, (int, float)) else None


# -----------------------------------------------------------------------------
# Verification (anti-hallucination + schema integrity)
# -----------------------------------------------------------------------------

def verify_curation(
    curation: Dict[str, Any],
    raw_cases: List[Dict[str, Any]],
    valid_snippet_nos: Optional[Collection[int]] = None,
    require_all_raw_cases: bool = True,
) -> List[str]:
    """
    Return a list of human-readable errors. Empty list == curation is valid.

    `valid_snippet_nos`: snippet numbers present in the sandbox (see `research_snippet_nos`).
    If None, snippets only need to be positive integers.
    `require_all_raw_cases`: report raw narratives that have no curation entry.
    """
    errors: List[str] = []
    raw_by_name = {c["case_name"]: c for c in raw_cases}
    entries = curation.get("cases", [])

    seen_ids, seen_names = set(), set()
    for entry in entries:
        cid = entry.get("case_id", "?")
        name = entry.get("case_name")
        if cid in seen_ids:
            errors.append(f"{cid}: duplicate case_id")
        seen_ids.add(cid)
        if name in seen_names:
            errors.append(f"{cid}: duplicate case_name")
        seen_names.add(name)

        raw = raw_by_name.get(name)
        if raw is None:
            errors.append(f"{cid}: case_name not found in raw narratives: {name!r}")
            continue
        text = _raw_case_text(raw)

        if entry.get("review_status") not in REVIEW_STATUSES:
            errors.append(f"{cid}: review_status must be one of {REVIEW_STATUSES}, got {entry.get('review_status')!r}")
        if entry.get("sector_category") not in _VALID_SECTORS:
            errors.append(f"{cid}: invalid sector_category {entry.get('sector_category')}")
        for wf in entry.get("workforce_archetypes", []):
            if wf not in _VALID_WORKFORCES:
                errors.append(f"{cid}: invalid workforce archetype {wf}")

        for group in ("problem_signals", "healthy_signals"):
            for sig in entry.get(group, []):
                if sig["signal"] not in _VALID_SIGNALS:
                    errors.append(f"{cid}: invalid signal {sig['signal']}")
                if sig.get("evidence") not in ("stated", "inferred"):
                    errors.append(f"{cid}: signal {sig['signal']} needs evidence stated|inferred")
                if sig.get("quote", "") not in text or not sig.get("quote"):
                    errors.append(f"{cid}: quote for {sig['signal']} is not verbatim in raw case: {sig.get('quote')!r}")

        for step in entry.get("steps", []):
            if step["action_category"] not in _VALID_ACTIONS:
                errors.append(f"{cid}: invalid action_category {step['action_category']}")
            if step["phase_bucket"] not in (1, 2, 3):
                errors.append(f"{cid}: phase_bucket must be 1..3")

        for no in entry.get("snippets", []):
            if valid_snippet_nos is not None and int(no) not in valid_snippet_nos:
                errors.append(f"{cid}: research snippet {no} does not exist (valid: {sorted(valid_snippet_nos)})")
            elif int(no) < 1:
                errors.append(f"{cid}: research snippet {no} must be >= 1")

    if require_all_raw_cases:
        missing = set(raw_by_name) - seen_names
        for name in sorted(missing):
            errors.append(
                f"raw case not curated: {name} "
                "(draft it with `python -m src.offline.case_curation_drafter`)"
            )
    return errors


# -----------------------------------------------------------------------------
# ROI deltas from T0 -> T1 telemetry
# -----------------------------------------------------------------------------

def _fmt(value: float, unit: str) -> str:
    if unit == "EUR":
        return f"EUR {value:,.0f}"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.2f}".rstrip("0").rstrip(".") + (f" {unit}" if unit and unit != "%" else unit)
    return f"{int(value):,}" + (f" {unit}" if unit and unit != "%" else unit)


def compute_roi_deltas(t0: Optional[Dict[str, Any]], t1: Optional[Dict[str, Any]]) -> List[QuantifiedROIDelta]:
    deltas: List[QuantifiedROIDelta] = []
    for path, label, unit in ROI_METRICS:
        v0, v1 = _get_path(t0, path), _get_path(t1, path)
        if v0 is None or v1 is None or v0 == v1:
            continue
        rel = f" ({(v1 - v0) / v0 * 100:+.0f}%)" if v0 else ""
        deltas.append(
            QuantifiedROIDelta(
                metric_name=path.split(".")[-1],
                t0_value=float(v0),
                t1_value=float(v1),
                delta_display=f"{label}: {_fmt(v0, unit)} -> {_fmt(v1, unit)}{rel}",
            )
        )
    # Most relevant first: largest relative change on top (ties keep metric order)
    deltas.sort(
        key=lambda d: -abs((d.t1_value - d.t0_value) / d.t0_value) if d.t0_value else 0.0
    )
    return deltas


# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------

def build_cases_db(
    raw_sandbox_data: Dict[str, Any],
    raw_snapshots_data: Optional[Dict[str, Any]],
    curation: Dict[str, Any],
) -> NormalizedCasesDB:
    raw_cases = raw_sandbox_data["raw_case_study_narratives"]
    errors = verify_curation(curation, raw_cases, valid_snippet_nos=research_snippet_nos(raw_sandbox_data))
    if errors:
        raise ValueError("Case curation failed verification:\n  - " + "\n  - ".join(errors))
    drafts = draft_case_ids(curation)
    if drafts:
        warnings.warn(
            f"{len(drafts)} case(s) built from unreviewed LLM drafts: {', '.join(drafts)}. "
            "Review them in the curation file, then run "
            "`python -m src.offline.case_curation_drafter --approve <CASE_ID>`.",
            UnreviewedCurationWarning,
            stacklevel=2,
        )

    raw_by_name = {c["case_name"]: c for c in raw_cases}
    snaps_by_name: Dict[str, Dict[str, Any]] = {}
    if raw_snapshots_data:
        for snap in raw_snapshots_data.get("case_study_analytics_snapshots", []):
            snaps_by_name[snap["case_name"]] = snap

    cases: List[NormalizedCaseStudy] = []
    for entry in curation["cases"]:
        raw = raw_by_name[entry["case_name"]]
        snap = snaps_by_name.get(entry["case_name"], {})
        t0 = snap.get("t0_before_intervention")
        t1 = snap.get("t1_after_12_months")
        bench = snap.get("sector_peer_benchmarks")

        cases.append(
            NormalizedCaseStudy(
                case_id=entry["case_id"],
                case_name=entry["case_name"],
                curation_review_status=entry["review_status"],
                sector_category=SectorCategory(entry["sector_category"]),
                sector_benchmark_group=snap.get("sector_benchmark_group"),
                workforce_archetypes=[WorkforceArchetype(w) for w in entry["workforce_archetypes"]],
                headcount=snap.get("headcount"),
                locations_count=snap.get("locations_count"),
                canonical_problem_tags=list(dict.fromkeys(SignalCode(s["signal"]) for s in entry["problem_signals"])),
                healthy_starting_conditions=list(dict.fromkeys(SignalCode(s["signal"]) for s in entry["healthy_signals"])),
                intervention_steps=[CaseInterventionStep(**step) for step in entry["steps"]],
                measured_roi_summary=raw["measured_roi"],
                quantified_roi_deltas=compute_roi_deltas(t0, t1),
                applicable_research_snippet_nos=[int(n) for n in entry["snippets"]],
                sector_peer_benchmarks=SectorPeerBenchmarks(**bench) if bench else None,
                t0_snapshot=TelemetrySnapshot(**t0) if t0 else None,
                t1_snapshot=TelemetrySnapshot(**t1) if t1 else None,
            )
        )

    version = raw_sandbox_data.get("metadata", {}).get("version", "")
    return NormalizedCasesDB(
        source_dataset_version=(
            f"sandbox {version} | {len(cases)} historical cases | curation-verified"
            + (f" | {len(drafts)} unreviewed LLM drafts" if drafts else "")
        ).strip(),
        cases=cases,
    )


def run_case_normalization(
    sandbox_path: Path = DEFAULT_SANDBOX,
    snapshots_path: Optional[Path] = DEFAULT_SNAPSHOTS,
    curation_path: Path = DEFAULT_CURATION,
    output_path: Optional[Path] = DEFAULT_OUTPUT,
) -> NormalizedCasesDB:
    sandbox = _read_json(sandbox_path)
    snapshots = _read_json(snapshots_path) if snapshots_path and snapshots_path.exists() else None
    curation = _read_json(curation_path)
    db = build_cases_db(sandbox, snapshots, curation)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(db.model_dump_json(indent=2), encoding="utf-8")
    return db


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build normalized_cases.json from curated case mapping.")
    parser.add_argument("--check", action="store_true", help="Verify only, do not write output.")
    args = parser.parse_args(argv)
    try:
        db = run_case_normalization(output_path=None if args.check else DEFAULT_OUTPUT)
    except ValueError as exc:
        print(exc)
        return 1
    for case in db.cases:
        print(
            f"{case.case_id:<24} {case.sector_category.value:<32} "
            f"signals={len(case.canonical_problem_tags)} healthy={len(case.healthy_starting_conditions)} "
            f"steps={len(case.intervention_steps)} roi_deltas={len(case.quantified_roi_deltas)}"
            + ("  [UNREVIEWED LLM DRAFT]" if case.curation_review_status == DRAFT_STATUS else "")
        )
    print(f"\nOK: {len(db.cases)} cases verified" + ("" if args.check else f" -> {DEFAULT_OUTPUT}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
