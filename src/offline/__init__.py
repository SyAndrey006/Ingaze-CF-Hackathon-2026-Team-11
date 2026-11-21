"""
Module: __init__.py
Stage: Offline Indexing Package
Execution Type: Utility

Description:
    Exposes offline indexing and database-loading helpers that transform raw
    sandbox domain files into normalized local JSON databases (`normalized_rules.json`
    and `normalized_cases.json`) and validate them into typed Pydantic objects.

Input:
    - Module exports from `normalize_databases.py` and `database_loader.py`.

Output:
    - Public offline indexing & loading functions imported by `src/main.py` and tests.

TODO:
    1. Keep re-exported function signatures aligned with `normalize_databases.py` and `database_loader.py`.
    2. Ensure offline indexing can be triggered standalone via CLI or lazily from `src/main.py`.
    3. Verify normalized JSON outputs contain zero company-scenario hardcoding.
"""

from src.offline.database_loader import (
    load_normalized_cases,
    load_normalized_databases,
    load_normalized_rules,
    load_raw_scenario_bundles,
)
from src.offline.normalize_databases import (
    build_normalized_cases,
    build_normalized_rules,
    run_offline_normalization,
)

__all__ = [
    "build_normalized_cases",
    "build_normalized_rules",
    "load_normalized_cases",
    "load_normalized_databases",
    "load_normalized_rules",
    "load_raw_scenario_bundles",
    "run_offline_normalization",
]
