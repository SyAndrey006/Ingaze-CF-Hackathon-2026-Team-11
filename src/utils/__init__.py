"""Shared structured-LLM and deterministic verification utilities.

``StructuredLLMClient`` serves the AI-enabled steps; the verifier builds typed
reasoning traces for tests and other consumers.
"""

from src.utils.llm_client import LLMConfig, StructuredLLMClient
from src.utils.verifier import build_reasoning_trace, verify_scenario_submission

__all__ = [
    "LLMConfig",
    "StructuredLLMClient",
    "build_reasoning_trace",
    "verify_scenario_submission",
]
