"""Compatibility wrapper for deterministic construction of normalized cases.

The active rule source remains ``database/knowledge/hr_knowledge_graph.json``;
this module does not build a duplicate normalized-rules database.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.schemas.domain_models import NormalizedCasesDB
from src.utils.llm_client import StructuredLLMClient


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
