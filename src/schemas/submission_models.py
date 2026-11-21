"""Pydantic schema matching the official ``submission.json`` contract."""

from __future__ import annotations

from typing import Any, Dict, List, Union

from pydantic import BaseModel, Field


SubmissionEntry = Union[str, Dict[str, Any]]


class ScenarioSubmission(BaseModel):
    """
    Exact per-scenario output schema for `submission.json`.

    Contains the 8 required core keys plus the 3 optional enrichment keys
    documented in `docs/OUTPUT_CONTRACT_AND_RUBRIC.md`.
    """

    # --- 8 Required Core Keys ---
    scenario_code: str = Field(
        ...,
        min_length=1,
        description="Exact scenario_code from `company_scenarios_to_diagnose`.",
    )
    diagnosed_root_causes: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Plain-English inferred underlying root causes across the 4 HR pillars.",
    )
    blocked_traps_and_guardrails: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Blocked wrong-industry solutions, noisy traps, deferred executive requests, and why.",
    )
    phase_1_actions: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Phase 1: Foundational diagnostics, audits, listening, or immediate low-risk quick wins.",
    )
    phase_2_actions: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Phase 2: Core structural, management, portal, governance, or cohort-specific fixes.",
    )
    phase_3_actions: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Phase 3: Downstream scaling & amplification unlocked once core foundations are in place.",
    )
    matched_case_studies: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Top 3 matched historical Case Studies from the 11-case sandbox library + quantified ROI.",
    )
    supporting_research_snippets: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Cited empirical research snippets from the sandbox backing the diagnosis and roadmap.",
    )

    # --- 3 Optional Enrichment Keys ---
    strategic_focus_and_do_not_touch: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Healthy baselines, high-performing cohorts, or assets preserved without over-fixing.",
    )
    cohort_specific_strategies: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Differentiated actions tailored to specific hubs, facilities, or workforce segments.",
    )
    open_questions_and_hypotheses_for_client: List[SubmissionEntry] = Field(
        default_factory=list,
        description="Concrete unknowns, hypotheses, or HRIS/ATS data checks to verify with the client.",
    )


class SubmissionPayload(BaseModel):
    """Top-level root JSON contract written to `submission.json`."""

    team_name: str = Field(
        ...,
        min_length=1,
        description="Team identifier (e.g., 'Team 11 — Ingaze Strategy Engine').",
    )
    chosen_architecture_paradigm: str = Field(
        ...,
        min_length=1,
        description="Concise one-line summary of the hybrid deterministic + AI architecture and stack.",
    )
    scenarios: List[ScenarioSubmission] = Field(
        default_factory=list,
        description="Diagnosed roadmaps for all active company scenarios.",
    )
