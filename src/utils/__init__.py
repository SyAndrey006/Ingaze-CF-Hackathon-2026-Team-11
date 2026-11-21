"""
Module: __init__.py
Stage: Utilities Package
Execution Type: Utility

Description:
    Exposes shared infrastructure utilities: the structured LLM client wrapper
    (`llm_client.py`) used strictly by AI stages (Offline Indexing, Step 1,
    Step 6) and the deterministic post-generation verifier & reasoning trace
    builder (`verifier.py`).

Input:
    - Utility exports from `llm_client.py` and `verifier.py`.

Output:
    - `StructuredLLMClient`, `LLMConfig`, `verify_scenario_submission`, and
      `build_reasoning_trace` imported across `src/offline/*`, `src/pipeline/*`, and `src/main.py`.

TODO:
    1. Keep LLM client strictly isolated to Offline Indexing, Step 1, and Step 6
       (never import `llm_client` inside Formula Steps 2, 3, 4, or 5).
    2. Keep verifier 100% deterministic so every generated `submission.json` is auditable.
    3. Add structured logging or trace export helpers if needed for the live demo.
"""

from src.utils.llm_client import LLMConfig, StructuredLLMClient
from src.utils.verifier import build_reasoning_trace, verify_scenario_submission

__all__ = [
    "LLMConfig",
    "StructuredLLMClient",
    "build_reasoning_trace",
    "verify_scenario_submission",
]
