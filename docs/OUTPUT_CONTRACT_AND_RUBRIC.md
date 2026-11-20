# Output Contract, Generalizability & Evaluation Rubric

This document specifies the JSON format expected from your working Proof-of-Concept and how submissions are evaluated during Sunday Pre-Finals (`09:30–10:30`).

---

## 1. Schema-Agnostic `submission.json` Contract

Your **internal** data representation, reasoning structure, or pipeline state is **100% up to your team** (relational tables, scoring matrices, agentic pipelines, rule/constraint engines, case-based rankers, or graphs are all equally welcome!).  
So we can evaluate all teams consistently across the 3 company scenarios (`SCENARIO_A_CLOUDNOVA_FINTECH`, `SCENARIO_B_EUROFREIGHT_LOGISTICS`, `SCENARIO_C_VERDECARE_BCORP`), commit a `submission.json` file in the root of your team's GitHub repository following this structure:

```json
{
  "team_name": "Team 10 — Fanatic",
  "chosen_architecture_paradigm": "One-line summary of your chosen architecture and stack",
  "scenarios": [
    {
      "scenario_code": "SCENARIO_A_CLOUDNOVA_FINTECH",
      "diagnosed_root_causes": [
        "Plain-English description of each inferred underlying root cause across the 4 pillars"
      ],
      "blocked_traps_and_guardrails": [
        "Plain-English description of wrong-industry solutions, premature executive requests, or redundant interventions blocked/deferred by your system (and why)"
      ],
      "phase_1_actions": [
        "Phase 1: Foundational diagnostics, audits, listening, or immediate low-risk quick wins"
      ],
      "phase_2_actions": [
        "Phase 2: Core structural, management, portal, governance, or cohort-specific interventions"
      ],
      "phase_3_actions": [
        "Phase 3: Downstream scaling & amplification unlocked once core foundations are in place"
      ],
      "matched_case_studies": [
        "Top 3 matched Case Studies from the 11-case sandbox library + quantified ROI precedent"
      ],
      "supporting_research_snippets": [
        "Cited empirical research snippets from the sandbox backing your plan"
      ],
      "strategic_focus_and_do_not_touch": [
        "(Optional) Healthy baselines, high-performing cohorts, or existing assets your strategy deliberately preserves without over-fixing"
      ],
      "cohort_specific_strategies": [
        "(Optional) Differentiated actions tailored to specific hubs, facilities, or workforce subpopulations"
      ],
      "open_questions_and_hypotheses_for_client": [
        "(Optional) Key unknowns, hypotheses, or HRIS/ATS data checks your system would verify with the client"
      ]
    }
  ]
}
```

> [!TIP]
> **Backward-Compatible & Open to Original Thinking:**
> - The first 8 keys (`scenario_code` through `supporting_research_snippets`) are the **required core keys** checked by `starter_baseline_and_validator.py --validate`.
> - The 3 enrichment keys (`strategic_focus_and_do_not_touch`, `cohort_specific_strategies`, `open_questions_and_hypotheses_for_client`) are **optional** (you can either include them as separate lists or weave those insights directly into your `blocked_traps_and_guardrails` and `phase_1/2/3_actions` strings).

---

## 2. Open Recommendations: Why There Is NO Closed Action Vocabulary

In real enterprise consulting, **there is no fixed 15-item menu of HR interventions**.  
While the 11 historical Case Studies illustrate proven interventions (such as reputation audits, 360° listening, persona calibration, mobile fast-apply flows, manager coaching, career frameworks, CFO risk dashboards, and ambassador automation), **your system is NOT restricted to a closed vocabulary of pre-labeled actions**:

1. **Concrete Precedent Actions + Original Recommendations:** Your engine should combine relevant evidence-backed interventions from the domain corpus with **original, non-obvious, context-specific recommendations** tailored to the client's specific bottlenecks.
2. **Strategic Restraint (*What to Do vs. What NOT to Touch*):** A great strategy engine knows when **not** to intervene. If a client's compensation is already at the 82nd percentile, if one hub has 94% retention, or if their B-Corp EVP is already authentic with active organic ambassadors, explicitly state what you are *preserving* and why you are skipping redundant corporate overhauls.
3. **Cohort & Site Differentiation:** Avoid one-size-fits-all corporate blanket programs when the data shows sharp asymmetries between hubs, regional facilities, or workforce segments (e.g., tenured vs. newly hired cohorts, HQ analysts vs. frontline operators, R&D labs vs. regional clinics).
4. **Client Discovery & Hypotheses:** Real client intake data is never 100% complete. Surfacing sharp hypotheses and concrete verification questions for the client's leadership/HRIS team earns high marks during Sunday judging.

### Mini-Example of Output Granularity (Toy Case — NOT One of the 3 Test Scenarios)

Here is a sample scenario object for an illustrative toy company (`EXAMPLE_ONLY_BAKERY_RETAIL` — a 40-shop regional bakery chain where artisan bakers have 95% retention, but frontline counter staff face mobile portal drop-off and weekend shift burnout):

