#!/usr/bin/env python3
"""
Ingaze Hackathon Starter CLI — Dataset Inspector, Naive Baseline & Submission Validator
=======================================================================================
Zero external dependencies (Python 3.9+ standard library only).

Usage examples:
  1. Inspect the sandbox dataset & 3 company scenarios:
       python starter_baseline_and_validator.py --inspect

  2. Generate the "Naive Flat Prompt" baseline to beat (offline simulation or live BYOK LLM):
       python starter_baseline_and_validator.py --run-naive-baseline --out naive_baseline_output.json
       python starter_baseline_and_validator.py --run-naive-baseline --live-llm --out live_naive_output.json

  3. Validate your team's exported submission.json before judging:
       python starter_baseline_and_validator.py --validate submission.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET_PATH = BASE_DIR / "data" / "ingaze_sandbox_dataset.json"

REQUIRED_SCENARIO_OUTPUT_KEYS: Tuple[str, ...] = (
    "scenario_code",
    "diagnosed_root_causes",
    "blocked_traps_and_guardrails",
    "phase_1_actions",
    "phase_2_actions",
    "phase_3_actions",
    "matched_case_studies",
    "supporting_research_snippets",
)

OPTIONAL_SCENARIO_ENRICHMENT_KEYS: Tuple[str, ...] = (
    "strategic_focus_and_do_not_touch",
    "cohort_specific_strategies",
    "open_questions_and_hypotheses_for_client",
    "action_rationales",
)


def load_sandbox_and_scenarios(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    extra_scenario_path: Optional[Path] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Load the sandbox dataset and optionally append a custom extra scenario for testing."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Sandbox dataset not found at: {dataset_path}")

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    scenarios = list(dataset.get("company_scenarios_to_diagnose", []))

    if extra_scenario_path is not None:
        if not extra_scenario_path.exists():
            raise FileNotFoundError(f"Extra scenario file not found at: {extra_scenario_path}")
        extra_raw = json.loads(extra_scenario_path.read_text(encoding="utf-8"))
        extra_obj = extra_raw.get("blind_judge_scenario", extra_raw.get("client_intake_case", extra_raw))
        if "scenario_code" not in extra_obj:
            raise ValueError("Extra scenario JSON must contain 'scenario_code'.")
        existing_codes = {s.get("scenario_code") for s in scenarios}
        if extra_obj["scenario_code"] not in existing_codes:
            scenarios.append(extra_obj)

    return dataset, scenarios


def cmd_inspect(dataset: Dict[str, Any], scenarios: List[Dict[str, Any]]) -> None:
    """Print a clean overview of all domain ingredients in the sandbox dataset."""
    meta = dataset.get("metadata", {})
    pillars_block = dataset.get("domain_pillars_and_causal_dynamics", {})
    pillars = pillars_block.get("pillars", [])
    rules = pillars_block.get("raw_cross_pillar_rules_to_structure", [])
    snippets = dataset.get("raw_empirical_research_snippets", [])
    cases = dataset.get("raw_case_study_narratives", [])

    print("=" * 78)
    print(f"INGAZE HACKATHON SANDBOX — {meta.get('version', 'unknown')}")
    print("=" * 78)
    print(f"  - HR Domain Pillars:            {len(pillars)}")
    for p in pillars:
        print(f"      * {p.get('pillar_name')}")
    print(f"  - Cross-Pillar Field Notes:     {len(rules)}")
    print(f"  - Empirical Research Snippets:  {len(snippets)}")
    print(f"  - Anonymized B2B Case Studies:  {len(cases)}")
    for idx, cs in enumerate(cases, start=1):
        print(f"      {idx:2d}. {cs.get('case_name')}")
    snapshots_path = BASE_DIR / "data" / "ingaze_synthetic_analytics_snapshots.json"
    if snapshots_path.exists():
        snap_data = json.loads(snapshots_path.read_text(encoding="utf-8"))
        cs_snaps = len(snap_data.get("case_study_analytics_snapshots", []))
        sc_snaps = len(snap_data.get("active_scenario_analytics_snapshots", []))
        print(f"  - Optional Analytics Snapshots: {cs_snaps} case T0->T1 + {sc_snaps} scenario T0 tables ({snapshots_path.name})")
    messy_path = BASE_DIR / "data" / "ingaze_real_world_messy_intake.json"
    if messy_path.exists():
        messy_data = json.loads(messy_path.read_text(encoding="utf-8")).get("client_intake_case", {})
        print(
            f"  - Real-World Messy Intake #1:   {messy_data.get('scenario_code')} — {messy_data.get('company_name')} "
            f"({messy_path.name})"
        )
    blind_path = BASE_DIR / "data" / "ingaze_sunday_blind_test_meridiana.json"
    if blind_path.exists():
        blind_data = json.loads(blind_path.read_text(encoding="utf-8")).get("client_intake_case", {})
        print(
            f"  - Sunday Blind Live Test #2:    {blind_data.get('scenario_code')} — {blind_data.get('company_name')} "
            f"({blind_path.name})"
        )
    print(f"  - Company Scenarios Loaded:     {len(scenarios)}")
    for sc in scenarios:
        has_dual = "ingaze_platform_signals" in sc and "client_internal_context" in sc
        has_messy = "raw_discovery_call_notes" in sc and "ingaze_onboarding_surveys_raw" in sc
        dual_tag = (
            " [Outside-In Signals + Inside-Out Client Context]"
            if has_dual
            else (" [Raw Discovery Calls + Archetype/Cost Surveys + Noisy Telemetry]" if has_messy else "")
        )
        ind = sc.get("industry") or sc.get("basic_company_facts", {}).get("industry", "Unknown")
        print(f"      * {sc.get('scenario_code')} — {sc.get('company_name')} ({ind}){dual_tag}")
    print("=" * 78)


def _simulate_offline_naive_prompt(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic illustration of how a naive, unstructured LLM prompt behaves:
    it echoes surface keywords, obeys bad executive requests without checking prerequisites,
    leaks cross-industry phrases from noisy prompts, and retrieves superficial case matches.
    """
    code = scenario.get("scenario_code", "UNKNOWN")
    narrative = scenario.get("narrative_situation_to_solve", "").lower()

    if "cloudnova" in code.lower() or "weekend shop shift" in narrative:
        return {
            "scenario_code": code,
            "diagnosed_root_causes": [
                "Low LinkedIn post engagement and high 6-month engineer turnover",
            ],
            "blocked_traps_and_guardrails": [],
            "phase_1_actions": [
                "Launch external Employee Ambassador campaign and Automated Ambassador Content Tracking next week as requested by the CEO",
                "Introduce retail store weekend shift rotation mentioned in the exported review notes and mobile-first fast-apply",
            ],
            "phase_2_actions": [
                "Rewrite job descriptions and run pulse surveys",
            ],
            "phase_3_actions": [
                "Build an HR dashboard",
            ],
            "matched_case_studies": [
                "Gamma Retail (turnover reduction)",
                "FlowPay (LinkedIn engagement)",
            ],
            "supporting_research_snippets": [
                "Snippet 3: Employee ambassador posts generate 5x to 8x higher organic engagement.",
            ],
        }

    if "eurofreight" in code.lower() or "drivers" in narrative:
        return {
            "scenario_code": code,
            "diagnosed_root_causes": [
                "High career page bounce rate and slow hiring",
            ],
            "blocked_traps_and_guardrails": [],
            "phase_1_actions": [
                "Launch technical engineering storytelling on LinkedIn and rewrite driver job descriptions immediately",
                "Deploy mobile-first fast-apply tomorrow before running any career portal UX or persona audit",
            ],
            "phase_2_actions": [
                "Run a career portal UX audit later",
            ],
            "phase_3_actions": [],
            "matched_case_studies": [
                "FlowPay (LinkedIn engagement)",
                "Beta Logistica (driver hiring)",
            ],
            "supporting_research_snippets": [
                "Snippet 2: Switching to a 60-second mobile fast-apply reduces bounce rates.",
            ],
        }

    return {
        "scenario_code": code,
        "diagnosed_root_causes": [
            "Low organic social reach and fragmented HR spreadsheets",
        ],
        "blocked_traps_and_guardrails": [],
        "phase_1_actions": [
            "Immediately turn on Automated Ambassador Content Tracking across all locations before auditing or selecting ambassadors",
        ],
        "phase_2_actions": [
            "Collect reviews and candidate surveys",
        ],
        "phase_3_actions": [],
        "matched_case_studies": [
            "Alfa Group",
        ],
        "supporting_research_snippets": [
            "Snippet 3: Automated tracking reclaims 8 to 20 hours/month.",
        ],
    }


