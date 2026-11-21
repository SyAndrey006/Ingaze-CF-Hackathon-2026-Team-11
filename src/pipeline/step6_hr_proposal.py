"""
Module: step6_hr_proposal.py
Stage: Step 6 — Plain-English HR Proposal & Output Formatting
Execution Type: AI

Description:
    Translates the deterministically verified upstream decisions (`PhasePlan`,
    `GuardrailResult` blocked/do-not-touch/noise items, `DiagnosisResult`,
    Top-3 matched Case Studies, research snippets, and client hub/cohort context)
    into clear, jargon-free plain-English HR & CFO reasoning with expected % / EUR
    ROI and exports a validated `ScenarioSubmission` conforming to the hackathon
    `submission.json` contract (8 required core keys + 3 optional enrichment keys).

Input:
    - client_input (NormalizedClientInput): Client hubs, cohort asymmetries, and healthy baselines from Step 1.
    - diagnosis (DiagnosisResult): Verified root causes, locked healthy baselines, and open hypotheses from Step 2.
    - scored (ScoredCandidates): Top-3 matched Case Studies and supporting empirical snippets from Step 3.
    - guardrails (GuardrailResult): Blocked actions, do-not-touch items, paused rationales, and filtered noise traps from Step 4.
    - phase_plan (PhasePlan): Verified Phase 1, Phase 2, and Phase 3 actions from Step 5.
    - llm_client (StructuredLLMClient): Deterministic structured LLM wrapper (`temperature=0`).

Output:
    - scenario_submission (ScenarioSubmission): Exact 11-key scenario output
      (8 required + 3 optional) passed to `src/utils/verifier.py` and aggregated
      into `submission.json` by `src/main.py`.

TODO:
    1. Construct a strictly grounded prompt that forbids the LLM from inventing
       new phases, overriding any `BLOCKED`/`DO_NOT_TOUCH`/`PAUSE` decision, or
       citing case studies outside `scored.top_matched_cases`.
    2. Translate technical `SignalCode` / `ActionCategory` tokens into crisp,
       plain-English HR & CFO prose incorporating expected % / EUR ROI ranges
       grounded in `scored.top_matched_cases` and `scored.selected_research_snippets`.
    3. Populate all 8 required keys AND all 3 optional enrichment keys
       (`strategic_focus_and_do_not_touch`, `cohort_specific_strategies`,
       `open_questions_and_hypotheses_for_client`) so judges see focused, cohort-aware,
       CFO-ready recommendations.
"""

from __future__ import annotations

from src.schemas.pipeline_models import (
    DiagnosisResult,
    GuardrailResult,
    NormalizedClientInput,
    PhasePlan,
    ScoredCandidates,
)
from src.schemas.submission_models import ScenarioSubmission
from src.utils.llm_client import StructuredLLMClient


def generate_hr_proposal(
    client_input: NormalizedClientInput,
    diagnosis: DiagnosisResult,
    scored: ScoredCandidates,
    guardrails: GuardrailResult,
    phase_plan: PhasePlan,
    llm_client: StructuredLLMClient,
) -> ScenarioSubmission:
    """
    Step 6 entrypoint: render the verified deterministic plan, guardrails, Top-3
    precedent cases, and cohort context into a plain-English `ScenarioSubmission`.
    """
    # TODO: 1. Serialize verified inputs (`diagnosis`, `phase_plan`, `guardrails.blocked_actions`,
    #          `guardrails.do_not_touch_items`, `guardrails.filtered_noise_traps`,
    #          `scored.top_matched_cases`, `scored.selected_research_snippets`, and
    #          `client_input.cohort_site_asymmetries`) into a compact structured prompt.
    # TODO: 2. Call `llm_client.generate_structured(..., response_model=ScenarioSubmission)`
    #          with strict fidelity rules (do not drop/add actions across phases, preserve
    #          exact case study names, avoid buzzwords, cite concrete % / EUR ROI).
    # TODO: 3. Force `scenario_submission.scenario_code = client_input.scenario_code` and
    #          return the validated `ScenarioSubmission` for `verifier.py`.
    raise NotImplementedError("TODO: Implement Step 6 (generate_hr_proposal)")
