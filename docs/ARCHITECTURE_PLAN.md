# Team 11 Evidence Based Recommendation Architecture

**Status** Proposed eight-hour implementation. The current prototype is documented in [ARCHITECTURE.md](ARCHITECTURE.md).

**Product decision.** Build a diagnostic workflow for an Ingaze consultant reviewing one client intake. It should answer which cohort has a problem, which mechanism best explains it, what would distinguish it from alternatives, and what can safely be piloted. Prioritize four reusable paths that cover the mechanisms in the judging scenarios. This is a coverage choice for the prototype. The sandbox cannot estimate their prevalence across employers.

**Engineering decision.** Extend the existing offline Python engine with typed observations, a small evidence-backed rule catalog and a comparable-baseline matcher. Agree on the interfaces first so three people can build against the same fixtures. The CLI remains the demo surface.

## 1. Domain Representation and State Design

### 1.1 Data contract

| Object | Required fields and behavior |
| --- | --- |
| `Scope` | `role_family`, `site_or_site_group`, `tenure_band`. Unknown stays unknown. Company-wide is an explicit scope. Maintain separate protected scopes for healthy cohorts. |
| `Observation` | `id`, `condition_or_metric`, `scope`, `value`, `unit`, `window`, `definition_id`, `sample_count`, `snapshot`, `source_ref`, `status`. Metric definitions include the numerator and denominator population. A missing count stays null. Status is observed, contradicted, unknown, or quarantined. |
| `ClientState` | Scoped observations, protected scopes, workforce profile, headcount, number of locations, leadership requests and client constraints. Advocacy records participation, formal program status and measurement capability independently. Each field can be unknown. |
| `MechanismRule` | `id`, symptom indicators, required direct evidence, contradictory indicators, alternatives, verification test, eligible pilot, scale gate and evidence IDs. Rules consume normalized observations and never use client identifiers. |
| `Hypothesis` | `mechanism_id`, `scope`, `status` (supported, plausible, unresolved), supporting and contradictory observation IDs, one discriminating question, proposed test. The status is a decision label, with no probability or claim of proof. |
| `Action` | `hypothesis_id`, `scope`, `phase`, `owner_role`, `prerequisites`, `outcome_metric`, `guard_metric`, and `decision` (propose, conditional, defer, exclude). Pilot-specific targets and review dates belong in the plan as proposed parameters. |
| `PrecedentMatch` | Case key, shared mechanisms, matched scopes and metrics, differences in delivery context, observed follow-up, transfer category, and reason. |
| `EvidenceRecord` | Source link, study design, setting and population, measured outcome, result, applicability, limitations. Keep external research, sandbox reference snippets and synthetic case outcomes identifiable in the trace. |

The cohort is the unit of diagnosis. A company-wide average can provide context for a scoped diagnosis. It cannot establish that the affected group shares the same condition. An approval request is independent of the evidence used to diagnose a problem.

### 1.2 Reusable diagnostic paths

| Path | Evidence that activates it and what to rule out | Phase 1 → Phase 2 → Phase 3 |
| --- | --- | --- |
| **Expectation drift and early exits** | Early exits or hiring deterioration plus a documented gap between recruitment claims and the same cohort’s experience. Look for manager-specific patterns, job or onboarding changes, and pay concerns before assigning a driver. Clear messaging alone cannot resolve actual loss of autonomy. | Compare job promises with onboarding and exit evidence → pilot an accurate role preview and repair verified management or progression problems in the affected teams → expand accurate messaging after employees confirm the practices and matched-window results support expansion. |
| **Manager support, onboarding or workload** | Treat management, role clarity and workload as distinct candidate causes. Seek direct evidence such as uncoached leads and concentrated exits, inconsistent role expectations, or sustained overload corroborated by schedules or pulse feedback. Check exits by tenure, team and voluntary status. | Compare affected and healthy teams and ask what changed → pilot the improvement tied to the evidence, such as delegation coaching, an onboarding plan or workload redesign → expand the intervention after the measured mechanism and a retention indicator improve. |
| **Application or handoff friction** | Find where a particular role, device or site loses candidates. Compare application starts with submissions and later funnel steps. Compare mobile and desktop for the same roles where available. Check applicant mix, platform tracking, minimum qualifications and delays after application. | Instrument step-level events and reproduce the friction → pilot an accessible mobile form with essential early questions, or a recruiter handoff if the blockage occurs after submission → expand when qualified completion or response improves and eligibility, accessibility and recruiter workload hold. |
| **Fragmented feedback or tracking with an existing advocacy base** | Confirm manual effort, inconsistent coverage or low feedback collection, poor handoff visibility and the current program stage. Healthy advocacy plus weak tracking points to a measurement problem. Posting volume alone leaves participation, program maturity and readiness unresolved. | Inventory feedback invitations, review coverage, volunteer participation and tracking effort → pilot a short feedback survey with reminders and an accountable local owner, or instrument the existing advocacy cohort → consider expansion after data quality, voluntary participation and outcome measurement pass, with internal trust verified in the target group. |

