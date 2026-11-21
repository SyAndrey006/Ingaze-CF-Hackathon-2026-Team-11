# Ingaze — Campus Founders AI Track Hackathon (20–22 Nov 2026)

> **Challenge:** *Architecting an AI Reasoning System for Cross-Pillar HR Strategy*  
> **Location:** GRAVITY Heilbronn | **Challenge Setter:** Ingaze (`ingaze.ai`) — Guglielmo Tornesi (CTO)

Welcome **Team 10 (Fanatic)**, **Team 11**, and **Team 12**!  
This repository contains the official sandbox dataset, zero-dependency baseline/validator CLI, and domain documentation for the Ingaze challenge.

---

## The Challenge in 30 Seconds — Real Product Context

**Where Ingaze is today:** Ingaze helps enterprise HR teams build data-driven Employer Strategy across **Employer Reputation**, **Recruiting**, **Employee Advocacy**, and **Internal Retention**. Today, when a client (say *Company Alpha*) arrives, **our platform already surfaces the areas needing attention**, and the client shares internal context (surveys, turnover data, leadership priorities)—but **our human experts still read all of that and manually recommend the action plan**.

**What we want to automate (and why plain LLMs fail):** We want an **automated Action Recommendation Engine** where we feed a client's situation (our platform analysis + their internal info) into a structured system and get accurate, tailored action recommendations out. Plain LLMs fail here **because they lack structured context**:
- Ask a flat LLM whether a FinTech with `16%` 6-month engineer churn should launch a LinkedIn Employee Ambassador campaign next week (as the CEO requested), and it happily says *"Yes!"*—triggering public backlash. It also leaks frontline retail or truck-driver fixes into B2B SaaS plans.

**Your mission as Chief AI Architect (100% open paradigm & open recommendations):**
1. **Structure the Context:** Design the data & context architecture (*Relational Scoring Matrix, Agentic Planner-Verifier Pipeline, Programmatic Rule/Policy Engine, Case-Based Hybrid Ranker, or Graph/Network*—**zero preferred paradigm!**) that organizes both **our HR domain knowledge/case studies** and **an incoming client's dual situation** (`ingaze_platform_signals` + `client_internal_context`, including healthy baselines not to break, cohort asymmetries, and leadership requests).
2. **Recommend High-Leverage Actions:** Feed that organized context into a Python recommendation engine that diagnoses true root causes, decides both **what to prioritize and what healthy areas NOT to touch**, blocks wrong-industry/premature traps, sequences actions across phases, and proposes **concrete, cohort-aware, and original recommendations** (not restricted to a fixed menu of labels) across **3 realistic company scenarios** (zero hardcoded `if company == ...` rules!).

---

## 60-Second Quickstart (Zero Dependencies)

Requires only **Python 3.9+** (standard library only):

```bash
# 1. Inspect the 4 HR pillars, 6 domain field notes, 10 studies, 21 case studies & 3 scenarios
python starter_baseline_and_validator.py --inspect

# 2. Run the "Naive Flat Prompt" baseline to see the exact traps your system must beat
python starter_baseline_and_validator.py --run-naive-baseline --out naive_baseline_output.json

# 3. Validate your team's exported submission JSON before judging
python starter_baseline_and_validator.py --validate naive_baseline_output.json
```

> **Optional Live LLM Baseline (BYOK):** Set `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `GEMINI_API_KEY` and pass `--live-llm` to benchmark your architecture directly against a live single-prompt LLM call.

### Team 11 offline engine

Run from the repository root with Python 3.9 or later.

```bash
mkdir -p database/ingaze-knowledge-graph
python3 recommendation_engine.py --sandbox --out submissions/proposal.json \
  --proposal-out submissions/hr_proposal.md \
  --trace-out database/ingaze-knowledge-graph/diagnostic_report.json \
  --graph-out database/ingaze-knowledge-graph/graph.json
