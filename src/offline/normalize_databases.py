
Description:
    Reads raw HR domain materials (4 pillars, 6 cross-pillar field notes, 10
    empirical research studies, telemetry dictionary) and 11 historical B2B case
    studies (+ T0/T1 analytics snapshots) from `data/`, then invokes a structured
    LLM normalizer (`llm_client.py`) to build two separate local JSON databases:
    `data/normalized/normalized_rules.json` and `data/normalized/normalized_cases.json`.

Input:
    - sandbox_dataset_path (Path): Path to `data/ingaze_sandbox_dataset.json`.
    - snapshots_dataset_path (Optional[Path]): Path to `data/ingaze_synthetic_analytics_snapshots.json`.
    - llm_client (StructuredLLMClient): Thin structured LLM wrapper (`temperature=0`).

Output:
    - normalized_rules (NormalizedRulesDB): Written to `data/normalized/normalized_rules.json`
      and loaded by Steps 2, 3, 4, and 5.
    - normalized_cases (NormalizedCasesDB): Written to `data/normalized/normalized_cases.json`
      and loaded by Step 3 for candidate ideas and Top-3 precedent matching.

TODO:
    1. Parse the 4 pillars, 6 `raw_cross_pillar_rules_to_structure`, and 10
       `raw_empirical_research_snippets` into universal symptom-to-root-cause rules,
       metric thresholds, scoring conditions/weights, guardrail rules, and phase
       sequencing rules (`NormalizedRulesDB`).
    2. Join each of the 11 `raw_case_study_narratives` 1:1 via `case_name` with its
       `case_study_analytics_snapshots` record (`sector_peer_benchmarks`, `t0_before_intervention`,
       `t1_after_12_months`) and normalize into `NormalizedCasesDB`.
    3. Anti-hardcoding check: NEVER read `company_scenarios_to_diagnose` or
       `active_scenario_analytics_snapshots` during offline normalization—only
       general HR domain knowledge and historical completed cases may enter the DBs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.schemas.domain_models import NormalizedCasesDB, NormalizedRulesDB
from src.utils.llm_client import StructuredLLMClient


def build_normalized_rules(
    raw_sandbox_data: Dict[str, Any],
    llm_client: StructuredLLMClient,
    telemetry_dictionary_path: Optional[Path] = None,
) -> NormalizedRulesDB:
    """
    Use structured AI extraction to convert the 4 pillars, 6 cross-pillar field notes,
    10 empirical research snippets, and telemetry dictionary into `NormalizedRulesDB`.
    """
    # TODO: 1. Extract only `domain_pillars_and_causal_dynamics` and `raw_empirical_research_snippets`.
    # TODO: 2. Prompt `llm_client.generate_structured(..., response_model=NormalizedRulesDB)` with
    #          strict canonical enum lists (`SignalCode`, `ActionCategory`, `WorkforceArchetype`, `SectorCategory`).
    # TODO: 3. Verify zero scenario names or active client company names leaked into generated rules.
    raise NotImplementedError("TODO: Implement AI normalization for normalized_rules.json")


def build_normalized_cases(
    raw_sandbox_data: Dict[str, Any],
    raw_snapshots_data: Optional[Dict[str, Any]],
    llm_client: Optional[StructuredLLMClient] = None,
    curation_path: Optional[Path] = None,
) -> NormalizedCasesDB:
    """
    Join curated historical B2B case study narratives with optional T0->T1 analytics
    snapshots via exact `case_name` join key and normalize into `NormalizedCasesDB`.

    LLM-assisted mappings are maintained separately in `database/curation/`; this
    build step is deterministic and verifies the curation before producing records.
    """
    from src.offline.case_normalizer import DEFAULT_CURATION, build_cases_db

    del llm_client  # LLM drafting is offline; reviewed curation is deterministic at build time.
    curation_file = Path(curation_path) if curation_path else DEFAULT_CURATION
    curation = json.loads(curation_file.read_text(encoding="utf-8"))
    return build_cases_db(raw_sandbox_data, raw_snapshots_data, curation)


def run_offline_normalization(
    sandbox_dataset_path: Path,
    snapshots_dataset_path: Optional[Path],
    output_rules_path: Path,
    output_cases_path: Path,
    llm_client: StructuredLLMClient,
    telemetry_dictionary_path: Optional[Path] = None,
) -> Tuple[NormalizedRulesDB, NormalizedCasesDB]:
    """
    Orchestrate one-time offline indexing and persist `normalized_rules.json` and
    `normalized_cases.json` atomically to `data/normalized/`.
    """
    # TODO: 1. Read raw JSON inputs (without modifying starter files).
    # TODO: 2. Call `build_normalized_rules(...)` and `build_normalized_cases(...)`.
    # TODO: 3. Validate both Pydantic DBs, serialize with `model_dump_json(indent=2)`,
    #          and write to `output_rules_path` and `output_cases_path`.
    raise NotImplementedError("TODO: Implement end-to-end offline database normalization runner")
