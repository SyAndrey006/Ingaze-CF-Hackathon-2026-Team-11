"""
Module: database_loader.py
Stage: Offline / Data Loading
Execution Type: Formula

Description:
    Deterministically loads and validates `data/normalized/normalized_rules.json`
    and `data/normalized/normalized_cases.json` into strongly typed Pydantic
    objects (`NormalizedRulesDB`, `NormalizedCasesDB`). Also loads active client
    scenarios paired 1:1 with their optional T0 telemetry snapshots into
    `RawScenarioBundle` objects for the online pipeline.

Input:
    - rules_path (Path): Path to `data/normalized/normalized_rules.json`.
    - cases_path (Path): Path to `data/normalized/normalized_cases.json`.
    - sandbox_dataset_path (Path): Path to `data/ingaze_sandbox_dataset.json`.
    - snapshots_dataset_path (Optional[Path]): Path to `data/ingaze_synthetic_analytics_snapshots.json`.
    - extra_scenario_path (Optional[Path]): Optional extra/blind judge scenario JSON path.

Output:
    - rules_db (NormalizedRulesDB): Validated universal HR rules consumed by Steps 2, 3, 4, 5.
    - cases_db (NormalizedCasesDB): Validated 11 normalized historical cases consumed by Step 3.
    - scenario_bundles (List[RawScenarioBundle]): Raw client scenarios + T0 snapshots consumed by Step 1.

TODO:
    1. Implement JSON file reading + Pydantic `model_validate_json` with clear error
       messages when placeholder JSON files have not been populated yet.
    2. Implement 1:1 join between `company_scenarios_to_diagnose` and
       `active_scenario_analytics_snapshots` using `scenario_code` (gracefully handle
       blind judge scenarios that may not have a matching telemetry snapshot).
    3. Support loading `--extra-scenario` / `--blind-scenario` JSON files identically
       to `starter_baseline_and_validator.py` for live Sunday Q&A testing.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from src.schemas.domain_models import NormalizedCasesDB, NormalizedRulesDB
from src.schemas.pipeline_models import RawScenarioBundle


def load_normalized_rules(rules_path: Path) -> NormalizedRulesDB:
    """
    Load and validate `normalized_rules.json` into a typed `NormalizedRulesDB`.
    """
    # TODO: 1. Check file existence and parse JSON via `NormalizedRulesDB.model_validate_json(...)`.
    # TODO: 2. Validate that rule lists are non-empty (fail fast if still placeholder template).
    # TODO: 3. Verify scoring weights sum to ~1.0 and all referenced snippet_nos exist.
    raise NotImplementedError("TODO: Implement load_normalized_rules")


def load_normalized_cases(cases_path: Path) -> NormalizedCasesDB:
    """
    Load and validate `normalized_cases.json` into a typed `NormalizedCasesDB`.
    """
    cases_path = Path(cases_path)
    if not cases_path.exists():
        raise FileNotFoundError(
            f"Normalized cases DB not found: {cases_path}. "
            "Build it with `python -m src.offline.case_normalizer`."
        )
    db = NormalizedCasesDB.model_validate_json(cases_path.read_text(encoding="utf-8"))
    if not db.cases:
        raise ValueError(
            f"{cases_path} contains no cases (still a placeholder?). "
            "Build it with `python -m src.offline.case_normalizer`."
        )
    for field in ("case_id", "case_name"):
        values = [getattr(case, field) for case in db.cases]
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise ValueError(f"{cases_path}: duplicate {field} values: {duplicates}")
    return db


def load_normalized_databases(
    rules_path: Path,
    cases_path: Path,
) -> Tuple[NormalizedRulesDB, NormalizedCasesDB]:
    """
    Convenience loader returning `(NormalizedRulesDB, NormalizedCasesDB)` together.
    """
    # TODO: 1. Delegate to `load_normalized_rules(rules_path)` and `load_normalized_cases(cases_path)`.
    # TODO: 2. Perform cross-database referential integrity checks (e.g., valid research snippet refs).
    raise NotImplementedError("TODO: Implement load_normalized_databases")


def load_raw_scenario_bundles(
    sandbox_dataset_path: Path,
    snapshots_dataset_path: Optional[Path] = None,
    extra_scenario_path: Optional[Path] = None,
) -> List[RawScenarioBundle]:
    """
    Load active company scenarios from `ingaze_sandbox_dataset.json` (plus any
    optional blind/extra scenario file) and join 1:1 with T0 telemetry snapshots
    from `ingaze_synthetic_analytics_snapshots.json` via `scenario_code`.
    """
    # TODO: 1. Read `company_scenarios_to_diagnose` from `sandbox_dataset_path`.
    # TODO: 2. Optionally append `extra_scenario_path` (supporting `blind_judge_scenario` wrapper).
    # TODO: 3. Index `active_scenario_analytics_snapshots` by `scenario_code` and parse
    #          `t0_current_snapshot` -> `TelemetrySnapshot` and `sector_peer_benchmarks` -> `SectorPeerBenchmarks`.
    # TODO: 4. Gracefully leave `t0_telemetry=None` if a brand-new blind scenario has no snapshot.
    raise NotImplementedError("TODO: Implement load_raw_scenario_bundles")
