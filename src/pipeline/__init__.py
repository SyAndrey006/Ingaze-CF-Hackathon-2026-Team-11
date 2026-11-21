"""
Module: __init__.py
Stage: Online Per-Client Pipeline Package (Steps 1-6)
Execution Type: Utility

Description:
    Exposes the six sequential stage entrypoints of the online per-client HR
    strategy pipeline: Step 1 (AI Input Normalization + Noise Gate), Steps 2-5
    (Deterministic Formula Diagnosis, Scoring, Guardrails, Phase Planning), and
    Step 6 (AI Plain-English HR Proposal & Output Formatting).

Input:
    - Stage entrypoints imported from `step1_normalize_input.py` through `step6_hr_proposal.py`.

Output:
    - Clean top-level stage functions consumed by `src/main.py` and `tests/test_pipeline_stubs.py`.

TODO:
    1. Keep re-exported entrypoint names stable as team members implement Steps 1-6.
    2. Maintain strict architectural separation: only Steps 1 and 6 accept `StructuredLLMClient`.
    3. Ensure Steps 2, 3, 4, and 5 remain 100% deterministic, reproducible, and company-name agnostic.
"""

from importlib import import_module
from typing import Dict, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "normalize_client_input": ("step1_normalize_input", "normalize_client_input"),
    "analyze_root_causes": ("step2_root_cause_analysis", "analyze_root_causes"),
    "score_candidates_and_cases": ("step3_conditions_scoring", "score_candidates_and_cases"),
    "apply_guardrail_checks": ("step4_guardrail_check", "apply_guardrail_checks"),
    "build_phase_plan": ("step5_phase_planner", "build_phase_plan"),
    "generate_hr_proposal": ("step6_hr_proposal", "generate_hr_proposal"),
}

__all__ = [
    "normalize_client_input",
    "analyze_root_causes",
    "score_candidates_and_cases",
    "apply_guardrail_checks",
    "build_phase_plan",
    "generate_hr_proposal",
]


def __getattr__(name: str):
    """Import stage entrypoints on first use instead of during package startup."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
