"""Public entrypoints for the live six-step recommendation pipeline.

Stages 2-5 use deterministic graph and Python rules. Imports are lazy so running
``python -m src.pipeline.step1_normalize_input`` does not pre-import the module.
"""

from importlib import import_module
from typing import Dict, Tuple


_EXPORTS: Dict[str, Tuple[str, str]] = {
    "normalize_client_input": ("step1_normalize_input", "normalize_client_input"),
    "run_root_cause_analysis": ("step2_root_cause_analysis", "run_root_cause_analysis"),
    "score_diagnostic_candidates": ("step3_conditions_scoring", "score_diagnostic_candidates"),
    "evaluate_guardrails": ("step4_guardrail_check", "evaluate_guardrails"),
    "build_reasoning_phase_plan": ("step5_phase_planner", "build_reasoning_phase_plan"),
    "assemble_recommendation": ("step6_hr_proposal", "assemble_recommendation"),
    "generate_hr_proposal": ("step6_hr_proposal", "generate_hr_proposal"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Import a stage function on first access."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
