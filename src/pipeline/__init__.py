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

from src.pipeline.step1_normalize_input import normalize_client_input
from src.pipeline.step2_root_cause_analysis import analyze_root_causes
from src.pipeline.step3_conditions_scoring import score_candidates_and_cases
from src.pipeline.step4_guardrail_check import apply_guardrail_checks
from src.pipeline.step5_phase_planner import build_phase_plan
from src.pipeline.step6_hr_proposal import generate_hr_proposal

__all__ = [
    "normalize_client_input",
    "analyze_root_causes",
    "score_candidates_and_cases",
    "apply_guardrail_checks",
    "build_phase_plan",
    "generate_hr_proposal",
]
