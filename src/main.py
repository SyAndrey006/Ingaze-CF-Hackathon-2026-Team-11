#!/usr/bin/env python3
"""Run the Ingaze HR planning prototype and export a judge-ready submission."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.step2_root_cause_analysis import (
    DEFAULT_ANALYTICS, REQUEST_FIELD, STRENGTH_FIELD, diagnose, graph_export,
    load_analytics, load_graph, normalize_intake, profile_for, prioritized,
    run_root_cause_analysis,
)
from src.pipeline.step3_conditions_scoring import (
    MECHANISM_WEIGHT, baseline_fit, case_matches, load_library, precedent_signals,
    score_cases_and_research, score_diagnostic_candidates, search_library, source_class,
)
from src.pipeline.step4_guardrail_check import (
    BLOCKERS, action_fit, evaluate_guardrails, protected_intervention,
)
from src.pipeline.step5_phase_planner import build_reasoning_phase_plan, tailor_pilot
from src.pipeline.step6_hr_proposal import assemble_recommendation, generate_hr_proposal
from src.schemas.submission_models import SubmissionPayload
from starter_baseline_and_validator import validate_submission

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "database" / "ingaze_sandbox_dataset.json"
DEFAULT_CLIENT_INPUT = PROJECT_ROOT / "data" / "client_io" / "input.json"
DEFAULT_NORMALIZED_CLIENT_OUTPUT = PROJECT_ROOT / "data" / "intermediate_steps"
DEFAULT_CUSTOM_OUTPUT = PROJECT_ROOT / "data" / "client_io" / "output.json"
DEFAULT_PROPOSAL_OUTPUT = PROJECT_ROOT / "outputs" / "hr_proposal.md"
DEFAULT_CUSTOM_PROPOSAL_OUTPUT = PROJECT_ROOT / "data" / "client_io" / "proposal.md"
DEFAULT_INTERMEDIATE_DIR = PROJECT_ROOT / "data" / "intermediate_steps"


def _json_safe(value):
    """Convert stage objects and sets into stable JSON-compatible values."""
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    if hasattr(value, "value") and isinstance(value.value, (str, int, float)):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_json_safe(item) for item in value)
    return value


def _persist_stage_result(scenario_code, stage_name, result, output_dir=DEFAULT_INTERMEDIATE_DIR):
    """Write one deterministic pipeline handoff for inspection and replay."""
    safe_code = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(scenario_code)).strip("._") or "scenario"
    scenario_dir = Path(output_dir) / safe_code
    scenario_dir.mkdir(parents=True, exist_ok=True)
    output_path = scenario_dir / f"{stage_name}.json"
    output_path.write_text(
        json.dumps(_json_safe(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def plan(
    scenario, dataset, evidence_library=(), graph=None, analytics=None,
    proposal_llm_client=None,
):
    if graph is None:
        graph = load_graph()
    analytics = analytics if analytics is not None else {"active": {}, "cases": {}}
    normalized_client_input = scenario.get("_normalized_client_input")
    engine_scenario = {
        key: value for key, value in scenario.items()
        if key != "_normalized_client_input"
    }
    profile, intake, hypotheses, ranked_hypotheses = run_root_cause_analysis(
        engine_scenario, graph, analytics
    )
    return plan_from_graph(
        engine_scenario, dataset, evidence_library, graph, intake, hypotheses, profile, analytics,
        ranked_hypotheses=ranked_hypotheses,
        normalized_client_input=normalized_client_input,
        proposal_llm_client=proposal_llm_client,
    )


def plan_from_graph(
    scenario,
    dataset,
    library,
    graph,
    intake,
    hypotheses,
    profile,
    analytics,
    ranked_hypotheses=None,
    intermediate_dir=DEFAULT_INTERMEDIATE_DIR,
    normalized_client_input=None,
    proposal_llm_client=None,
):
    """Run diagnosis -> scoring -> guardrails -> phase plan -> final response."""
    if ranked_hypotheses is None:
        observations = {row["id"]: row for row in intake["observations"]}
        ranked_hypotheses = list(prioritized(hypotheses, observations, graph))

    diagnosis_state = {
        "scenario_code": scenario["scenario_code"],
        "profile": sorted(profile),
        "workforce_target": scenario.get("workforce_target"),
        "intake": intake,
        "diagnostic_hypotheses": hypotheses,
        "prioritized_hypotheses": ranked_hypotheses,
    }
    _persist_stage_result(scenario["scenario_code"], "step2_root_cause_analysis", diagnosis_state, intermediate_dir)

    scored_state = score_diagnostic_candidates(
        diagnosis_state,
        dataset,
        library,
        graph,
        analytics,
        normalized_client_input=normalized_client_input,
    )
    _persist_stage_result(
        scenario["scenario_code"], "step3_conditions_scoring", scored_state, intermediate_dir
    )

    guardrail_state = evaluate_guardrails(
        scenario,
        graph,
        intake,
        hypotheses,
        ranked_hypotheses,
        profile,
        scored_state=scored_state,
    )
    _persist_stage_result(
        scenario["scenario_code"], "step4_guardrail_check", guardrail_state, intermediate_dir
    )

    phase_state = build_reasoning_phase_plan(scenario, intake, guardrail_state, profile)
    _persist_stage_result(
        scenario["scenario_code"], "step5_phase_planner", phase_state, intermediate_dir
    )

    result, trace = assemble_recommendation(
        scenario, graph, diagnosis_state, scored_state, guardrail_state, phase_state
    )
    trace["proposal_markdown"] = generate_hr_proposal(
        normalized_client_input or scenario.get("_normalized_client_input", scenario),
        diagnosis_state,
        scored_state,
        guardrail_state,
        phase_state,
        llm_client=proposal_llm_client,
    )
    _persist_stage_result(
        scenario["scenario_code"],
        "step6_recommendation",
        {"result": result, "trace": trace},
        intermediate_dir,
    )
    return result, trace


_STEP1_SIGNAL_ADAPTER = {
    "SAY_DO_GAP": ("expectation_gap", "documented_broken_promise"),
    "LOW_EMPLOYER_BRAND_ALIGNMENT": ("brand_misalignment", "expectation_gap"),
    "MULTISITE_REPUTATION_VARIANCE": ("local_reputation",),
    "UNMONITORED_LOCAL_REVIEWS": ("local_reputation", "review_tracking"),
    "LOW_PUBLIC_RATING": ("employer_reputation_weak", "local_reputation"),
    "HEALTHY_AUTHENTIC_EVP": ("culture_ready",),
    "MOBILE_PORTAL_FRICTION": ("mobile_friction", "form_obstacle_verified"),
    "HIGH_APPLICATION_DROPOFF": ("application_abandonment", "application_loss"),
    "GENERIC_BOILERPLATE_JDS": ("generic_ads",),
    "CHANNEL_WORKFORCE_MISMATCH": ("corporate_engagement_weak",),
    "HIGH_TIME_TO_HIRE": ("hiring_delay",),
    "HIGH_EXTERNAL_AGENCY_DEPENDENCY": ("agency_spend",),
    "FRAGMENTED_CANDIDATE_FEEDBACK": ("feedback_fragmentation",),
    "LOW_INBOUND_QUALIFIED_APPLICANTS": ("application_loss",),
    "LOW_CORPORATE_SOCIAL_ENGAGEMENT": ("corporate_engagement_weak",),
    "MANUAL_HR_SPREADSHEET_DRAG": ("manual_tracking_load", "review_tracking"),
    "MISSING_CFO_ROI_EMV_VISIBILITY": ("emv",),
    "ACTIVE_ORGANIC_AMBASSADORS_PRESENT": ("existing_advocates",),
    "EARLY_FIRST_YEAR_ATTRITION": ("early_attrition",),
    "WEAK_MIDDLE_MANAGEMENT": ("manager_support",),
    "CAREER_PATH_OPACITY": ("career_clarity",),
    "WORKLOAD_BURNOUT": ("burnout",),
    "HIGH_FINANCIAL_TURNOVER_RISK": ("early_attrition",),
    "COHORT_OR_SITE_ASYMMETRY": ("local_reputation",),
}


def _deterministic_normalized_client(bundle):
    """Build a fact-extracted Step 1 record when LLM normalization is unavailable."""
    from src.pipeline.step1_normalize_input import normalize_client_input_deterministically

    return normalize_client_input_deterministically(bundle)


def _adapt_client_for_engine(bundle, normalized, graph):
    """Bridge Step 1's schema to the deterministic engine's intake schema."""
    from src.pipeline.step2_root_cause_analysis import REQUEST_FIELD, STRENGTH_FIELD

    scenario = dict(bundle.raw_scenario)
    scenario["scenario_code"] = normalized.scenario_code
    scenario.setdefault("company_name", normalized.company_name)
    scenario.setdefault("industry", normalized.industry_raw)
    scenario.setdefault("workforce_target", normalized.workforce_target_summary)
    if "headcount_and_footprint" not in scenario and (
        normalized.headcount or normalized.locations_count
    ):
        scenario["headcount_and_footprint"] = ", ".join(
            item for item in (
                f"{normalized.headcount} employees" if normalized.headcount else "",
                f"{normalized.locations_count} locations" if normalized.locations_count else "",
            ) if item
        )

    context = scenario.get("client_internal_context", {})
    if not isinstance(context, dict):
        context = {"client_summary": str(context)} if context else {}
    else:
        context = dict(context)
    if normalized.healthy_baselines and not context.get(STRENGTH_FIELD):
        context[STRENGTH_FIELD] = " ".join(
            f"{item.asset_or_cohort_name}: {item.evidence}. Preserve {item.do_not_touch_scope}."
            for item in normalized.healthy_baselines
        )
    if normalized.cohort_site_asymmetries and not context.get("cohort_and_site_asymmetries"):
        context["cohort_and_site_asymmetries"] = " ".join(
            f"Struggling: {item.struggling_segment}: {item.struggling_evidence}. "
            f"Healthy comparison: {item.healthy_comparison_segment}: {item.healthy_evidence}."
            for item in normalized.cohort_site_asymmetries
        )
    if normalized.leadership_requests:
        mapped_requests = " ".join(
            f"{item.stakeholder_role} requested {item.requested_action_text} "
            f"(mapped category: {item.inferred_action_category.value}; "
            f"urgency: {item.requested_urgency}; scope: {item.target_scope})."
            for item in normalized.leadership_requests
        )
        context[REQUEST_FIELD] = " ".join(
            value for value in (str(context.get(REQUEST_FIELD, "")), mapped_requests) if value
        )
    scenario["client_internal_context"] = context

    platform = scenario.get("ingaze_platform_signals", {})
    if not isinstance(platform, dict):
        platform = {"client_signal_summary": str(platform)} if platform else {}
    else:
        platform = dict(platform)
    if not platform:
        brief_fields = ("hr_intake_notes", "problem_description", "initial_challenge", "client_brief")
        brief = " ".join(str(scenario.get(key, "")) for key in brief_fields if scenario.get(key))
        if brief:
            platform["initial_challenge"] = brief
    scenario["ingaze_platform_signals"] = platform

    existing_observations = scenario.get("diagnostic_observations", [])
    if not isinstance(existing_observations, list):
        existing_observations = []
    observations = list(existing_observations)
    # The organizer adapter already supplies source-level observations. Its
    # canonical signal list is for matching, with no second copy of the evidence.
    adapted_signals = () if "intake_normalization_audit" in scenario else normalized.canonical_signals
    for index, signal in enumerate(adapted_signals, start=1):
        engine_signal = next(
            (tag for tag in _STEP1_SIGNAL_ADAPTER.get(signal.signal_code.value, ()) if tag in graph["signals"]),
            None,
        )
        if engine_signal is None:
            continue
        observations.append({
            "id": f"step1:{normalized.scenario_code}:{index}:{engine_signal}",
            "signal": engine_signal,
            "state": "present",
            "quality": "reported",
            "source_ref": f"step1.normalized_input.{signal.signal_code.value}",
            "origins": ["step1_normalized_client_input"],
            "scope": {
                "cohort": ", ".join(signal.affected_cohorts) or None,
                "site": None,
                "tenure": None,
                "window": "intake",
            },
            "evidence_type": "reported_observation",
            "text": signal.evidence_quote,
        })
    scenario["diagnostic_observations"] = observations

    if bundle.t0_telemetry is not None or bundle.sector_benchmarks is not None:
        snapshot = dict(scenario.get("analytics", {})) if isinstance(scenario.get("analytics"), dict) else {}
        if bundle.t0_telemetry is not None:
            snapshot.setdefault("t0_current_snapshot", bundle.t0_telemetry.model_dump(mode="json"))
        if bundle.sector_benchmarks is not None:
            snapshot.setdefault(
                "sector_peer_benchmarks", bundle.sector_benchmarks.model_dump(mode="json")
            )
        scenario["analytics"] = snapshot
    scenario["_normalized_client_input"] = normalized.model_dump(mode="json")
    return scenario


def run_custom_client(
    client_input: Path = DEFAULT_CLIENT_INPUT,
    *,
    dataset_path: Path = DEFAULT_DATA,
    analytics_path: Optional[Path] = None,
    output_path: Path = DEFAULT_CUSTOM_OUTPUT,
    proposal_output_path: Optional[Path] = None,
    normalized_output_path: Path = DEFAULT_NORMALIZED_CLIENT_OUTPUT,
    skip_llm_normalization: bool = False,
    no_analytics: bool = False,
    graph=None,
    evidence_library=None,
    llm_client=None,
    proposal_llm_client=None,
):
    """Normalize a custom brief, adapt it, and run the deterministic planner."""
    from src.pipeline.step1_normalize_input import load_standalone_input, normalize_client_input
    from src.schemas.domain_models import SectorPeerBenchmarks, TelemetrySnapshot
    from src.utils.llm_client import StructuredLLMClient

    input_path = Path(client_input)
    bundles = load_standalone_input(input_path)
    if not bundles:
        raise ValueError(f"No client scenarios were found in {input_path}.")
    if any(not any(value not in (None, "", [], {}) for key, value in bundle.raw_scenario.items()
                   if key not in {"scenario_code", "scenario_id"}) for bundle in bundles):
        raise ValueError(f"The client input {input_path} contains an empty scenario.")

    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8-sig"))
    if not isinstance(dataset, dict) or not isinstance(dataset.get("raw_case_study_narratives"), list):
        raise ValueError(f"{dataset_path} must contain a raw_case_study_narratives list.")
    if no_analytics:
        analytics_path = None
    elif analytics_path is None:
        analytics_path = DEFAULT_ANALYTICS if DEFAULT_ANALYTICS.exists() else None
    analytics = load_analytics(analytics_path)

    # Attach companion T0 data only on an exact scenario_code match. Inline
    # telemetry in the client file takes precedence over the shared snapshot.
    for index, bundle in enumerate(bundles):
        companion = analytics.get("active", {}).get(bundle.scenario_code, {})
        telemetry = bundle.t0_telemetry
        benchmarks = bundle.sector_benchmarks
        if telemetry is None:
            telemetry_raw = companion.get("t0_current_snapshot") or companion.get("t0_before_intervention")
            if isinstance(telemetry_raw, dict):
                telemetry = TelemetrySnapshot.model_validate(telemetry_raw)
        if benchmarks is None and isinstance(companion.get("sector_peer_benchmarks"), dict):
            benchmarks = SectorPeerBenchmarks.model_validate(companion["sector_peer_benchmarks"])
        if telemetry is not bundle.t0_telemetry or benchmarks is not bundle.sector_benchmarks:
            bundles[index] = bundle.model_copy(
                update={"t0_telemetry": telemetry, "sector_benchmarks": benchmarks}
            )

    normalized_inputs = []
    normalization_status = "llm_normalized"
    proposal_llm_client = None if skip_llm_normalization else proposal_llm_client
    adapted_count = sum("intake_normalization_audit" in bundle.raw_scenario for bundle in bundles)
    if skip_llm_normalization or adapted_count == len(bundles):
        normalization_status = (
            "deterministic_messy_intake" if adapted_count == len(bundles) else "deterministic_fallback"
        )
        normalized_inputs = [_deterministic_normalized_client(bundle) for bundle in bundles]
        print("Step 1 is using deterministic fact extraction.")
    else:
        if adapted_count:
            normalization_status = "mixed_llm_and_deterministic_messy_intake"
        client = llm_client or StructuredLLMClient()
        for bundle in bundles:
            print(f"Processing {input_path.name} — {bundle.scenario_code}...")
            try:
                normalized_inputs.append(normalize_client_input(bundle, client))
            except RuntimeError as exc:
                if "No LLM API key is configured" in str(exc):
                    normalization_status = "deterministic_fallback_no_api_key"
                    proposal_llm_client = None
                    normalized_inputs = [_deterministic_normalized_client(item) for item in bundles]
                    print(
                        "No LLM API key is configured; Step 1 is using deterministic fact "
                        "extraction and continuing through the recommendation pipeline."
                    )
                    break
                raise

    normalized_root = Path(normalized_output_path)
    if normalized_root.suffix.casefold() == ".json":
        # Accept the former file-style argument while placing Step 1 beside the
        # other per-scenario stage results.
        normalized_root = normalized_root.parent
    normalized_paths = []
    for bundle, normalized in zip(bundles, normalized_inputs):
        raw = bundle.raw_scenario
        output = normalized.model_dump(mode="json")
        if "intake_normalization_audit" in raw:
            output.update(
                reported_intake_observations=raw["reported_intake_observations"],
                protected_scopes=raw["protected_scopes"],
                intake_normalization_audit=raw["intake_normalization_audit"],
            )
        normalized_paths.append(
            _persist_stage_result(bundle.scenario_code, "step1_normalize_input", output, normalized_root)
        )
    portable_normalized_paths = [
        path.relative_to(PROJECT_ROOT).as_posix()
        if path.is_absolute() and path.is_relative_to(PROJECT_ROOT)
        else str(path)
        for path in normalized_paths
    ]
    normalized_path_value = (
        portable_normalized_paths[0]
        if len(portable_normalized_paths) == 1
        else portable_normalized_paths
    )

    graph = graph or load_graph()
    evidence_library = evidence_library if evidence_library is not None else load_library()

    planned = []
    traces = []
    for bundle, normalized in zip(bundles, normalized_inputs):
        scenario = _adapt_client_for_engine(bundle, normalized, graph)
        result, trace = plan(
            scenario, dataset, evidence_library, graph, analytics,
            proposal_llm_client=proposal_llm_client,
        )
        planned.append(result)
        traces.append(trace)

    payload = {
        "team_name": "Team 11",
        "chosen_architecture_paradigm": (
            "Step 1 client normalization, evidence-grounded adaptation, and deterministic HR policy "
            "with weighted case-based reasoning"
        ),
        "normalization_status": normalization_status,
        "normalized_input_path": normalized_path_value,
        "scenarios": planned,
        "traces": traces,
    }
    SubmissionPayload.model_validate(payload)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for bundle, result in zip(bundles, planned):
        company_name = bundle.raw_scenario.get("company_name") or result["scenario_code"]
        print(f"\n{company_name} ({result['scenario_code']})")
        print(f"  Root-cause hypotheses: {len(result.get('diagnosed_root_causes', []))}")
        print(f"  Phase actions: {sum(len(result.get(key, [])) for key in ('phase_1_actions', 'phase_2_actions', 'phase_3_actions'))}")
        print(f"  Guardrails: {len(result.get('blocked_traps_and_guardrails', []))}")
        print(f"  Matched precedents: {len(result.get('matched_case_studies', []))}")
    proposal_path = Path(proposal_output_path or DEFAULT_CUSTOM_PROPOSAL_OUTPUT)
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(
        "\n\n---\n\n".join(trace["proposal_markdown"] for trace in traces) + "\n",
        encoding="utf-8",
    )
    for normalized_path in normalized_paths:
        print(f"Wrote normalized client input: {normalized_path}")
    print(f"Wrote custom recommendation and reasoning trace: {output}")
    print(f"Wrote readable HR proposal: {proposal_path}")
    return payload


def main(argv: Optional[Sequence[str]] = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--analytics", type=Path, help="Optional companion telemetry file")
    parser.add_argument("--no-analytics", action="store_true", help="Skip loading the companion telemetry file")
    parser.add_argument("--out", type=Path, help="Sandbox submission path; also selects the custom output path in client mode")
    parser.add_argument(
        "--proposal-out",
        type=Path,
        help="Write the readable HR proposal Markdown to this path (default: outputs/hr_proposal.md, or data/client_io/proposal.md in client mode).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--client-input",
        type=Path,
        nargs="?",
        const=DEFAULT_CLIENT_INPUT,
        help="Run a custom client brief instead of the three sandbox scenarios (default path: data/client_io/input.json).",
    )
    mode.add_argument(
        "--sandbox",
        action="store_true",
        help="Run the official three sandbox scenarios instead of data/client_io/input.json.",
    )
    parser.add_argument(
        "--skip-llm-normalization",
        action="store_true",
        help="Skip Step 1's LLM extraction and run the raw client brief through deterministic intake.",
    )
    parser.add_argument("--trace", action="store_true", help="Print source paths and planning decisions")
    parser.add_argument("--trace-out", type=Path, help="Write the reasoning trace as JSON")
    parser.add_argument("--graph-out", type=Path, help="Write the graph's typed nodes and edges as JSON")
    parser.add_argument("--graph-pack", type=Path, action="append", default=[],
                        help="Load an additional graph JSON pack. May be repeated.")
    parser.add_argument("--observations", type=Path, help="Load scoped observations keyed by scenario code")
    parser.add_argument("--evidence-pack", type=Path, action="append", default=[],
                        help="Load an additional JSON evidence pack. May be repeated.")
    parser.add_argument("--search-evidence", metavar="QUERY", help="Search the evidence library without generating a plan")
    args = parser.parse_args(argv)
    if args.client_input is None and not args.sandbox:
        args.client_input = DEFAULT_CLIENT_INPUT
    try:
        evidence_library = load_library(args.evidence_pack)
        graph = load_graph(args.graph_pack)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.search_evidence is not None:
        print(json.dumps(search_library(evidence_library, query=args.search_evidence), indent=2, ensure_ascii=False))
        return
    if args.skip_llm_normalization and args.client_input is None:
        parser.error("--skip-llm-normalization requires --client-input.")
    if args.client_input is not None:
        try:
            proposal_llm_client = None
            if not args.skip_llm_normalization:
                from src.utils.llm_client import StructuredLLMClient

                candidate_client = StructuredLLMClient()
                try:
                    candidate_client._resolve_credentials()
                except RuntimeError as exc:
                    if "No LLM API key is configured" not in str(exc):
                        raise
                else:
                    proposal_llm_client = candidate_client
            result = run_custom_client(
                args.client_input,
                dataset_path=args.dataset,
                analytics_path=args.analytics,
                output_path=args.out or DEFAULT_CUSTOM_OUTPUT,
                proposal_output_path=args.proposal_out,
                skip_llm_normalization=args.skip_llm_normalization,
                no_analytics=args.no_analytics,
                graph=graph,
                evidence_library=evidence_library,
                llm_client=proposal_llm_client,
                proposal_llm_client=proposal_llm_client,
            )
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        if args.trace_out:
            args.trace_out.parent.mkdir(parents=True, exist_ok=True)
            args.trace_out.write_text(json.dumps(result["traces"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if args.graph_out:
            args.graph_out.parent.mkdir(parents=True, exist_ok=True)
            args.graph_out.write_text(json.dumps(graph_export(graph), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if args.trace:
            print(json.dumps(result["traces"], indent=2, ensure_ascii=False))
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
    SubmissionPayload.model_validate(payload)
    output_path = args.out or Path("submission.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    errors, warnings = validate_submission(output_path, dataset, scenarios)
    traces = [trace for _, trace in plans]
    proposal_path = args.proposal_out or (
        args.out.with_suffix(".md") if args.out else DEFAULT_PROPOSAL_OUTPUT
    )
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(
        "\n\n---\n\n".join(trace["proposal_markdown"] for trace in traces) + "\n",
        encoding="utf-8",
    )
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
    print(f"Wrote {output_path} with {len(plans)} scenario plans and {len(warnings)} validation warnings.")
    print(f"Wrote readable HR proposal: {proposal_path}")


if __name__ == "__main__":
    main()
