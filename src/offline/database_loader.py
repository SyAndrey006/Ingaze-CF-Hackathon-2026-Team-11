"""Load the reviewed normalized case store consumed by Step 3."""

from __future__ import annotations

from pathlib import Path
from src.schemas.domain_models import NormalizedCasesDB

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
