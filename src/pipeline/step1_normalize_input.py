"""
Module: step1_normalize_input.py
Stage: Step 1 — Input Normalization & Noise Gate
Execution Type: AI

Description:
    Ingests a raw incoming client scenario (`ingaze_platform_signals`,
    `client_internal_context`, company metadata, and optional T0 telemetry
    snapshot) and runs a structured AI extraction + noise-gate pass to strip
    contaminated/unverified rows, map varied phrasing onto canonical `SignalCode`
    tags, and extract healthy baselines ("do not touch"), cohort/site asymmetries,
    and leadership requests.

Input:
    - raw_bundle (RawScenarioBundle): Raw client scenario dict + optional T0
      `TelemetrySnapshot` and `SectorPeerBenchmarks` from `database_loader.py`.
    - llm_client (StructuredLLMClient): Deterministic structured LLM wrapper (`temperature=0`).

Output:
    - normalized_input (NormalizedClientInput): Clean, noise-filtered canonical
      client representation passed to Step 2 (`step2_root_cause_analysis.py`),
      Step 4 (`step4_guardrail_check.py`), and Step 6 (`step6_hr_proposal.py`).

TODO:
    1. Implement the Noise Gate (`filter_contaminated_signals`) to detect and isolate
       unverified, cross-industry, or external-pilot rows in raw review exports into
       `filtered_noise_items` instead of emitting them as active `canonical_signals`.
    2. Prompt `llm_client.generate_structured(..., response_model=NormalizedClientInput)`
       to normalize phrasing variations (e.g., "6-month churn" vs. "early first-year
       turnover") strictly onto canonical `SignalCode`, `SectorCategory`,
       `WorkforceArchetype`, and `ActionCategory` enums.
    3. Explicitly preserve `healthy_baselines`, `cohort_site_asymmetries`, and
       `leadership_requests` (treated as untrusted hypotheses, NOT blind commands),
       and never branch on company names or scenario codes.
"""

from __future__ import annotations

from typing import List, Tuple

from src.schemas.pipeline_models import (
    ExtractedSignal,
    FilteredNoiseItem,
    NormalizedClientInput,
    RawScenarioBundle,
)
from src.utils.llm_client import StructuredLLMClient


def filter_contaminated_signals(
    raw_bundle: RawScenarioBundle,
    extracted_signals: List[ExtractedSignal],
    llm_client: StructuredLLMClient,
) -> Tuple[List[ExtractedSignal], List[FilteredNoiseItem]]:
    """
    Noise Gate: separate valid client-scoped signals from contaminated, unverified,
    or cross-industry export artifacts (e.g., external merchant pilot rows in a
    digital workplace export).
    """
    # TODO: 1. Inspect `raw_bundle.raw_scenario["ingaze_platform_signals"]` for unverified /
    #          out-of-scope / cross-sector mentions inconsistent with client industry & workforce.
    # TODO: 2. Move noisy items into `FilteredNoiseItem` with explicit `reason_filtered`.
    # TODO: 3. Return `(clean_signals, filtered_noise_items)` so Step 2 never sees noise
    #          while Step 4/Step 6 can still report the blocked trap transparently.
    raise NotImplementedError("TODO: Implement Step 1 Noise Gate (filter_contaminated_signals)")


def normalize_client_input(
    raw_bundle: RawScenarioBundle,
    llm_client: StructuredLLMClient,
) -> NormalizedClientInput:
    """
    Step 1 entrypoint: convert raw client scenario + optional T0 telemetry into
    a noise-filtered, canonically tagged `NormalizedClientInput`.
    """
    # TODO: 1. Build structured system + user prompts providing all canonical Enum vocabularies
    #          (`SignalCode`, `SectorCategory`, `WorkforceArchetype`, `ActionCategory`).
    # TODO: 2. Extract company profile, outside-in signals, inside-out healthy baselines,
    #          cohort/site asymmetries, CFO constraints, and leadership requests.
    # TODO: 3. Run `filter_contaminated_signals(...)` and attach `raw_bundle.t0_telemetry`
    #          and `raw_bundle.sector_benchmarks` onto the returned `NormalizedClientInput`.
    raise NotImplementedError("TODO: Implement Step 1 (normalize_client_input)")