python3 starter_baseline_and_validator.py --validate submissions/proposal.json
python3 -m scripts.demo_recommendations
```

The active knowledge-graph orchestrator lives in `src/main.py` and calls the stages in `src/pipeline/`. The reusable modules under `src/reasoning/` provide policy, intake, evidence, and graph utilities; `recommendation_engine.py` is the public CLI and Python facade. Offline case preparation lives in `src/offline/`. The online pipeline requires Pydantic 2 and python-dotenv.

| Folder | Contents |
| --- | --- |
| `database/` | Sandbox datasets, normalized cases, knowledge assets, and retained Ingaze inspection datasets |
| `database/knowledge/` | Editable graph rules and research catalog |
| `data/` | Client input/output files and pipeline intermediate files |
| `scripts/` | Demo and historical replay commands |
| `database/ingaze-knowledge-graph/` | Graph exports, diagnostic traces, and historical replay |
| `database/ingaze-telemetry-excel/` | Existing telemetry spreadsheet |
| `database/ingaze_csv_exports/` | Existing CSV inspection exports and source note |
| `submissions/` | Official sandbox results: `proposal.json` and `hr_proposal.md` |

The generated sandbox deliverables are grouped in `submissions/`. [Architecture](ARCHITECTURE.md) · [Proposal JSON](submissions/proposal.json) · [HR proposal](submissions/hr_proposal.md)

---

## Repository Map & Essential Docs

| File / Doc | Read Time | What You'll Find |
| :--- | :---: | :--- |
| **[`docs/HR_DOMAIN_PRIMER_FOR_ENGINEERS.md`](./docs/HR_DOMAIN_PRIMER_FOR_ENGINEERS.md)** | **5 min** | **Start here if HR is new to you!** Plain-English crash course on EVP, Say-Do Gap, CpH/TtH, EMV, Workforce Archetypes, Phase 1$\to$3 dependencies, and how CFOs think. |
| **[`docs/CHALLENGE_BRIEF.md`](./docs/CHALLENGE_BRIEF.md)** | **6 min** | Full problem statement, architectural freedom (100% open paradigm & stack), and realistic scope for a 3-person weekend sprint. |
| **[`docs/OUTPUT_CONTRACT_AND_RUBRIC.md`](./docs/OUTPUT_CONTRACT_AND_RUBRIC.md)** | **3 min** | Exact `submission.json` schema, anti-hardcoding rules, and the 100-point Campus Founders Jury Rubric. |
| **[`docs/ANALYTICS_TELEMETRY_DICTIONARY.md`](./docs/ANALYTICS_TELEMETRY_DICTIONARY.md)** | **4 min** | **Data Guide ("What Is What"):** Field-by-field walkthrough of **both** JSON files (`ingaze_sandbox_dataset.json` + `ingaze_synthetic_analytics_snapshots.json`), how they link `1:1`, and all metric scales/polarities. |
| **[`ARCHITECTURE_TEMPLATE.md`](./ARCHITECTURE_TEMPLATE.md)** | — | Copy to `ARCHITECTURE.md` and fill in your representation design, context structuring & noise-filtering controls, planning mechanism, and stack trade-offs. |
| **[`database/ingaze_sandbox_dataset.json`](./database/ingaze_sandbox_dataset.json)** | — | Core sandbox dataset: **4 Pillars**, **6 Cross-Pillar Field Notes**, **10 Empirical Research Studies**, **21 Past B2B Case Studies**, and **3 Active Client Scenarios to Solve**. |
| **[`database/ingaze_synthetic_analytics_snapshots.json`](./database/ingaze_synthetic_analytics_snapshots.json)** | — | *(Optional)* Aggregated synthetic multi-channel telemetry & sector peer benchmarks (`T0 -> T1` for the 21 past cases + `T0` intake snapshot for the 3 active scenarios). |
| **[`starter_baseline_and_validator.py`](./starter_baseline_and_validator.py)** | — | CLI dataset inspector, naive baseline runner, and `submission.json` validator. |

*(Note: While the intro slides mentioned 5 sample case studies, we included **21 anonymized B2B Case Studies** across overlapping industries so precedent retrieval requires real structural matching rather than a trivial 1-per-sector lookup.)*

---

## Definition of Success (3 Functional Benchmarks)

A winning weekend PoC clearly beats the naive baseline across **3 verifiable functional benchmarks**:

1. **Root-Cause Precision & `100%` Sector-Trap Immunity:** Across all 3 scenarios (`CloudNova Pay`, `EuroFreight Interport`, `VerdeCare Group`), distinguish underlying cross-pillar root causes from surface symptoms without false-positive keyword stuffing, and block every wrong-industry trap (e.g., no retail weekend shift rotation for a cloud FinTech; no LinkedIn engineering-blog strategy for commercial truck drivers).
2. **Prerequisite-Safe 3-Phase Sequencing & ROI Grounding:** Sequence actions strictly across `Phase 1 (Audits & Listening) -> Phase 2 (Core Structural Fixes) -> Phase 3 (Scaling & Advocacy)`—deferring premature advocacy when an internal Say-Do Gap/burnout blocker is active—and match the **Top-3** structurally relevant historical Case Studies with quantified ROI + empirical research citations.
3. **Reproducible Execution, Schema Validity & Zero Hardcoding:** Export `submissions/proposal.json` that passes `python starter_baseline_and_validator.py --validate submissions/proposal.json` with `0` errors, runs live from general domain logic (zero `if company == "..."` rules), and adapts dynamically if a scenario trait is tweaked live during Sunday Q&A.

---

## What You Deliver on Sunday (`09:30` Pre-Finals)

Everything is self-contained in this repo—**no extra datasets or files to wait for during the weekend!** Before Sunday `09:30`, push to your team's GitHub repo:
1. **`ARCHITECTURE.md`** (based on `ARCHITECTURE_TEMPLATE.md`) — Formal representation design, context structuring & noise-filtering controls, diagnostic/3-phase sequencing mechanism, and stack justification.
2. **Working Python PoC + Live Demo** — Ingests `database/ingaze_sandbox_dataset.json`, outperforms the naive baseline on all 3 scenarios (`CloudNova Pay`, `EuroFreight Interport`, `VerdeCare Group`), and generalizes cleanly (during Q&A we may tweak a scenario trait live to verify zero hardcoded `if company == ...` rules!).
3. **Validated `submissions/proposal.json`** — Passing:
   ```bash
   python starter_baseline_and_validator.py --validate submissions/proposal.json
   ```
