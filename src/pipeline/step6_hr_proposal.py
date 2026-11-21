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


def assemble_recommendation(scenario, graph, diagnosis_state, scored_state, guardrail_state, phase_state):
    """Assemble the final deterministic response from the verified stage outputs."""
    result = {
        "scenario_code": scenario["scenario_code"],
        "diagnosed_root_causes": phase_state["diagnosed_root_causes"],
        "blocked_traps_and_guardrails": guardrail_state["guards"],
        "phase_1_actions": phase_state["phase_1_actions"],
        "phase_2_actions": phase_state["phase_2_actions"],
        "phase_3_actions": phase_state["phase_3_actions"],
        "matched_case_studies": scored_state["matched_case_studies"],
        "supporting_research_snippets": scored_state["supporting_research_snippets"],
        "strategic_focus_and_do_not_touch": (
            [phase_state["strengths"]] if phase_state["strengths"] else []
        ),
        "cohort_specific_strategies": (
            [phase_state["cohort"]] if phase_state["cohort"] else []
        ),
        "open_questions_and_hypotheses_for_client": (
            phase_state["open_questions_and_hypotheses_for_client"]
        ),
    }
    trace = {
        "scenario_code": scenario["scenario_code"],
        "profile": diagnosis_state["profile"],
        "excluded_noise": diagnosis_state["intake"]["excluded"],
        "diagnostic_hypotheses": diagnosis_state["diagnostic_hypotheses"],
        "diagnostic_observations": diagnosis_state["intake"]["observations"],
        "normalized_measurements": diagnosis_state["intake"]["measurements"],
        "action_decisions": guardrail_state["decisions"],
        "guardrails": guardrail_state["guards"],
        "protected_scopes": guardrail_state["protected"],
        "case_ranking": scored_state["matched_case_studies"],
        "candidate_action_scores": scored_state["ranked_candidates"],
        "normalized_case_matches": scored_state.get("normalized_case_matches", []),
        "case_informed_action_candidates": scored_state.get(
            "case_informed_action_candidates", []
        ),
        "mandatory_constraint_source": graph["sources"]["ingaze_policy"]["url"],
        "protected_baselines": diagnosis_state["intake"]["protected_baselines"],
        "research": scored_state["supporting_research_snippets"],
        "advocacy_ready_for_pilot": guardrail_state["advocacy_ready"],
        "advocacy_blockers": guardrail_state["blockers"],
        "operational_assumptions": [
            "Peer-gap margins prioritize review and have no statistical or causal interpretation.",
            "A conditional pilot requires verification and Phase 3 requires evaluated results.",
            "Historical ranking weights are retrieval heuristics. T1 is displayed after ranking.",
        ],
        "evidence": {
            signal: [
                row["source_ref"]
                for row in guardrail_state["present"]
                if row["signal"] == signal
            ]
            for signal in sorted(guardrail_state["features"])
        },
    }
    return result, trace


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
