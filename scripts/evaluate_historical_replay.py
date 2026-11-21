"""Replay each historical intake with that company withheld from precedent retrieval."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.step2_root_cause_analysis import DEFAULT_ANALYTICS, load_analytics, load_graph
from recommendation_engine import DEFAULT_DATA, plan


def replay(dataset, analytics, graph):
    cases = dataset["raw_case_study_narratives"]
    results = []
    for case in cases:
        name = case["case_name"]
        historical = analytics["cases"].get(name, {})
        # Only starting inputs can enter the synthetic client packet. Holding
        # out the case also excludes its outcome and intervention from retrieval.
        scenario = {
            "scenario_code": name,
            "industry": case["sector_and_profile"],
            "ingaze_platform_signals": {"starting_conditions": case["initial_challenge"]},
            "analytics": {
                key: historical[key] for key in (
                    "t0_before_intervention", "sector_peer_benchmarks", "headcount", "locations_count",
                    "sector_benchmark_group",
                ) if key in historical
            },
        }
        training = {**dataset, "raw_case_study_narratives": [item for item in cases if item["case_name"] != name]}
        available = {"cases": {key: row for key, row in analytics["cases"].items() if key != name}}
        output, trace = plan(scenario, training, graph=graph, analytics=available)
        precedents = [match["case"] for match in output["matched_case_studies"]]
        if name in precedents:
            raise AssertionError(f"Held-out company appeared in precedent retrieval: {name}")
        results.append({
            "held_out_case": name,
            "precedents": precedents,
            "hypothesis_status_counts": dict(Counter(row["status"] for row in trace["diagnostic_hypotheses"])),
            "pilot_rules": [item["rule"] for item in output["phase_2_actions"]],
            "phase_one_actions": len(output["phase_1_actions"]),
        })
    return {
        "method": "Fixed-catalog replay using intake narrative and T0 only. Hold out each company and its outcomes from its own precedent search.",
        "limitation": "Synthetic historical cases and no independently labeled diagnostic answers. This checks retrieval leakage and execution, with no diagnostic accuracy estimate.",
        "case_count": len(results),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--analytics", type=Path, default=DEFAULT_ANALYTICS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8-sig"))
    report = replay(dataset, load_analytics(args.analytics), load_graph())
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Replayed {report['case_count']} held-out companies.")


if __name__ == "__main__":
    main()