Research for these paths supports interventions worth testing. A meta-analytic path analysis linked realistic previews to voluntary turnover primarily through perceived honesty. Newcomer research links role clarity and adjustment to work outcomes. A retail field trial tested manager-level retention goals. A controlled-study meta-analysis found a small reduction in exhaustion from organizational interventions, with very low certainty. These findings do not supply a transferable coaching, career framework or retention effect for the client. [Earnest et al.](https://doi.org/10.1111/j.1744-6570.2011.01230.x) · [Bauer et al.](https://pubmed.ncbi.nlm.nih.gov/17484552/) · [Friebel et al.](https://doi.org/10.1287/mnsc.2020.3905) · [Bes et al.](https://doi.org/10.1007/s00420-023-02009-z) · [WHO workplace mental health guidelines](https://www.who.int/publications/i/item/9789240053052)

Application simplification is supported by vendor observations about completion and by W3C form design guidance. Applicant reaction research links favorable selection perceptions to favorable views and reported intentions. A Cochrane review supports testing short questionnaires and electronic reminders in applicable settings. Recruitment vignettes found that the messenger and disclosed incentives affected perceived employer attractiveness. The evidence warrants testing a local design, with actual qualified completions, response coverage and attributable outcomes as measures. [Appcast observations](https://www.appcast.io/high-volume-recruiting-strategy/) · [W3C forms guidance](https://www.w3.org/WAI/tutorials/forms/) · [Hausknecht et al.](https://doi.org/10.1111/j.1744-6570.2004.00003.x) · [Edwards et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC10687884/) · [Van Hoye et al.](https://doi.org/10.1111/ijsa.12128)

## 2. Client Intake Parsing Normalization and Noise Filtering

1. Read the core sandbox, optional analytics and curated evidence. Join historical analytics by exact `case_name` and client analytics by exact `scenario_code`. Treat duplicate joins or invalid telemetry as input errors surfaced in the trace. Missing optional records fall back to narrative evidence. [Upstream telemetry dictionary](https://github.com/guglielmo-Ingaze/Ingaze-CF-Hackathon-2026/blob/main/docs/ANALYTICS_TELEMETRY_DICTIONARY.md)
2. Map raw phrases to canonical conditions while preserving scope, windows, polarity and source paths. Six-month cohort attrition and first-year attrition share a turnover concept and retain different metric definitions. An application-start abandonment rate uses a different denominator from applications per visit.
3. Validate percentages, stars, counts, and time windows against metric definitions. Calculate a peer gap only for like metrics and express it in the original unit, with polarity. For EuroFreight the telemetry reports 63% application form drop-off against 41.2% for its sector, a 21.8 percentage-point gap. Check the event definition in the applicant tracking system before choosing a pilot KPI. Use peer gaps as context about severity. [Upstream analytics](https://github.com/guglielmo-Ingaze/Ingaze-CF-Hackathon-2026/blob/main/database/ingaze_synthetic_analytics_snapshots.json)
4. Deduplicate observations that report the same fact, including a narrative repeating a platform metric. Quarantine out-of-scope imports. Surface disagreements and keep unknowns visible. Capture review counts and corroborate themes with employee listening or operational records before attributing causes. Voluntary employer reviews are susceptible to selection bias. [Marinescu et al.](https://www.nber.org/system/files/working_papers/w24372/w24372.pdf)

**Minimum telemetry integration.** Implement headcount, locations, first-year attrition, claims gap, form drop-off and smartphone share first. Use only values whose scope and meaning are known. Keep a source pointer for each normalized value. Add the remaining telemetry fields after the demo works.

## 3. Diagnostic Prioritization and Action Planning

### 3.1 Decide what the intake supports

Run the rules per cohort. Emit a supported hypothesis when there is direct mechanism evidence plus a consistent outcome in the same scope, no material unresolved contradiction, and an observable test. A symptom alone is plausible and calls for Phase 1 evidence collection. Conflicting or missing evidence yields an unresolved result with the next best question. A supported hypothesis can justify a scoped, reversible pilot. Prioritize the hypotheses by client impact, strength of local evidence, and whether the next step is feasible within the client’s budget and capacity.

Apply policy gates before rendering actions. Protect healthy cohorts. During an active expectation gap, credible workload concern or unresolved readiness in the target cohort, defer external advocacy and keep independent diagnostic or operational work moving. For fit, check the actual workforce, workflow and decision owner. Phase 3 actions are conditional on explicit pilot success, stable guard metrics and any required approval. An executive request can trigger evaluation but cannot satisfy a prerequisite.

**Example trace for the CTO.** A frontline intake reports a desktop-style form and unusually high application abandonment. That supports application friction as a hypothesis. Slow recruiter response may also explain the time-to-hire increase, so the next check splits time spent before submission from time spent waiting for first contact. If the mobile audit confirms form friction, propose a frontline pilot. Track qualified submissions per application start and time to first contact. Preserve the working HQ funnel. If applicants are completing the form and waiting for replies, route the pilot to the recruiter handoff instead.

### 3.2 Retrieve comparable precedents and explain the limits

- Compare the client intake with historical **T0** only. First rank by shared supported mechanism, then workforce and affected cohort, then compatible metric gaps and advocacy maturity. Use headcount ratio, location count and rollout scope as soft qualifiers. Surface a disagreement in any dimension and report missing information as unknown. The ordering is an explainable prototype heuristic.
- Treat metric comparability as a separate decision. Check concept, cohort, observation window, denominator definition and units. Keep counts and measurement uncertainty visible. For example, CloudNova’s six-month Milan and Berlin new-hire attrition cannot be compared directly with first-year attrition. A relevant case can still suggest which action to test. [Upstream telemetry dictionary](https://github.com/guglielmo-Ingaze/Ingaze-CF-Hackathon-2026/blob/main/docs/ANALYTICS_TELEMETRY_DICTIONARY.md)
- Export exactly three ranked sandbox precedents. Mark weak or incomplete matches as context only. For each, state the historically observed outcome, the part of the intervention that transfers, and limits on comparing the number. Use historical T1 only after selection, and label these before-and-after changes as synthetic historical observations. For client pilots, prefer a randomized or phased comparison where feasible, or use a comparison cohort and account for trends and concurrent changes. Differences in effect modifiers can limit generalization even from a randomized study. [Dahabreh et al.](https://pubmed.ncbi.nlm.nih.gov/32253789/) · [Lopez Bernal et al.](https://doi.org/10.1093/ije/dyw098)

### 3.3 Edge cases and additional evidence-backed constraints

| Edge case | Handling and evidence |
| --- | --- |
| Healthy average hides a struggling site or a changing hiring mix drives the trend | Inspect within-cohort trends and sample counts. Flag scope mismatches and ask whether the role mix, calendar period, or exposure window changed. Avoid treating a segment association as causal without checking the underlying mechanism. [Hernán et al.](https://doi.org/10.1093/ije/dyr041) |
| Company-wide competitive pay masks a local fairness problem | Preserve existing pay policy while testing compensation as an alternative if comparable roles or teams show discrepancies. A retail quasi-experiment connected unequal raises with quits in that setting. [Dube et al.](https://doi.org/10.1257/aer.20160232) |
| Schedule instability or remote-work mismatch mimics generic burnout | Route documented shift instability to a scheduling review. The Gap field experiment tested a package of scheduling changes and reported productivity and sales outcomes. For remote-capable roles only, hybrid work is a candidate for local testing when commute or flexibility is evidenced. A technology-firm trial found lower attrition under its tested schedule. [Kesavan et al.](https://doi.org/10.1287/mnsc.2021.4291) · [Bloom et al.](https://pubmed.ncbi.nlm.nih.gov/38867040/) |
| Completion improves while applicant quality or accessibility declines | Retain qualification checks and track qualified completions alongside overall completion. Verify labels, instructions and errors on the device and assistive technologies used by applicants. A pilot with worse access or qualified completion goes back for redesign. [W3C forms guidance](https://www.w3.org/WAI/tutorials/forms/) |
| Advocacy reach grows while business value is uncertain | Track relevant audience reach, qualified applications or referrals, and verified staff time separately. If a CFO requests a paid-media equivalency figure, ask for the required methodology and label it as an estimated media cost equivalent. AMEC advises against using advertising value equivalents to evaluate communications impact. [AMEC Barcelona Principles 4.0](https://amecorg.com/wp-content/uploads/2025/06/Barcelona-Principles-V4.0-Ebook-FINAL-Compressed.pdf) |

### 3.4 Organizer requirements and claims for Team 11 review

**Implement the organizer’s constraints.** Use one general Python pipeline for three active scenarios, show the three-phase plan and trace, preserve healthy cohorts, enforce workforce fit and advocacy readiness, cite sandbox research, include three sandbox precedents, compare with the baseline, and validate `submission.json`. The optional synthetic file can strengthen the diagnosis. These are rubric and product choices. [Challenge brief](https://github.com/guglielmo-Ingaze/Ingaze-CF-Hackathon-2026/blob/main/docs/CHALLENGE_BRIEF.md) · [Output contract and rubric](https://github.com/guglielmo-Ingaze/Ingaze-CF-Hackathon-2026/blob/main/docs/OUTPUT_CONTRACT_AND_RUBRIC.md)

**Retain supported directions at the level of the evidence.** Investigate a mismatch between hiring promises and experience. Inspect the apply flow before redesign. Corroborate workforce concerns and test scoped structural changes. Treat credibility and genuine employee participation as relevant to advocacy. These directions trigger investigation or a pilot, with pilot results determining expansion.

**Flag for your decision.** The core JSON gives source labels and findings for snippets 1–10 without enough bibliographic detail to verify the exact claims. The outside sources reviewed support some underlying mechanisms and use different settings, interventions or outcomes. Keep these figures visible as supplied references pending your decision and leave them out of numerical triggers, forecasts and ROI claims. [Sandbox research snippets](https://github.com/guglielmo-Ingaze/Ingaze-CF-Hackathon-2026/blob/main/database/ingaze_sandbox_dataset.json)

| Snippets | Claims requiring a decision |
| --- | --- |
| 1, 4 | A universal claims-gap cutoff and its churn or offer effects, shares of financial risk attributed to management and career clarity, and a fixed coaching-related attrition reduction. The companion dictionary’s severe-gap marker also differs from snippet 1’s threshold. |
| 2, 6, 7 | Four-screen or 60-second thresholds, fixed mobile conversion gains, fixed LinkedIn lifts, role-wide channel assumptions and a universal callback target. Use client funnel and role evidence to choose a pilot. |
| 3, 5, 8 | Universal engagement multipliers and time savings, a fixed 60-day advocacy backlash claim, and the CFO budget-rejection percentage. Continue to enforce the challenge’s advocacy gate as a policy. |
| 9, 10 | A fixed Gen-Z response lift or 14-day discovery promise, and a fixed attrition reduction from a retail scheduling and coaching package. |

## 4. Tech Stack and Production Trade Offs

| Layer | Eight-hour implementation |
| --- | --- |
| Intake and state | Existing Python CLI, dataclasses or typed dictionaries, JSON files, validated metric definitions and named fixture inputs. |
| Reasoning | Declarative mechanism rules with scope and provenance, explicit prerequisites, and a weighted or ordered baseline matcher. Reuse the existing policy and evidence modules where possible. |
| Evidence and output | Existing local evidence catalog, allow-listed rule references, structured reasons in the trace, and official submission validator. |
| Validation | Offline baseline comparison, behavioral checks with single-input changes, a deterministic rerun and a short recording fallback. |

Phrase matching gives reproducible extraction but can miss language outside the sandbox. Structured telemetry reduces the number of facts that depend on text extraction. The rule catalog can grow without adding company-specific logic. Unlike the flat baseline, the proposed trace can show exactly which observation triggers a condition, which prerequisite fails, and which outcome is comparable. Measure those differences in the demo before claiming improved performance.

| Time | Owner A · intake and precedent matching | Owner B · diagnosis and planning | Owner C · integration and demo |
| --- | --- | --- | --- |
| 0–0.5 h | Agree on fields, join rules and one fixture | Agree on rule inputs and action structure | Lock rubric checks and expected demo behavior |
| 0.5–3.5 h | Normalize intake and minimal telemetry, implement T0 matching | Implement four scoped paths and action gates against fixtures | Wire the pipeline to the CLI and prepare baseline and validator runs |
| 3.5–5.5 h | Integrate and inspect peer gaps and match reasons | Tune evidence conflicts and fallback questions | Run all three scenarios and compare each guardrail with the baseline |
| 5.5–7 h | Check unknown or incompatible metrics and scale sensitivity | Check missing telemetry and one input change that alters a decision | Finalize architecture against actual code, regenerate and validate submission |
| 7–8 h | Review match explanations and figures | Review plan and readiness gates | Rehearse, record fallback, and prepare submission |

**Acceptance checks.** CloudNova preserves healthy teams and defers advocacy on evidence from the affected teams. EuroFreight keeps the HQ channel, audits the frontline funnel and holds rollout until pilot evidence supports it. VerdeCare preserves existing voluntary advocacy and addresses measurement and candidate handoffs. Adding a scoped burnout signal changes the advocacy decision. Removing mobile friction evidence cancels the mobile redesign recommendation or returns it to discovery. Renaming a client does not change reasoning. Missing telemetry and incomparable windows remain inspectable. The three outputs pass the official validator and explain their advantage over the baseline in the live walkthrough.

Change one historical T1 outcome in a fixture and verify that case order stays fixed. Only the outcome reported for that case should change.
