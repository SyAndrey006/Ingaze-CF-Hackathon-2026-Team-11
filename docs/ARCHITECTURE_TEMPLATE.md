# Architecture & Reasoning Blueprint — [Your Team Name]

> **Instructions:** Copy or rename this file to `ARCHITECTURE.md`. Keep it concrete, crisp, and engineering-focused (schemas, state designs, algorithms, diagrams, and honest trade-offs beat long generic prose!). **Any architectural paradigm is welcome**—there is no secret "expected" paradigm.

- **Team Number & Name:** `Team [10 / 11 / 12] — [Name]`
- **Team Members:** `[Names]`
- **Chosen Paradigm & Stack (1 line):** *(e.g., Relational Scoring Matrix + Constraint Rules / Agentic Decomposition & Verifier Pipeline / Programmatic Policy Engine / Case-Based Hybrid Retrieval / Property Graph)*

---

## 1. Domain Representation & State Design

### 1.1 Core Data Models, Tables, Rules, or State Objects
*Define the exact data structures, tables, schemas, predicates, or state objects your system uses (paste a Mermaid diagram, Pydantic/SQL/JSON schema, or state specification).*

### 1.2 Representing Cross-Pillar Dynamics, Prerequisites & Sector Guardrails
- **Cross-Pillar Symptom $\rightarrow$ Root Cause Links:** *How does your representation trace surface symptoms back to underlying structural causes across the 4 HR pillars?*
- **Dependency Prerequisites (`Phase 1 -> Phase 2 -> Phase 3`):** *How does your design prevent a downstream intervention (e.g., Employee Advocacy) from being scheduled when an active blocker (e.g., Say-Do Gap or severe burnout) is present or when foundational diagnostics have not run yet?*
- **Industry & Workforce Guardrails:** *How do you prevent sector contamination (e.g., Retail vs. FinTech vs. Logistics) while dynamically activating context-appropriate interventions when the company profile calls for them?*
- **Evidence & Case Study Representation:** *How are the 10 empirical research benchmarks and 21 historical Case Studies indexed and linked to problems, interventions, and ROI metrics?*

---

## 2. Client Intake Parsing, Normalization & Noise Filtering

- **Context Organization Pipeline:** *How are an incoming client's messy situation (platform warning signals + internal notes) and the HR domain/case-study reference library transformed into your structured representation?*
- **Concept Normalization / Deduplication:** *How do you map surface phrasing variations (e.g., "6-month churn" vs. "early first-year turnover") to a consistent internal concept?*
- **Noise Filtering & Anti-Hallucination Controls:** *What validation checks, schema constraints, or review steps prevent noisy client exports (e.g., unrelated retail reviews inside a FinTech dump) or LLM extraction errors from triggering wrong recommendations?*

---

## 3. Diagnostic, Prioritization & Action-Planning Mechanism

*Walk through how your system processes an incoming Company Scenario (`ingaze_platform_signals` + `client_internal_context`) and generates its strategic plan (feel free to adapt the subsections to match your architecture):*
- **Cross-Pillar Root Cause Diagnosis & Healthy Baseline Preservation:** *How does your system separate true root causes from surface symptoms—and identify healthy metrics/cohorts that should NOT be disrupted?*
- **Guardrail Enforcement, Readiness & Sequencing:** *How does your system evaluate executive requests, respect diagnostic/cultural readiness across phases, and differentiate between cohorts or sites?*
- **Action Generation (Precedent-Backed + Original Recommendations) & ROI Grounding:** *How does your system combine proven case-study interventions with tailored/original recommendations, match the Top-3 Case Studies, and surface open discovery questions for the client?*

---

## 4. Tech Stack & Production Trade-Offs

| Layer | Chosen Tool / Library | Why We Picked It Over Alternatives |
| :--- | :--- | :--- |
| **Data / State Layer** | | |
| **Reasoning / Planning Layer** | | |
| **LLM / Parsing Layer** | | |
| **Validation / Testing** | | |

### Why Our Architecture Works Best:
1. **Compared to a Flat Single-Prompt LLM / Naive Vector RAG:** *(Cite concrete comparison examples from your runs!)*
2. **Compared to Alternative Paradigms We Considered:** *(Discuss engineering simplicity, determinism, LLM token cost, latency, and CFO auditability.)*