# Engine vs. Naive Flat-Prompt Baseline

The organizer’s offline baseline simulates a single unstructured LLM prompt with scripted responses. Team 11 ran its deterministic engine in sandbox mode on the same three official scenarios. Both outputs passed the organizer’s validator with zero errors or warnings. The engine output matched the checked-in submission byte for byte. [Challenge brief](CHALLENGE_BRIEF.md) · [Submission](../submission.json)

## Summary

| Check | Naive baseline | Team 11 engine |
| --- | --- | --- |
| Explicit guardrail entries | 0 | 10, including blocks, deferrals and baseline protections |
| Diagnostic entries | 3 surface-symptom summaries | 16 evidence-linked hypotheses, 15 plausible and 1 conflicted |
| Healthy baselines named | 0 scenarios | All 3 scenarios |
| Historical case matches | 2 for CloudNova, 2 for EuroFreight, 1 for VerdeCare | 3 per scenario, with shared problem tags and historical outcomes |
| Client verification questions | 0 | 17 across the three scenarios |
| Scenarios with actions in all three phases | 1 of 3 | 3 of 3, with verification required before pilots and scale-up |

## Per-scenario results

### CloudNova Pay

| Check | Naive baseline | Team 11 engine |
| --- | --- | --- |
| Diagnosis | Low LinkedIn engagement and high six-month engineer turnover. | Tests whether expectation drift, management practices and onboarding clarity contribute to exits. Also investigates role information, manual reporting and agency dependence. |
| Action and guardrails | Launches an ambassador campaign next week and adopts retail shift rotation from the noisy review feed. | Defers public advocacy, excludes retail shift rotation and preserves 82nd-percentile compensation and the Amsterdam cohort’s 94% annual retention. |
| Precedents | Gamma Retail and FlowPay. | Alfa Group, KronoCart Tech and QuantEx Markets. Alfa reported 22% lower first-year engineering turnover and introduced ambassador selection after internal trust stabilized. |

### EuroFreight Interport

| Check | Naive baseline | Team 11 engine |
| --- | --- | --- |
| Diagnosis | High bounce and slow hiring. | Tests the reported mobile form obstacle and investigates recruiter handoff delays in Bologna and Naples separately. |
| Action and guardrails | Starts technical LinkedIn storytelling for drivers and deploys fast-apply before a portal audit. | Preserves the functioning HQ channel. Reproduces the suspected form obstacle by device before a pilot, then gates scale on qualified completion, eligibility and recruiter response. |
| Precedents | FlowPay and Beta Logistica. | Beta Logistica, TransEuropa Supply Chain and Meridian Express Logistics. Beta reported a fall in application abandonment from 58% to 29%. Meridian provides a cross-hub operations precedent. |

### VerdeCare Group

| Check | Naive baseline | Team 11 engine |
| --- | --- | --- |
| Diagnosis | Low social reach and fragmented spreadsheets. | Investigates regional clinic reputation, feedback coverage and interview handoffs. Flags conflicting evidence on role information for verification. |
| Action and guardrails | Switches on ambassador tracking across all locations before auditing or selecting participants. | Preserves the healthy employer proposition and gates wider automation on readiness, opt-in participation and reporting. The pilot cohort still needs confirmation. |
| Precedents | Alfa Group. | VitaCare Network, VerdiCraft Botanicals and NaturaPure Group. VitaCare reported 120 hours per year saved in manual review and spreadsheet work. |

## Interpretation and reproduction

The result demonstrates guardrail and sequencing behavior against the organizer’s scripted baseline. Live LLM and vector RAG comparisons remain untested. The engine’s diagnoses are provisional, and historical outcomes describe the individual precedents. [Sandbox scenarios and case studies](../database/ingaze_sandbox_dataset.json)

Run from the repository root.

```bash
comparison_dir=$(mktemp -d)
python3 starter_baseline_and_validator.py --run-naive-baseline --out "$comparison_dir/naive.json"
python3 recommendation_engine.py --sandbox --out "$comparison_dir/engine.json" --trace-out "$comparison_dir/trace.json"
python3 starter_baseline_and_validator.py --validate "$comparison_dir/naive.json"
python3 starter_baseline_and_validator.py --validate "$comparison_dir/engine.json"
```
