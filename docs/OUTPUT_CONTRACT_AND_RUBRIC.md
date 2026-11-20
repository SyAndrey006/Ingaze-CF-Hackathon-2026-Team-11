# Output Contract, Generalizability & Evaluation Rubric

This document specifies the exact JSON format expected from your working Proof-of-Concept and how submissions are scored during Sunday Pre-Finals (`09:30–10:30`).

---

## 1. Schema-Agnostic `submission.json` Contract

Your **internal** data representation, reasoning structure, or pipeline state is **100% up to your team** (relational tables, scoring matrices, agentic pipelines, rule/constraint engines, case-based rankers, or graphs are all equally welcome!).  
However, so we can evaluate all teams consistently across the 3 company scenarios (`SCENARIO_A_CLOUDNOVA_FINTECH`, `SCENARIO_B_EUROFREIGHT_LOGISTICS`, `SCENARIO_C_VERDECARE_BCORP`), commit a `submission.json` file in the root of your team's GitHub repository following this exact format:

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
        "Plain-English description of wrong-industry solutions or premature executive requests blocked/deferred by your system (and why)"
      ],
      "phase_1_actions": [
        "Phase 1: Foundational diagnostics, listening surveys, audits, and persona calibrations"
      ],
      "phase_2_actions": [
        "Phase 2: Core structural, management, portal, EVP, and CFO dashboard interventions"
      ],
      "phase_3_actions": [
        "Phase 3: Downstream scaling & amplification unlocked after Phase 2 foundations"
      ],
      "matched_case_studies": [
        "Top 3 matched Case Studies from the 11-case sandbox library + quantified ROI precedent"
      ],
      "supporting_research_snippets": [
        "Cited empirical research snippets from the sandbox backing your plan"
      ]
    }
  ]
}
```

### Mini-Example of Expected Output Granularity (Toy Case — NOT One of the 3 Test Scenarios)

To illustrate the expected level of concreteness (and show how a **physical retail** profile dynamically *activates* store shift rotation while *blocking* B2B LinkedIn engineering blogs), here is a sample scenario object for an illustrative toy company (`EXAMPLE_ONLY_BAKERY_RETAIL` — a 40-shop regional bakery chain with mobile portal friction and weekend shift burnout):

```json
{
  "scenario_code": "EXAMPLE_ONLY_BAKERY_RETAIL",
  "diagnosed_root_causes": [
    "Mobile application friction caused by a desktop-heavy registration form",
    "Weak store-manager support and unpredictable weekend shift burnout"
  ],
  "blocked_traps_and_guardrails": [
    "Blocked Technical Engineering Storytelling on LinkedIn — ineffective primary channel for frontline shop staff who apply via smartphones"
  ],
  "phase_1_actions": [
    "Career Portal UX Audit to pinpoint mobile drop-off steps",
    "360-Degree Internal Feedback Listening across store teams",
    "Candidate Persona Calibration for frontline shop staff"
  ],
  "phase_2_actions": [
    "Mobile-First Fast-Apply Flow (<60s smartphone application)",
    "Predictable Retail Store Weekend Shift Rotation to reduce shift burnout",
    "Manager Coaching Program for shop supervisors"
  ],
  "phase_3_actions": [
    "Persona-Aligned Job Descriptions highlighting reliable schedules"
  ],
  "matched_case_studies": [
    "Gamma Retail (-19% 6-month store turnover, +28% mobile conversion)",
    "BellaModa Retail (+31% mobile conversion, -16% early store attrition)",
    "Global Retail Group (+22% conversion, -35% mobile abandonment)"
  ],
  "supporting_research_snippets": [
    "Snippet 2: >58% mobile abandonment on multi-screen desktop forms; 60s fast-apply cuts bounce by 30-35%",
    "Snippet 10: Predictable weekend shift rotation + store-manager coaching cuts 6-month store attrition by 15-22%"
  ]
}
```

### Reference HR Intervention Vocabulary (15 Generic Archetypes — Alphabetical)

Your system does **not** need exact wording matches (natural phrasing variations and synonyms are completely fine), as long as recommendations stay **concrete** rather than vague (e.g., avoid generic lines like *"Improve HR digital strategy"*). For reference, here are the **15 recurring concrete HR interventions** appearing across the sandbox case studies (listed alphabetically, without phase ordering or sector rules):

- `360-Degree Internal Feedback Listening`
- `Automated Ambassador Content Tracking`
- `Board Financial Risk & ROI Dashboard`
- `Candidate Persona Calibration`
- `Career Portal UX Audit`
- `Data-Driven Ambassador Selection`
- `EVP Realignment`
- `Manager Coaching Program`
- `Mobile-First Fast-Apply Flow`
- `Multi-Channel Reputation Audit`
- `Persona-Aligned Job Descriptions`
- `Post-Interview & Career Day Gen-Z Surveys`
- `Predictable Retail Store Weekend Shift Rotation`
- `Technical Engineering Storytelling on LinkedIn`
- `Transparent Career Progression Framework`

### Always Validate Before Pushing!
Run the zero-dependency validator included in the root of this repo:

```bash
python starter_baseline_and_validator.py --validate submission.json
```

### Precision, Domain Modeling & Generalizability Rules
1. **Domain Modeling vs. Hardcoding (Important Distinction!):**
   - **Allowed & Encouraged:** Modeling **general HR domain knowledge** (symptom $\rightarrow$ root-cause links, phase prerequisites, sector/workforce compatibility, and intervention catalog) in declarative files (`YAML`, `JSON`, `SQLite`, rules, graphs, or structured prompts) that are 100% independent of company names.
   - **Strictly Forbidden (Hardcoding):** Any company-specific `if/else` logic (`if company == "CloudNova"`) or pre-baked answers tied to the 3 test scenarios. During Sunday live Q&A, we may tweak one input symptom live to verify your system adapts dynamically!
2. **Avoid Keyword Stuffing:**
   - **Do NOT dump all possible HR problems** into `diagnosed_root_causes`—false-positive root causes are penalized.
   - **Do NOT dump all 11 Case Studies** into `matched_case_studies`—select the **Top 3** most structurally relevant precedents for that company's sector, workforce, and problem profile.
   - **Do NOT dump all actions into `phase_1_actions`**—respect diagnostic and cultural prerequisites across Phase 1 $\rightarrow$ Phase 2 $\rightarrow$ Phase 3.

---

## 2. Official Pre-Finals & Finals Judging Rubric (100 Points)

During Sunday Pre-Finals (`09:30–10:30`), each team presents its architecture and live demo, and we select **1 winning team** from the Ingaze track to advance to the Campus Founders Main Stage (`10:30–11:30`):

| Criterion | Weight | What Earns Top Marks |
| :--- | :---: | :--- |
| **1. Problem Fit & Value** | **25%** | Pinpoints true cross-pillar root causes (vs. surface symptoms), enforces 100% of industry/workforce guardrails, and grounds recommendations in CFO-credible Case Study ROI. |
| **2. Technical Execution & PoC** | **30%** | Working live Python execution across the scenarios (using generalizable domain logic), valid 3-phase prerequisite sequencing, and clear outperformance vs. the naive flat-prompt baseline. |
| **3. Innovation & Approach** | **20%** | Clarity, formal rigor, and creativity of your domain representation, reasoning/planning mechanics, and reliability & validation controls in `ARCHITECTURE.md`. |
| **4. Feasibility & Scalability** | **15%** | Smart engineering trade-offs (latency, LLM token cost, determinism, maintainability) that could realistically scale to hundreds of enterprise case studies and thousands of domain records. |
| **5. Pitch & Demo Delivery** | **10%** | Crisp problem-to-proof storytelling + **50% Live Demo Rule** (show real execution & inspectable reasoning traces; keep a 30-sec screen recording ready as Wi-Fi fallback). |
