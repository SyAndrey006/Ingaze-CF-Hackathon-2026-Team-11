"""
Module: __init__.py
Stage: Package Root
Execution Type: Utility

Description:
    Marks `src` as the root Python package for the Ingaze HR Strategy
    Recommendation Engine. Exposes package-level metadata for the hybrid
    deterministic + AI pipeline.

Input:
    - None (package initialization module).

Output:
    - Package namespace (`src`) imported by offline, pipeline, schemas, and utils modules.

TODO:
    1. Keep package initialization lightweight and free of side effects.
    2. Optionally expose `__version__` or top-level pipeline entrypoint once implemented.
    3. Ensure no company-specific constants or hardcoded scenario names are ever placed here.
"""

__version__ = "0.1.0-scaffold"