def _parse_llm_json_response(raw_content: str) -> Dict[str, Any]:
    """Strip optional markdown code fences and unwrap nested scenario objects from a live LLM response."""
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    parsed = json.loads(cleaned)
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return parsed[0]
    if isinstance(parsed, dict):
        if "scenarios" in parsed and isinstance(parsed["scenarios"], list) and parsed["scenarios"]:
            first = parsed["scenarios"][0]
            if isinstance(first, dict):
                return first
        return parsed
    return {}


def _call_live_flat_llm(dataset: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optional BYOK single-prompt LLM baseline via stdlib urllib (supports OpenAI / OpenRouter / Gemini).
    Dumps the ENTIRE raw unstructured dataset context (4 pillars, 6 field notes, 10 research snippets,
    21 full case studies) plus the full raw scenario object into a single flat prompt to test the true
    limits of a single-pass LLM without a structured reasoning architecture.
    """
    raw_domain_context = {
        "domain_pillars_and_causal_dynamics": dataset.get("domain_pillars_and_causal_dynamics", {}),
        "raw_empirical_research_snippets": dataset.get("raw_empirical_research_snippets", []),
        "raw_case_study_narratives": dataset.get("raw_case_study_narratives", []),
    }
    prompt = (
        "You are an HR strategy assistant. Below is a raw dump of HR domain materials (pillars, field notes, "
        "empirical research snippets, and 21 historical case studies) followed by a client company scenario.\n"
        f"Return ONLY valid JSON with keys {list(REQUIRED_SCENARIO_OUTPUT_KEYS)} "
        f"(where scenario_code is '{scenario.get('scenario_code')}').\n\n"
        "=== RAW DOMAIN MATERIALS (UNSTRUCTURED DUMP) ===\n"
        f"{json.dumps(raw_domain_context, ensure_ascii=False, indent=2)}\n\n"
        "=== CLIENT COMPANY SCENARIO TO DIAGNOSE ===\n"
        f"{json.dumps(scenario, ensure_ascii=False, indent=2)}\n"
    )

    openai_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if openai_key:
        is_openrouter = bool(os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("OPENAI_API_KEY"))
        url = (
            "https://openrouter.ai/api/v1/chat/completions"
            if is_openrouter
            else "https://api.openai.com/v1/chat/completions"
        )
        model = os.environ.get("BASELINE_MODEL", "openai/gpt-4o-mini" if is_openrouter else "gpt-4o-mini")
        payload = json.dumps(
            {
                "model": model,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            return _parse_llm_json_response(content)

    if gemini_key:
        model = os.environ.get("BASELINE_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        payload = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_llm_json_response(content)

    raise RuntimeError(
        "No API key found for --live-llm. Set OPENAI_API_KEY, OPENROUTER_API_KEY, or GEMINI_API_KEY, "
        "or omit --live-llm to run the built-in offline naive baseline."
    )


def generate_naive_baseline(
    dataset: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    live_llm: bool = False,
) -> Dict[str, Any]:
    """Generate a baseline submission JSON across all loaded scenarios."""
    outputs: List[Dict[str, Any]] = []
    for sc in scenarios:
        if live_llm:
            sc_out = _call_live_flat_llm(dataset, sc)
        else:
            sc_out = _simulate_offline_naive_prompt(sc)
        # Ensure all required keys exist as lists of strings
        normalized: Dict[str, Any] = {"scenario_code": sc.get("scenario_code", "")}
        for key in REQUIRED_SCENARIO_OUTPUT_KEYS:
            if key == "scenario_code":
                continue
            val = sc_out.get(key, []) if isinstance(sc_out, dict) else []
            if val is None:
                normalized[key] = []
            elif isinstance(val, list):
                normalized[key] = [
                    (" — ".join(str(v) for v in x.values() if v is not None) if isinstance(x, dict) else str(x))
                    for x in val
                    if x is not None
                ]
            else:
                normalized[key] = [str(val)]
        outputs.append(normalized)

    mode_label = "Live Single-Prompt Flat LLM (Full Raw Context Dump)" if live_llm else "Offline Naive Unstructured Prompt Simulator"
    return {
        "team_name": "Baseline_Naive_Flat_Prompt",
        "chosen_architecture_paradigm": f"Baseline to Beat ({mode_label} — single-pass unstructured prompt)",
        "scenarios": outputs,
    }


def validate_submission(
    submission_path: Path,
    dataset: Dict[str, Any],
    expected_scenarios: List[Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """
    Validate a team's exported submission JSON against the required output contract.
    Supports both the core required keys and optional strategic enrichment keys
    (e.g., strategic_focus_and_do_not_touch, cohort_specific_strategies,
    open_questions_and_hypotheses_for_client) without penalizing original or focused plans.
    Returns (errors, warnings). Does NOT contain confidential ground-truth answers.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not submission_path.exists():
        return [f"File not found: {submission_path}"], warnings

    try:
        sub = json.loads(submission_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON syntax: {exc}"], warnings

    if not isinstance(sub, dict):
        return ["Top-level JSON root must be an object/dict."], warnings

    for top_key in ("team_name", "chosen_architecture_paradigm", "scenarios"):
        if top_key not in sub:
            errors.append(f"Missing top-level key: '{top_key}'")

    if isinstance(sub.get("team_name"), str) and not sub["team_name"].strip():
        errors.append("'team_name' cannot be empty.")

    scenarios_list = sub.get("scenarios")
    if not isinstance(scenarios_list, list) or not scenarios_list:
        errors.append("'scenarios' must be a non-empty list of scenario diagnosis objects.")
        return errors, warnings

    expected_codes = {s["scenario_code"] for s in expected_scenarios}
    found_codes = set()

    known_case_prefixes: List[str] = []
    for c in dataset.get("raw_case_study_narratives", []):
        if "case_name" in c:
            full_pref = c["case_name"].split("(")[0].strip().lower()
            known_case_prefixes.append(full_pref)
            short_pref = (
                full_pref.replace(" group", "")
                .replace(" network", "")
                .replace(" retail", "")
                .strip()
            )
            if short_pref and len(short_pref) >= 4 and short_pref not in known_case_prefixes:
                known_case_prefixes.append(short_pref)

    for idx, item in enumerate(scenarios_list):
        if not isinstance(item, dict):
            errors.append(f"scenarios[{idx}] must be a dict.")
            continue

        sc_code = item.get("scenario_code")
        if not isinstance(sc_code, str) or not sc_code.strip():
            errors.append(f"scenarios[{idx}] is missing a valid 'scenario_code' string.")
            continue

        found_codes.add(sc_code)

        for req_key in REQUIRED_SCENARIO_OUTPUT_KEYS:
            if req_key == "scenario_code":
                continue
            if req_key not in item:
                errors.append(f"[{sc_code}] Missing required key: '{req_key}'")
            elif not isinstance(item[req_key], list):
                errors.append(f"[{sc_code}] Key '{req_key}' must be a list of strings (or structured objects).")
            else:
                invalid_entries = [x for x in item[req_key] if not isinstance(x, (str, dict))]
                if invalid_entries:
                    errors.append(f"[{sc_code}] All entries in '{req_key}' must be strings or structured dicts.")

        for opt_key in OPTIONAL_SCENARIO_ENRICHMENT_KEYS:
            if opt_key in item and item[opt_key] is not None:
                if not isinstance(item[opt_key], (list, dict, str)):
                    errors.append(f"[{sc_code}] Optional key '{opt_key}' must be a list, dict, or string if provided.")

        # Helpful structural sanity warnings (flexible & open to focused/original plans)
        if isinstance(item.get("diagnosed_root_causes"), list) and len(item["diagnosed_root_causes"]) == 0:
            warnings.append(f"[{sc_code}] 'diagnosed_root_causes' is empty.")
        if isinstance(item.get("diagnosed_root_causes"), list) and len(item["diagnosed_root_causes"]) > 6:
            warnings.append(
                f"[{sc_code}] {len(item['diagnosed_root_causes'])} root causes listed — watch out for false-positive keyword stuffing!"
            )

        p1 = item.get("phase_1_actions", []) if isinstance(item.get("phase_1_actions"), list) else []
        p2 = item.get("phase_2_actions", []) if isinstance(item.get("phase_2_actions"), list) else []
        p3 = item.get("phase_3_actions", []) if isinstance(item.get("phase_3_actions"), list) else []
        if len(p1) + len(p2) + len(p3) == 0:
            warnings.append(f"[{sc_code}] No actions provided across phase_1_actions, phase_2_actions, or phase_3_actions.")
        elif len(p1) > 0 and len(p2) == 0 and len(p3) == 0:
            warnings.append(
                f"[{sc_code}] All actions are placed into 'phase_1_actions' with empty Phase 2 & Phase 3 — check prerequisite sequencing!"
            )

        mcs = item.get("matched_case_studies", [])
        if isinstance(mcs, list):
            if len(mcs) == 0:
                warnings.append(f"[{sc_code}] 'matched_case_studies' is empty.")
            elif len(mcs) > 5:
                warnings.append(
                    f"[{sc_code}] {len(mcs)} case studies returned — aim for the Top 3 strongest precedents to avoid false-positive penalties!"
                )
            for cs_entry in mcs:
                cs_str = (
                    " ".join(str(v) for v in cs_entry.values() if v is not None)
                    if isinstance(cs_entry, dict)
                    else (cs_entry if isinstance(cs_entry, str) else "")
                )
                if cs_str:
                    low = cs_str.lower()
                    if not any(pref in low for pref in known_case_prefixes):
                        warnings.append(
                            f"[{sc_code}] Case study '{cs_str}' did not match any of the 21 sandbox case study names."
                        )

    missing_codes = expected_codes - found_codes
    if missing_codes:
        errors.append(f"Missing required scenario_code(s): {sorted(missing_codes)}")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingaze Hackathon Starter CLI: Inspect Data, Run Naive Baseline, Validate Submission JSON."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH, help="Path to sandbox JSON dataset.")
    parser.add_argument(
        "--extra-scenario",
        "--blind-scenario",
        dest="extra_scenario",
        type=Path,
        default=None,
        help="Optional path to an extra custom company scenario JSON file for generalizability testing.",
    )
    parser.add_argument("--inspect", action="store_true", help="Print a summary of the sandbox dataset & scenarios.")
    parser.add_argument(
        "--run-naive-baseline",
        action="store_true",
        help="Generate the Naive Flat Prompt baseline submission JSON.",
    )
    parser.add_argument(
        "--live-llm",
        action="store_true",
        help="With --run-naive-baseline, call a real single-prompt LLM using OPENAI_API_KEY / OPENROUTER_API_KEY / GEMINI_API_KEY.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("naive_baseline_output.json"),
        help="Output path for --run-naive-baseline.",
    )
    parser.add_argument(
        "--validate",
        type=Path,
        default=None,
        help="Validate a team submission JSON file against the required schema.",
    )

    args = parser.parse_args()
    if not (args.inspect or args.run_naive_baseline or args.validate):
        parser.print_help()
        sys.exit(0)

    dataset, scenarios = load_sandbox_and_scenarios(args.dataset, args.extra_scenario)

    if args.inspect:
        cmd_inspect(dataset, scenarios)

    if args.run_naive_baseline:
        baseline_obj = generate_naive_baseline(dataset, scenarios, live_llm=args.live_llm)
        args.out.write_text(json.dumps(baseline_obj, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] Wrote naive baseline submission ({len(scenarios)} scenarios) to: {args.out}")
        print("     Notice in CloudNova how the naive baseline falls for BOTH traps (Phase-1 Advocacy + Retail Shift Rotation)!")

    if args.validate is not None:
        errors, warnings = validate_submission(args.validate, dataset, scenarios)
        print("=" * 78)
        print(f"VALIDATION REPORT FOR: {args.validate}")
        print("=" * 78)
        for w in warnings:
            print(f"  [WARN]  {w}")
        if errors:
            for e in errors:
                print(f"  [ERROR] {e}")
            print("-" * 78)
            print(f"[FAIL] {len(errors)} schema error(s) found. Please fix before submitting!")
            sys.exit(1)
        print(f"[PASS] Schema valid! ({len(scenarios)} required scenarios verified, {len(warnings)} structural warning(s)).")


if __name__ == "__main__":
    main()
