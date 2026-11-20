# Ingaze — Campus Founders AI Track Hackathon (20–22 Nov 2026)

> **Challenge:** *Architecting an AI Reasoning System for Cross-Pillar HR Strategy*  
> **Location:** GRAVITY Heilbronn | **Challenge Setter:** Ingaze (`ingaze.ai`) — Guglielmo Tornesi (CTO)

Welcome **Team 10 (Fanatic)**, **Team 11**, and **Team 12**!  
This repository contains the official sandbox dataset, zero-dependency baseline/validator CLI, and domain documentation for the Ingaze challenge.

---

## The Challenge in 30 Seconds

Enterprise HR problems across **Employer Reputation**, **Recruiting**, **Employee Advocacy**, and **Internal Retention** form strict causal chains, prerequisites, and sector constraints:
- **Why flat LLMs fail:** Ask a standard LLM or vector RAG pipeline whether a FinTech with `16%` 6-month engineer churn should launch a LinkedIn Employee Ambassador campaign next week (as the CEO requested), and it happily says *"Yes!"*—triggering public reputational backlash. It also leaks frontline retail or truck-driver interventions into B2B SaaS plans.
- **Your mission as Chief AI Architect:** You have **100% architectural freedom** (there is zero preferred paradigm!). Invent, formalize, and prove the best **representation & reasoning architecture** (*Relational Scoring Matrix, Agentic Planner-Verifier Pipeline, Programmatic Rule/Policy Engine, Case-Based Hybrid Ranker, or Graph/Network Representation*) in Python—and beat our naive LLM baseline across our **3 multi-pillar company scenarios** (using general domain logic, zero hardcoded company `if/else` rules!).

---

## 60-Second Quickstart (Zero Dependencies)

Requires only **Python 3.9+** (standard library only):

```bash
# 1. Inspect the 4 HR pillars, 6 domain field notes, 10 studies, 11 case studies & 3 scenarios
python starter_baseline_and_validator.py --inspect

# 2. Run the "Naive Flat Prompt" baseline to see the exact traps your system must beat
python starter_baseline_and_validator.py --run-naive-baseline --out naive_baseline_output.json

# 3. Validate your team's exported submission JSON before judging
python starter_baseline_and_validator.py --validate naive_baseline_output.json
```

> **Optional Live LLM Baseline (BYOK):** Set `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `GEMINI_API_KEY` and pass `--live-llm` to benchmark your architecture directly against a live single-prompt LLM call.

---

## Repository Map & Essential Docs

| File / Doc | Read Time | What You'll Find |
| :--- | :---: | :--- |
| **[`docs/HR_DOMAIN_PRIMER_FOR_ENGINEERS.md`](./docs/HR_DOMAIN_PRIMER_FOR_ENGINEERS.md)** | **5 min** | **Start here if HR is new to you!** Plain-English crash course on EVP, Say-Do Gap, CpH/TtH, EMV, Workforce Archetypes, Phase 1$\to$3 dependencies, and how CFOs think. |
| **[`docs/CHALLENGE_BRIEF.md`](./docs/CHALLENGE_BRIEF.md)** | **6 min** | Full problem statement, architectural freedom (100% open paradigm & stack), and realistic scope for a 3-person weekend sprint. |
| **[`docs/OUTPUT_CONTRACT_AND_RUBRIC.md`](./docs/OUTPUT_CONTRACT_AND_RUBRIC.md)** | **3 min** | Exact `submission.json` schema, anti-hardcoding rules, and the 100-point Campus Founders Jury Rubric. |
| **[`ARCHITECTURE_TEMPLATE.md`](./ARCHITECTURE_TEMPLATE.md)** | — | Copy to `ARCHITECTURE.md` and fill in your representation design, ingestion/validation controls, planning mechanism, and stack trade-offs. |
| **[`data/ingaze_sandbox_dataset.json`](./data/ingaze_sandbox_dataset.json)** | — | Schema-agnostic sandbox dataset: **4 Pillars**, **6 Cross-Pillar Field Notes**, **10 Empirical Research Studies**, **11 Anonymized B2B Case Studies**, and **3 Company Scenarios**. |
| **[`starter_baseline_and_validator.py`](./starter_baseline_and_validator.py)** | — | CLI dataset inspector, naive baseline runner, and `submission.json` validator. |

*(Note: While the intro slides mentioned 5 sample case studies, we included **11 anonymized B2B Case Studies** across overlapping industries so precedent retrieval requires real structural matching rather than a trivial 1-per-sector lookup.)*

---

## Definition of Success (3 Functional Benchmarks)

A winning weekend PoC clearly beats the naive baseline across **3 verifiable functional benchmarks**:

1. **Root-Cause Precision & `100%` Sector-Trap Immunity:** Across all 3 scenarios (`CloudNova Pay`, `EuroFreight Interport`, `VerdeCare Group`), distinguish underlying cross-pillar root causes from surface symptoms without false-positive keyword stuffing, and block every wrong-industry trap (e.g., no retail weekend shift rotation for a cloud FinTech; no LinkedIn engineering-blog strategy for commercial truck drivers).
2. **Prerequisite-Safe 3-Phase Sequencing & ROI Grounding:** Sequence actions strictly across `Phase 1 (Audits & Listening) -> Phase 2 (Core Structural Fixes) -> Phase 3 (Scaling & Advocacy)`—deferring premature advocacy when an internal Say-Do Gap/burnout blocker is active—and match the **Top-3** structurally relevant historical Case Studies with quantified ROI + empirical research citations.
3. **Reproducible Execution, Schema Validity & Zero Hardcoding:** Export a `submission.json` that passes `python starter_baseline_and_validator.py --validate submission.json` with `0` errors, runs live from general domain logic (zero `if company == "..."` rules), and adapts dynamically if a scenario trait is tweaked live during Sunday Q&A.

---

## What You Deliver on Sunday (`09:30` Pre-Finals)

Everything is self-contained in this repo—**no extra datasets or files to wait for during the weekend!** Before Sunday `09:30`, push to your team's GitHub repo:
1. **`ARCHITECTURE.md`** (based on `ARCHITECTURE_TEMPLATE.md`) — Formal representation design, ingestion & validation controls, diagnostic/3-phase sequencing mechanism, and stack justification.
2. **Working Python PoC + Live Demo** — Ingests `data/ingaze_sandbox_dataset.json`, outperforms the naive baseline on all 3 scenarios (`CloudNova Pay`, `EuroFreight Interport`, `VerdeCare Group`), and generalizes cleanly (during Q&A we may tweak a scenario trait live to verify zero hardcoded `if company == ...` rules!).
3. **Validated `submission.json`** — Committed in your repo root and passing:
   ```bash
   python starter_baseline_and_validator.py --validate submission.json
   ```
