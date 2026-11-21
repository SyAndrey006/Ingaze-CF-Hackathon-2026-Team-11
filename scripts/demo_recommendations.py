"""Compare the engine with the offline baseline and demonstrate a readiness change."""

import json
from copy import deepcopy

from src.reasoning.hr_intake import load_analytics
from recommendation_engine import DEFAULT_DATA, plan
from starter_baseline_and_validator import generate_naive_baseline


def main():
    dataset = json.loads(DEFAULT_DATA.read_text(encoding="utf-8"))
    analytics = load_analytics()
    scenarios = dataset["company_scenarios_to_diagnose"]
    baseline = generate_naive_baseline(dataset, scenarios)
    for scenario, naive in zip(scenarios, baseline["scenarios"]):
        result, trace = plan(scenario, dataset, analytics=analytics)
        print(f"\n{scenario['company_name']}")
        print("Baseline Phase 1:")
        for action in naive["phase_1_actions"]:
            print(f"  - {action}")
        print("Engine guardrails:")
        for guard in result["blocked_traps_and_guardrails"]:
            print(f"  - {guard}")
        print("Engine case precedents:")
        for case in trace["case_ranking"]:
            print(f"  - {case['case']} ({case['score']}) | {case['historical_roi']}")

    healthy = next(
        scenario for scenario in scenarios if plan(scenario, dataset, analytics=analytics)[1]["advocacy_ready_for_pilot"]
    )
    changed = deepcopy(healthy)
    changed["client_internal_context"]["cohort_and_site_asymmetries"] += (
        " Recent confidential interviews report severe workload burnout in the target cohort."
    )
    original, before = plan(healthy, dataset, analytics=analytics)
    revised, after = plan(changed, dataset, analytics=analytics)
    assert before["advocacy_ready_for_pilot"] and not after["advocacy_ready_for_pilot"]
    assert "burnout" in after["advocacy_blockers"]
    assert original["phase_3_actions"] != revised["phase_3_actions"]
    print(f"\nLive input change for {healthy['company_name']}")
    print("  Original advocacy pilot ready:", before["advocacy_ready_for_pilot"])
    print("  After new workload evidence:", after["advocacy_ready_for_pilot"])
    print("  Blocking evidence:", after["evidence"]["burnout"])
    print("  Revised decision:", next(guard for guard in revised["blocked_traps_and_guardrails"] if guard.startswith("Defer external advocacy")))


if __name__ == "__main__":
    main()