```json
{
  "scenario_code": "EXAMPLE_ONLY_BAKERY_RETAIL",
  "diagnosed_root_causes": [
    "Mobile application friction caused by a 5-screen desktop registration form for smartphone applicants",
    "Weak shop-supervisor support and unpredictable weekend shift scheduling driving frontline counter-staff burnout"
  ],
  "blocked_traps_and_guardrails": [
    "Blocked B2B Technical Engineering Storytelling on LinkedIn — mismatched channel for frontline counter staff who apply via mobile",
    "Preserved artisan baker compensation & apprenticeship track (95% retention) — avoided a blanket company-wide EVP overhaul"
  ],
  "phase_1_actions": [
    "Career Portal UX Audit focused on the smartphone application funnel",
    "360-Degree Internal Feedback Listening targeted at high-churn store locations",
    "Candidate Persona Calibration for frontline bakery counter staff"
  ],
  "phase_2_actions": [
    "60-Second Mobile-First Fast-Apply Flow (no desktop account wall; WhatsApp/SMS interview slot confirmation)",
    "Predictable Retail Store Weekend Shift Rotation and supervisor coaching for store managers",
    "Peer buddy-pairing during the first 30 days in high-footfall city-center shops"
  ],
  "phase_3_actions": [
    "Persona-Aligned Job Descriptions highlighting predictable weekend rosters and local store stability"
  ],
  "matched_case_studies": [
    "Gamma Retail (-19% 6-month store turnover, +28% mobile conversion)",
    "BellaModa Retail (+31% mobile conversion, -16% early store attrition)",
    "Global Retail Group (+22% conversion, -35% mobile abandonment)"
  ],
  "supporting_research_snippets": [
    "Snippet 2: >58% mobile abandonment on multi-screen desktop forms; 60s fast-apply cuts bounce by 30-35%",
    "Snippet 10: Predictable weekend shift rotation + store-manager coaching cuts 6-month store attrition by 15-22%"
  ],
  "strategic_focus_and_do_not_touch": [
    "Do not disrupt the central artisan bakery production team (95% retention) or waste budget on a corporate-wide rebranding campaign"
  ],
  "cohort_specific_strategies": [
    "City-center flagship stores: prioritize weekend shift rotation and manager coaching; Suburban shops: focus on mobile fast-apply speed"
  ],
  "open_questions_and_hypotheses_for_client": [
    "Verify in store scheduling logs whether 6-month counter-staff exits cluster around specific store managers or consecutive Sunday shifts"
  ]
}
```

### Always Validate Before Pushing!
Run the zero-dependency validator included in the root of this repo:

```bash
python starter_baseline_and_validator.py --validate submission.json
```

### Precision, Domain Modeling & Generalizability Rules
1. **Domain Modeling vs. Hardcoding (Important Distinction!):**
   - **Allowed & Encouraged:** Modeling **general HR domain knowledge** (causal mechanisms, readiness prerequisites, workforce/channel fit, and precedent indexing) in declarative files (`YAML`, `JSON`, `SQLite`, rules, graphs, or structured agentic workflows) that are 100% independent of company names.
   - **Strictly Forbidden (Hardcoding):** Any company-specific `if/else` logic (`if company == "CloudNova"`) or pre-baked answers tied to the 3 test scenarios. During Sunday live Q&A, we may tweak one input signal live to verify your system adapts dynamically!
2. **Focus Over Keyword Stuffing:**
   - **Do NOT dump every conceivable HR problem** into `diagnosed_root_causes`—pinpoint the true underlying root causes supported by the scenario's platform signals and internal context.
   - **Do NOT dump all 11 Case Studies** into `matched_case_studies`—select the **Top 3** most structurally relevant precedents for that company's profile and bottlenecks.
   - **Do NOT dump every action into `phase_1_actions`**—sequence diagnostics, structural fixes, and scaling logically based on the company's actual readiness.

---

## 3. Official Pre-Finals & Finals Judging Rubric (100 Points)

During Sunday Pre-Finals (`09:30–10:30`), each team presents its architecture and live demo, and we select **1 winning team** from the Ingaze track to advance to the Campus Founders Main Stage (`10:30–11:30`):

| Criterion | Weight | What Earns Top Marks |
| :--- | :---: | :--- |
| **1. Problem Fit & Value** | **25%** | Pinpoints true cross-pillar root causes (vs. surface symptoms), demonstrates strategic focus (*what to fix vs. what healthy baselines not to touch*), blocks sector/cultural traps, and grounds ROI in CFO-credible precedents. |
| **2. Technical Execution & PoC** | **30%** | Working live Python execution across the scenarios (using generalizable domain logic), logical prerequisite sequencing, and clear outperformance vs. the flat-prompt baseline. |
| **3. Innovation & Approach** | **20%** | Originality, clarity, and rigor of your domain representation, reasoning mechanics, cohort-specific/non-obvious recommendations, and reliability controls in `ARCHITECTURE.md`. |
| **4. Feasibility & Scalability** | **15%** | Smart engineering trade-offs (latency, LLM token cost, determinism, maintainability) that could realistically scale to hundreds of enterprise case studies and client intakes. |
| **5. Pitch & Demo Delivery** | **10%** | Crisp problem-to-proof storytelling + **50% Live Demo Rule** (show real execution & inspectable reasoning traces; keep a 30-sec screen recording ready as Wi-Fi fallback). |
