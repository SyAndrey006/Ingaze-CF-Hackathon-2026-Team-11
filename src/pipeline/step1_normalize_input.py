"""Step 1: normalize incoming client data and quarantine contaminated signals.

This module keeps LLM extraction separate from deterministic hygiene. The
intermediate extraction model includes a noise flag; the public pipeline model
remains the exact schema defined in ``pipeline_models.py``.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from src.schemas.domain_models import (
    ActionCategory,
    SectorCategory,
    SignalCode,
    TelemetrySnapshot,
    SectorPeerBenchmarks,
    WorkforceArchetype,
)
from src.schemas.pipeline_models import (
    CohortSiteAsymmetry,
    ExtractedSignal,
    FilteredNoiseItem,
    HealthyBaseline,
    LeadershipRequest,
    NormalizedClientInput,
    RawScenarioBundle,
)
from src.utils.llm_client import StructuredLLMClient

LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parents[2]
CLIENT_IO_DIR = BASE_DIR / "data" / "client_io"
INPUT_FILE = CLIENT_IO_DIR / "input.json"
OUTPUT_DIR = BASE_DIR / "data" / "intermediate_steps"

_UNVERIFIED_MARKERS = re.compile(
    r"\b(?:unverified|uncorroborated|external\s+(?:merchant\s+)?pilot|"
    r"imported\s+from\s+(?:an?\s+)?external|third[- ]party\s+pilot)\b",
    re.IGNORECASE,
)
_RETAIL_SHIFT_MARKERS = re.compile(
    r"\b(?:retail|shop|store|merchant|point[- ]of[- ]sale|pos)\b.{0,80}"
    r"\b(?:weekend|shift|rotation|schedule|fatigue)\b|"
    r"\b(?:weekend|shift|rotation|schedule|fatigue)\b.{0,80}"
    r"\b(?:retail|shop|store|merchant|point[- ]of[- ]sale|pos)\b",
    re.IGNORECASE,
)
_PHYSICAL_RETAIL_POSITIVE = re.compile(
    r"\bphysical\s+(?:retail\s+)?(?:stores?|shops?|outlets?)\b|"
    r"\b(?:retail\s+)?(?:store|shop|outlet)\s+"
    r"(?:associates?|employees|workers|staff|locations?|network)\b|"
    r"\b(?:operate|operates|operating|run|runs|manage|manages|has|have|with)\s+"
    r"(?:\d+\s+)?(?:physical\s+)?(?:retail\s+)?(?:stores?|shops?|outlets?)\b|"
    r"\b(?:retail\s+operations|retail\s+workforce|shop[- ]floor|"
    r"brick[- ]and[- ]mortar)\b",
    re.IGNORECASE,
)
_PHYSICAL_RETAIL_NEGATIVE = re.compile(
    r"\b(?:no|not|without|lack(?:s|ing)?\s+of)\s+(?:any\s+)?"
    r"(?:physical\s+)?(?:retail\s+)?(?:stores?|shops?|outlets?)\b",
    re.IGNORECASE,
)


class _LLMExtractedSignal(ExtractedSignal):
    """Step 1-only extraction shape that preserves an LLM noise judgment."""

    is_unverified_or_external_noise: bool = Field(
        default=False,
        description="True for unverified, externally imported, or out-of-scope evidence.",
    )


class _LLMNormalizedClientInput(BaseModel):
    """LLM payload with the Step 1 public fields plus a private noise flag."""

    scenario_code: str
    company_name: str
    industry_raw: str
    sector_category: SectorCategory
    workforce_archetypes: List[WorkforceArchetype] = Field(default_factory=list)
    headcount: Optional[int] = Field(default=None, ge=1)
    locations_count: Optional[int] = Field(default=None, ge=1)
    workforce_target_summary: str = ""
    declared_evp: str = ""
    canonical_signals: List[_LLMExtractedSignal] = Field(default_factory=list)
    healthy_baselines: List[HealthyBaseline] = Field(default_factory=list)
    cohort_site_asymmetries: List[CohortSiteAsymmetry] = Field(default_factory=list)
    leadership_requests: List[LeadershipRequest] = Field(default_factory=list)
    budget_and_cfo_constraints: List[str] = Field(default_factory=list)


def load_standalone_input(input_path: Path) -> List[RawScenarioBundle]:
    """Load one client brief or a list of client records from a JSON/TXT file."""
    path = Path(input_path)
    suffix = path.suffix.casefold()
    if suffix == ".txt":
        brief = path.read_text(encoding="utf-8-sig").strip()
        if not brief:
            raise ValueError(f"Standalone text input is empty: {path}")
        rows = [
            {
                "scenario_code": "STANDALONE_001",
                "company_name": path.stem or "Standalone Client",
                "industry": "Unspecified",
                "client_internal_context": brief,
                "ingaze_platform_signals": {},
            }
        ]
    elif suffix == ".json":
        with path.open("r", encoding="utf-8-sig") as handle:
            document = json.load(handle)
        if isinstance(document, list):
            rows = document
        elif isinstance(document, dict):
            rows = None
            for key in (
                "clients",
                "scenarios",
                "company_scenarios_to_diagnose",
                "client_scenarios",
                "company_scenarios",
                "companies",
            ):
                if isinstance(document.get(key), list):
                    rows = document[key]
                    break
            if rows is None:
                rows = next(
                    (
                        value
                        for value in document.values()
                        if isinstance(value, list)
                        and all(isinstance(item, dict) for item in value)
                    ),
                    None,
                )
            if rows is None:
                rows = [document]
        else:
            raise ValueError("Standalone JSON input must contain an object or a list of objects.")
        if not isinstance(rows, list):
            raise ValueError("The standalone JSON scenario collection must be a list.")
        if not rows:
            raise ValueError(f"Standalone JSON file contains no client objects: {path}")
    else:
        raise ValueError(
            f"Unsupported standalone input type {path.suffix or '(no extension)'!r}; "
            "use a .json or .txt file."
        )

    bundles: List[RawScenarioBundle] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Standalone JSON client #{index} must be an object.")

        raw_candidate = row.get("raw_scenario", row)
        if not isinstance(raw_candidate, dict):
            raise ValueError(f"Standalone JSON client #{index} has an invalid raw_scenario object.")
        raw_scenario = dict(raw_candidate)
        derived_code = path.stem if len(rows) == 1 else f"{path.stem}_{index:03d}"
        scenario_code = str(
            row.get("scenario_code")
            or row.get("scenario_id")
            or raw_scenario.get("scenario_code")
            or raw_scenario.get("scenario_id")
            or derived_code
        )
        raw_scenario.setdefault("scenario_code", scenario_code)

        t0_raw = (
            row.get("t0_telemetry")
            or row.get("t0_snapshot")
            or row.get("t0_current_snapshot")
            or raw_scenario.get("t0_telemetry")
            or raw_scenario.get("t0_snapshot")
            or raw_scenario.get("t0_current_snapshot")
        )
        if isinstance(t0_raw, dict) and isinstance(t0_raw.get("t0_current_snapshot"), dict):
            t0_raw = t0_raw["t0_current_snapshot"]
        benchmark_raw = (
            row.get("sector_benchmarks")
            or row.get("sector_peer_benchmarks")
            or raw_scenario.get("sector_benchmarks")
            or raw_scenario.get("sector_peer_benchmarks")
        )
        bundles.append(
            RawScenarioBundle(
                scenario_code=scenario_code,
                raw_scenario=raw_scenario,
                t0_telemetry=TelemetrySnapshot.model_validate(t0_raw) if t0_raw else None,
                sector_benchmarks=(
                    SectorPeerBenchmarks.model_validate(benchmark_raw)
                    if benchmark_raw
                    else None
                ),
            )
        )
    return bundles


def filter_contaminated_signals(
    raw_bundle: RawScenarioBundle,
    extracted_signals: List[ExtractedSignal],
    llm_client: Optional[StructuredLLMClient] = None,
) -> Tuple[List[ExtractedSignal], List[FilteredNoiseItem]]:
    """Quarantine unverified/impossible signals, then merge duplicate signal codes.

    ``llm_client`` remains an optional compatibility parameter. Filtering is
    deterministic and does not make an LLM call.
    """
    del llm_client
    clean: List[ExtractedSignal] = []
    noise: List[FilteredNoiseItem] = []
    seen_noise: set[tuple[str, str]] = set()

    for signal in extracted_signals:
        quote = signal.evidence_quote.strip()
        flagged_unverified = bool(
            getattr(signal, "is_unverified_or_external_noise", False)
        ) or bool(_UNVERIFIED_MARKERS.search(quote))
        physically_impossible = _is_impossible_retail_shift(raw_bundle, quote)
        quote_is_grounded = _is_quote_grounded(raw_bundle, quote)
        if not quote_is_grounded:
            LOGGER.info(
                "Signal quote has weak source overlap but is retained for review: %s | %s",
                signal.signal_code.value,
                quote,
            )

        if flagged_unverified or physically_impossible:
            if flagged_unverified:
                reason = (
                    "The source marks this evidence as unverified or imported from an "
                    "external pilot, so it is not accepted as client-verified evidence."
                )
            elif physically_impossible:
                reason = (
                    "Retail/store shift evidence is incompatible with the client's "
                    "documented industry and workforce; the company has no identified "
                    "physical retail operation."
                )
            _append_noise(
                noise,
                seen_noise,
                FilteredNoiseItem(
                    raw_excerpt=quote or "(empty evidence quote)",
                    inferred_mismatched_action_or_topic=signal.signal_code.value,
                    reason_filtered=reason,
                ),
            )
            continue
        clean.append(signal)

    # Catch clearly marked unverified platform-feed artifacts even if a model
    # misses the artifact during extraction. This makes suspicious input visible
    # instead of silently discarding it.
    for raw_excerpt in _find_unverified_feed_excerpts(raw_bundle.raw_scenario):
        if any(
            signal.evidence_quote.strip().lower() in raw_excerpt.lower()
            for signal in extracted_signals
            if signal.evidence_quote.strip()
        ):
            continue
        _append_noise(
            noise,
            seen_noise,
            FilteredNoiseItem(
                raw_excerpt=raw_excerpt,
                inferred_mismatched_action_or_topic=(
                    "Unverified externally imported evidence"
                ),
                reason_filtered=(
                    "The raw platform feed explicitly labels this material as "
                    "unverified and imported from an external pilot."
                ),
            ),
        )

    deduplicated = _deduplicate_signals(clean)
    for item in noise:
        LOGGER.info(
            "Step 1 quarantined signal/topic %s: %s | evidence: %s",
            item.inferred_mismatched_action_or_topic,
            item.reason_filtered,
            item.raw_excerpt,
        )
    return deduplicated, noise


def _append_noise(
    noise: List[FilteredNoiseItem],
    seen: set[tuple[str, str]],
    item: FilteredNoiseItem,
) -> None:
    key = (item.inferred_mismatched_action_or_topic.casefold(), item.raw_excerpt.casefold())
    if key not in seen:
        noise.append(item)
        seen.add(key)


def _find_unverified_feed_excerpts(raw_scenario: dict) -> List[str]:
    platform = raw_scenario.get("ingaze_platform_signals", {})
    if not isinstance(platform, dict):
        return []
    excerpts: List[str] = []
    for value in platform.values():
        if not isinstance(value, str):
            continue
        match = _UNVERIFIED_MARKERS.search(value)
        if not match:
            continue
        # Keep a concise, verbatim window around the marker for the report.
        start = max(0, match.start() - 90)
        if start:
            boundary = value.find(" ", start, match.start())
            if boundary >= 0:
                start = boundary + 1
        end = min(len(value), match.end() + 120)
        if end < len(value):
            boundary = value.rfind(" ", match.end(), end)
            if boundary > match.end():
                end = boundary
        excerpt = value[start:end].strip(" ,.;\n\t")
        if excerpt and excerpt not in excerpts:
            excerpts.append(excerpt)
    return excerpts


def _is_quote_grounded(raw_bundle: RawScenarioBundle, evidence_quote: str) -> bool:
    """Check exact, metric key/value, then 70% content-token overlap grounding."""
    quote = _normalize_grounding_text(evidence_quote.strip().strip("\"'"))
    if not quote:
        return False

    source_documents = [raw_bundle.raw_scenario]
    if raw_bundle.t0_telemetry is not None:
        source_documents.append(raw_bundle.t0_telemetry.model_dump(mode="json"))
    if raw_bundle.sector_benchmarks is not None:
        source_documents.append(raw_bundle.sector_benchmarks.model_dump(mode="json"))

    source_texts: List[str] = []
    for document in source_documents:
        candidates = [json.dumps(document, ensure_ascii=False)]
        candidates.extend(_flatten_source_values(document))
        for candidate in candidates:
            source_texts.append(candidate)
            if quote and quote in _normalize_grounding_text(candidate):
                return True

    if _has_matching_metric_pair(evidence_quote, source_documents):
        return True

    quote_tokens = set(_content_tokens(evidence_quote))
    if not quote_tokens:
        return False
    source_tokens = {
        token
        for source_text in source_texts
        for token in _content_tokens(source_text)
    }
    return len(quote_tokens & source_tokens) / len(quote_tokens) >= 0.70


_CONTENT_TOKEN_RE = re.compile(
    r"\d+(?:[.,]\d+)?%?|[^\W\d_]+(?:['’][^\W\d_]+)*",
    re.UNICODE,
)
_GROUNDING_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by",
    "for", "from", "had", "has", "have", "in", "into", "is", "it", "of",
    "on", "or", "the", "their", "then", "there", "these", "this", "those",
    "to", "was", "were", "with", "within",
}
_METRIC_PAIR_RE = re.compile(
    r"[\"']?(?P<key>[a-zA-Z_][\w .-]*?)[\"']?\s*[:=]\s*"
    r"(?P<value>-?\d+(?:[.,]\d+)?%?)",
    re.IGNORECASE,
)


def _normalize_grounding_text(value: str) -> str:
    """Normalize case, quotes, punctuation, and spacing to meaningful tokens."""
    return " ".join(_content_tokens(value))


def _content_tokens(value: str) -> List[str]:
    return [
        token.casefold().replace("’", "'")
        for token in _CONTENT_TOKEN_RE.findall(value)
        if token.casefold() not in _GROUNDING_STOP_WORDS
    ]


def _has_matching_metric_pair(quote: str, source_documents: Sequence[object]) -> bool:
    quote_pairs = list(_METRIC_PAIR_RE.finditer(quote))
    if not quote_pairs:
        return False

    source_pairs = [
        (key, value)
        for document in source_documents
        for key, value in _iter_numeric_key_values(document)
    ]
    for quote_pair in quote_pairs:
        quoted_key = _normalize_metric_key(quote_pair.group("key"))
        quoted_value = _normalize_metric_value(quote_pair.group("value"))
        if quoted_value is None:
            continue
        for source_key, source_value in source_pairs:
            if _normalize_metric_key(source_key) != quoted_key:
                continue
            if _normalize_metric_value(str(source_value)) == quoted_value:
                return True
    return False


def _iter_numeric_key_values(value: object) -> List[Tuple[str, object]]:
    if isinstance(value, dict):
        pairs: List[Tuple[str, object]] = []
        for key, item in value.items():
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                pairs.append((str(key), item))
            else:
                pairs.extend(_iter_numeric_key_values(item))
        return pairs
    if isinstance(value, (list, tuple)):
        pairs = []
        for item in value:
            pairs.extend(_iter_numeric_key_values(item))
        return pairs
    return []


def _normalize_metric_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _normalize_metric_value(value: str) -> Optional[float]:
    cleaned = value.strip().rstrip("%").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _flatten_source_values(value: object) -> List[str]:
    if isinstance(value, dict):
        flattened: List[str] = []
        for key, item in value.items():
            flattened.append(str(key))
            flattened.extend(_flatten_source_values(item))
        return flattened
    if isinstance(value, (list, tuple)):
        flattened = []
        for item in value:
            flattened.extend(_flatten_source_values(item))
        return flattened
    if value is None:
        return []
    return [str(value)]


def _is_impossible_retail_shift(raw_bundle: RawScenarioBundle, evidence_quote: str) -> bool:
    if not evidence_quote or not _RETAIL_SHIFT_MARKERS.search(evidence_quote):
        return False
    if raw_bundle.raw_scenario.get("sector_category") == SectorCategory.RETAIL_OMNICHANNEL.value:
        return False

    archetype_values = {
        item.value if isinstance(item, WorkforceArchetype) else str(item)
        for item in raw_bundle.raw_scenario.get("workforce_archetypes", [])
    }
    if WorkforceArchetype.DESKLESS_FRONTLINE_RETAIL.value in archetype_values:
        return False

    raw = raw_bundle.raw_scenario
    factual_context = " ".join(
        str(raw.get(key, ""))
        for key in (
            "industry",
            "workforce_target",
            "headcount_and_footprint",
            "organizational_context",
            "client_internal_context",
        )
    )
    if _PHYSICAL_RETAIL_NEGATIVE.search(factual_context):
        return True
    industry = str(raw.get("industry", ""))
    if re.search(r"\bretail\b", industry, re.IGNORECASE):
        return False
    if _PHYSICAL_RETAIL_POSITIVE.search(industry):
        return False
    if _PHYSICAL_RETAIL_POSITIVE.search(raw.get("workforce_target", "")):
        return False
    if _PHYSICAL_RETAIL_POSITIVE.search(
        " ".join(
            str(raw.get(key, ""))
            for key in ("headcount_and_footprint", "organizational_context", "client_internal_context")
        )
    ):
        return False
    return True


def _deduplicate_signals(signals: Sequence[ExtractedSignal]) -> List[ExtractedSignal]:
    """Merge evidence and cohorts for repeated canonical signal codes."""
    merged: dict[SignalCode, ExtractedSignal] = {}
    severity_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    for signal in signals:
        current = merged.get(signal.signal_code)
        if current is None:
            merged[signal.signal_code] = signal.model_copy(deep=True)
            continue

        quotes: List[str] = []
        for quote in (current.evidence_quote, signal.evidence_quote):
            for part in quote.split(" | "):
                cleaned = part.strip()
                if cleaned and cleaned not in quotes:
                    quotes.append(cleaned)
        cohorts: List[str] = []
        for cohort in (*current.affected_cohorts, *signal.affected_cohorts):
            cleaned = cohort.strip()
            if cleaned and cleaned not in cohorts:
                cohorts.append(cleaned)
        current.evidence_quote = " | ".join(quotes)
        current.affected_cohorts = cohorts
        if severity_rank[signal.severity] > severity_rank[current.severity]:
            current.severity = signal.severity
    return list(merged.values())


def normalize_client_input_deterministically(
    raw_bundle: RawScenarioBundle,
) -> NormalizedClientInput:
    """Extract explicit facts with general rules when no LLM is available.

    This fallback deliberately tags only evidence matched in the supplied text
    or telemetry. It does not diagnose causes or recommend interventions.
    """
    raw = raw_bundle.raw_scenario
    platform = raw.get("ingaze_platform_signals", {})
    internal = raw.get("client_internal_context", {})
    platform_texts = _flatten_source_values(platform)
    internal_texts = _flatten_source_values(internal)
    internal_texts.extend(
        str(raw[key])
        for key in ("organizational_context", "hr_intake_notes", "workforce_target")
        if raw.get(key)
    )

    industry = str(raw.get("industry") or "Unspecified")
    profile_text = " ".join(
        [
            industry,
            str(raw.get("workforce_target", "")),
            str(raw.get("headcount_and_footprint", "")),
            str(raw.get("organizational_context", "")),
        ]
    )
    sector = _deterministic_sector(raw.get("sector_category"), profile_text)
    workforce = _deterministic_workforce(profile_text)
    for value in raw.get("workforce_archetypes", []):
        try:
            archetype = WorkforceArchetype(value)
        except (TypeError, ValueError):
            continue
        if archetype not in workforce:
            workforce.append(archetype)
    headcount, locations = _deterministic_footprint(raw)
    declared_evp = str(raw.get("declared_evp") or "").strip()
    if not declared_evp:
        declared_evp = _extract_declared_evp(raw)

    cohorts = _extract_cohort_labels(" ".join([*platform_texts, *internal_texts]))
    source_texts = {
        "outside_in_platform": platform_texts,
        "inside_out_client": internal_texts,
        "t0_telemetry": (
            _flatten_source_values(raw_bundle.t0_telemetry.model_dump(mode="json"))
            if raw_bundle.t0_telemetry
            else []
        ),
    }
    rules = (
        (SignalCode.LOW_PUBLIC_RATING, "outside_in_platform", r"\brating\b.{0,55}\b[1-3](?:\.\d+)?\s*/\s*5\b", "HIGH"),
        (SignalCode.MULTISITE_REPUTATION_VARIANCE, "outside_in_platform", r"\b(?:split|disparity|variance)\b.{0,130}\b(?:HQ|headquarters|stores?|sites?|locations?|hubs?)\b|\bHQ\b.{0,100}\b(?:while|versus|vs\.?)\b.{0,100}\b(?:stores?|sites?|locations?|hubs?)\b", "HIGH"),
        (SignalCode.UNMONITORED_LOCAL_REVIEWS, "outside_in_platform", r"\b(?:unmonitored|untracked|not monitored|not tracked|no monitoring)\b.{0,50}\b(?:reviews?|feedback|mentions?)\b", "MEDIUM"),
        (SignalCode.MOBILE_PORTAL_FRICTION, "outside_in_platform", r"\b(?:mobile|smartphone)\b.{0,140}\b(?:application|portal|apply|visitors?|traffic)\b|\b(?:desktop account|verify (?:their )?email|formatted PDF resume|application.{0,20}screens?)\b", "HIGH"),
        (SignalCode.HIGH_APPLICATION_DROPOFF, "outside_in_platform", r"\b\d+(?:[.,]\d+)?%\s+(?:of\s+)?(?:visitors?\s+)?(?:abandon|drop(?:s|ped)?\s+off)\b|\b(?:application|applicants?).{0,60}\b(?:abandon|drop[- ]off)\b", "HIGH"),
        (SignalCode.GENERIC_BOILERPLATE_JDS, "outside_in_platform", r"\b(?:copy[- ]pasted|boilerplate|generic.{0,30}(?:job|role) descriptions?|old.{0,30}templates?|never mention)\b", "MEDIUM"),
        (SignalCode.CHANNEL_WORKFORCE_MISMATCH, "outside_in_platform", r"\b(?:LinkedIn|corporate social|social channel).{0,160}\b(?:almost zero|few|no|low)\s+(?:applications?|applicants?)\b|\b(?:almost zero|few|no|low)\s+(?:applications?|applicants?).{0,100}\b(?:store|frontline|clinical|warehouse|field)\b", "MEDIUM"),
        (SignalCode.MANUAL_HR_SPREADSHEET_DRAG, "outside_in_platform", r"\b(?:manual(?:ly)?|copying|spreadsheet|Excel tracker)\b.{0,100}\b(?:reviews?|data|track(?:er|ing)?|hours?)\b|\b\d+(?:[.,]\d+)?\s+hours?.{0,80}\b(?:manual|spreadsheet|copying|tracking)\b", "MEDIUM"),
        (SignalCode.EARLY_FIRST_YEAR_ATTRITION, "inside_out_client", r"\b(?:quit|leave|resign|attrition|turnover)\b.{0,100}\b(?:first|six|6|12|twelve|year|months?|newly hired)\b|\b(?:first|six|6|12|twelve|year|months?|newly hired)\b.{0,100}\b(?:quit|leave|resign|attrition|turnover)\b", "HIGH"),
        (SignalCode.UNPREDICTABLE_SHIFT_SCHEDULING, "outside_in_platform", r"\b(?:unpredictable|last[- ]minute|chaotic|unstable)\b.{0,90}\b(?:weekend|shift|roster|schedule)s?\b|\b(?:weekend|shift|roster|schedule)s?\b.{0,90}\b(?:unpredictable|last[- ]minute|chaotic|unstable)\b", "HIGH"),
        (SignalCode.WORKLOAD_BURNOUT, "outside_in_platform", r"\b(?:burnout|burned out|overwork(?:ed)?|exhaust(?:ion|ed)|fatigue)\b", "HIGH"),
        (SignalCode.WEAK_MIDDLE_MANAGEMENT, "outside_in_platform", r"\b(?:manager|supervisor)s?\b.{0,90}\b(?:never give feedback|no feedback|zero people[- ]management training|lack of training|not trained)\b|\b(?:zero|no|lack of)\s+(?:people[- ]management|managerial|management) training\b", "HIGH"),
        (SignalCode.HIGH_FINANCIAL_TURNOVER_RISK, "inside_out_client", r"\b(?:turnover|attrition|replacement|lost[- ]sales)\b.{0,100}\b(?:EUR|USD|€|\$)?\s*\d[\d,.]*\s*(?:k|m|million)?\s*(?:/\s*year|per year|annually)\b", "HIGH"),
        (SignalCode.MISSING_CFO_ROI_EMV_VISIBILITY, "inside_out_client", r"\b(?:freeze|frozen|hard numbers|ROI|return on investment|EMV|cost[- ]per[- ]hire|vanity metrics)\b", "MEDIUM"),
        (SignalCode.LOW_INBOUND_QUALIFIED_APPLICANTS, "inside_out_client", r"\b(?:applicant shortage|shortage of applicants|too few applicants|not enough applicants|lack of qualified applicants)\b", "MEDIUM"),
    )

    signals: List[ExtractedSignal] = []
    seen_quotes: set[tuple[SignalCode, str]] = set()
    for code, stream, pattern_text, severity in rules:
        pattern = re.compile(pattern_text, re.IGNORECASE)
        evidence = _first_matching_sentence(source_texts[stream], pattern)
        if evidence:
            key = (code, evidence.casefold())
            if key not in seen_quotes:
                signals.append(
                    ExtractedSignal(
                        signal_code=code,
                        evidence_quote=evidence,
                        source_stream=stream,
                        severity=severity,
                        affected_cohorts=_extract_cohort_labels(evidence) or cohorts,
                    )
                )
                seen_quotes.add(key)

    # Preserve a say/do gap only when the raw EVP claim and an employee-review
    # contradiction are both present in the source.
    negative_review_pattern = re.compile(
        r"\b(?:unpredictable|burnout|burned out|poor management|never give feedback|"
        r"broken promise|unsafe|hostile|lack of support)\b",
        re.IGNORECASE,
    )
    positive_evp_pattern = re.compile(
        r"\b(?:people[- ]first|work[- ]life balance|well[- ]being|supportive|"
        r"flexib(?:le|ility)|career growth|creativity|inclusive|development)\b",
        re.IGNORECASE,
    )
    review_evidence = _first_matching_sentence(platform_texts, negative_review_pattern)
    if declared_evp and positive_evp_pattern.search(declared_evp) and review_evidence:
        signals.append(
            ExtractedSignal(
                signal_code=SignalCode.SAY_DO_GAP,
                evidence_quote=f"{declared_evp} | {review_evidence}",
                source_stream="outside_in_platform",
                severity="HIGH",
                affected_cohorts=_extract_cohort_labels(review_evidence) or cohorts,
            )
        )

    # T0 telemetry is retained in full; only the explicitly defined >1.1-star
    # external-claims gap is promoted to a canonical signal here.
    if raw_bundle.t0_telemetry:
        gap = raw_bundle.t0_telemetry.public_reputation.external_claims_gap_stars_5
        if gap is not None and gap > 1.1:
            signals.append(
                ExtractedSignal(
                    signal_code=SignalCode.SAY_DO_GAP,
                    evidence_quote=f"public_reputation.external_claims_gap_stars_5: {gap}",
                    source_stream="t0_telemetry",
                    severity="HIGH",
                    affected_cohorts=cohorts,
                )
            )

    canonical_signals, filtered_noise = filter_contaminated_signals(
        raw_bundle, signals
    )
    baselines = _deterministic_healthy_baselines(internal)
    asymmetries = _deterministic_asymmetries(internal)
    if asymmetries and not any(
        signal.signal_code == SignalCode.COHORT_OR_SITE_ASYMMETRY
        for signal in canonical_signals
    ):
        asymmetry = asymmetries[0]
        canonical_signals = _deduplicate_signals(
            [
                *canonical_signals,
                ExtractedSignal(
                    signal_code=SignalCode.COHORT_OR_SITE_ASYMMETRY,
                    evidence_quote=asymmetry.struggling_evidence,
                    source_stream="inside_out_client",
                    severity="HIGH",
                    affected_cohorts=[asymmetry.struggling_segment],
                ),
            ]
        )

    requests = _deterministic_leadership_requests(internal)
    budget = internal.get("budget_and_capacity_constraints", "") if isinstance(internal, dict) else ""
    budget_constraints = [str(budget).strip()] if str(budget).strip() else []

    return NormalizedClientInput(
        scenario_code=raw_bundle.scenario_code,
        company_name=str(raw.get("company_name") or raw_bundle.scenario_code),
        industry_raw=industry,
        sector_category=sector,
        workforce_archetypes=workforce,
        headcount=headcount,
        locations_count=locations,
        workforce_target_summary=str(raw.get("workforce_target") or ""),
        declared_evp=declared_evp,
        canonical_signals=canonical_signals,
        filtered_noise_items=filtered_noise,
        healthy_baselines=baselines,
        cohort_site_asymmetries=asymmetries,
        leadership_requests=requests,
        budget_and_cfo_constraints=budget_constraints,
        t0_telemetry=raw_bundle.t0_telemetry,
        sector_benchmarks=raw_bundle.sector_benchmarks,
    )


def _first_matching_sentence(values: Sequence[str], pattern: re.Pattern[str]) -> str:
    for value in values:
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])", str(value).strip()):
            if pattern.search(sentence):
                return sentence.strip()
        if pattern.search(str(value)):
            return str(value).strip()
    return ""


def _deterministic_sector(value: object, text: str) -> SectorCategory:
    try:
        return SectorCategory(value)
    except (TypeError, ValueError):
        lowered = text.casefold()
    if re.search(r"\b(?:fintech|payments?|payment processing)\b", lowered):
        return SectorCategory.FINTECH_PAYMENTS
    if re.search(r"\b(?:bank(?:ing)?|financial services?)\b", lowered):
        return SectorCategory.BANKING_FINANCIAL_SERVICES
    if re.search(r"\b(?:logistics|freight|supply chain|warehouse)\b", lowered):
        return SectorCategory.LOGISTICS_FREIGHT
    if re.search(r"\b(?:retail|stores?|shops?|apparel|fashion)\b", lowered):
        return SectorCategory.RETAIL_OMNICHANNEL
    if re.search(r"\b(?:healthcare|clinical|clinic|hospital|senior care)\b", lowered):
        return SectorCategory.HEALTHCARE_CLINICAL
    if re.search(r"\b(?:cleantech|clean[- ]tech|sustainability|renewable energy|b corp)\b", lowered):
        return SectorCategory.CLEANTECH_SUSTAINABILITY_BCORP
    if re.search(r"\b(?:software|saas|technology|tech company)\b", lowered):
        return SectorCategory.B2B_TECH_SAAS
    return SectorCategory.GENERAL_ENTERPRISE


def _deterministic_workforce(text: str) -> List[WorkforceArchetype]:
    lowered = text.casefold()
    result: List[WorkforceArchetype] = []
    rules = (
        (r"\b(?:retail|store|shop|apparel|sales associate|shop floor)\b", WorkforceArchetype.DESKLESS_FRONTLINE_RETAIL),
        (r"\b(?:logistics|freight|warehouse|driver|distribution center)\b", WorkforceArchetype.DESKLESS_FRONTLINE_LOGISTICS),
        (r"\b(?:healthcare|clinical|clinic|nurse|hospital|patient care)\b", WorkforceArchetype.MULTISITE_CLINICAL_HEALTHCARE),
        (r"\b(?:software engineer|engineering team|technology specialist|developer)\b", WorkforceArchetype.DESK_BASED_TECH_SPECIALIST),
        (r"\b(?:hq|headquarters|corporate office|corporate team)\b", WorkforceArchetype.CORPORATE_HQ_ADMIN),
        (r"\b(?:multiple sites|multi[- ]site|distributed locations|across \d+\s+(?:physical\s+)?(?:retail\s+)?(?:locations?|stores?|sites?))\b", WorkforceArchetype.MIXED_DISTRIBUTED),
    )
    for pattern, archetype in rules:
        if re.search(pattern, lowered) and archetype not in result:
            result.append(archetype)
    return result


def _deterministic_footprint(raw: dict) -> tuple[Optional[int], Optional[int]]:
    def positive_int(value: object) -> Optional[int]:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        match = re.search(r"\b(\d[\d,]*)\b", str(value)) if value else None
        if match:
            number = int(match.group(1).replace(",", ""))
            return number if number > 0 else None
        return None

    footprint = str(raw.get("headcount_and_footprint", ""))
    headcount = positive_int(raw.get("headcount"))
    if headcount is None:
        match = re.search(r"\b\d[\d,]*\s+employees?\b", footprint, re.IGNORECASE)
        headcount = positive_int(match.group(0)) if match else None
    locations = positive_int(raw.get("locations_count"))
    if locations is None:
        match = re.search(
            r"\b(?:across|at|in)\s+(\d[\d,]*)\s+(?:physical\s+)?"
            r"(?:retail\s+)?(?:stores?|sites?|locations?|clinics?|hubs?)\b",
            footprint,
            re.IGNORECASE,
        )
        locations = positive_int(match.group(1)) if match else None
    return headcount, locations


def _extract_declared_evp(raw: dict) -> str:
    for value in _flatten_source_values(raw):
        match = re.search(
            r"\b(?:declared\s+)?EVP\b[^:]{0,70}:\s*[\"'“‘](.+?)[\"'”’]",
            value,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
    return ""


def _extract_cohort_labels(text: str) -> List[str]:
    pattern = re.compile(
        r"\b(?:(?:suburban\s+mall|city[- ]center\s+flagship|newly[- ]hired|"
        r"in[- ]store|assistant\s+store|store|retail|sales|corporate|design|"
        r"merchandising|frontline|warehouse|clinical|candidate|HQ|headquarters)"
        r"[\s-]+){0,3}(?:stores?|associates?|managers?|teams?|workers?|"
        r"employees?|candidates?|roles?|sites?|hubs?|locations?)\b|"
        r"\b(?:store|retail|frontline|corporate)\s+staff\b|"
        r"\b(?:HQ|headquarters)\b",
        re.IGNORECASE,
    )
    labels: List[str] = []
    for match in pattern.finditer(text):
        label = match.group(0).strip(" ,.;:")
        if label and label.casefold() not in {item.casefold() for item in labels}:
            labels.append(label)
    return labels


def _deterministic_healthy_baselines(internal: object) -> List[HealthyBaseline]:
    if isinstance(internal, dict):
        texts = _flatten_source_values(
            internal.get("healthy_metrics_and_strengths_not_to_break", "")
        )
    else:
        texts = []
    baseline_rules = (
        (re.compile(r"\b(?:pay|compensation|wages?)\b.{0,80}\b(?:above|higher|competitive|exceed)\b", re.I),
         SignalCode.COMPETITIVE_COMPENSATION_HEALTHY, "Competitive base pay",
         "Preserve the documented pay position; do not overhaul compensation without separate evidence."),
        (re.compile(r"\b\d+(?:[.,]\d+)?%?\s+(?:annual\s+)?retention\b|\bhigh[- ]retention\b", re.I),
         SignalCode.HIGH_COHORT_RETENTION_HEALTHY, "High-retention cohort",
         "Protect the identified high-retention cohort from broad changes; use it as a comparison group."),
        (re.compile(r"\b(?:employees?\s+love|valued|popular|strong)\b.{0,80}\b(?:discount|benefit|perk|asset)\b|\b\d+%\s+(?:staff\s+)?discount\b", re.I),
         SignalCode.STRONG_OPERATIONAL_ASSETS_HEALTHY, "Valued employee benefit",
         "Preserve the documented benefit; do not remove it to fund a different initiative."),
    )
    baselines: List[HealthyBaseline] = []
    for text in texts:
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])", text.strip())
        for sentence in sentences:
            for pattern, code, asset, preserve in baseline_rules:
                if pattern.search(sentence) and not any(item.related_signal == code and item.evidence == sentence for item in baselines):
                    baselines.append(
                        HealthyBaseline(
                            asset_or_cohort_name=asset,
                            evidence=sentence.strip(),
                            related_signal=code,
                            do_not_touch_scope=preserve,
                        )
                    )
    return baselines


def _deterministic_asymmetries(internal: object) -> List[CohortSiteAsymmetry]:
    if isinstance(internal, dict):
        texts = _flatten_source_values(internal.get("cohort_and_site_asymmetries", ""))
    else:
        texts = []
    for text in texts:
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])", text.strip())
        struggling = next(
            (sentence.strip() for sentence in sentences if re.search(
                r"\b(?:concentrated|bleeding|struggling|quit|leave|turnover|attrition|chaotic)\b", sentence, re.I
            )),
            "",
        )
        healthy = next(
            (sentence.strip() for sentence in sentences if re.search(
                r"\b(?:smoothly|long[- ]term|high[- ]retention|retain|retention|strong performance)\b", sentence, re.I
            )),
            "",
        )
        if not struggling or not healthy:
            continue
        struggling_match = re.search(
            r"\b(?:concentrated in|focused in|located in)\s+(?:the\s+)?([^,.;]+)",
            struggling,
            re.IGNORECASE,
        )
        struggling_labels = _extract_cohort_labels(struggling)
        healthy_labels = _extract_cohort_labels(healthy)
        struggling_segment = (
            struggling_match.group(1).strip()
            if struggling_match
            else (struggling_labels[0] if struggling_labels else "Affected cohort described by the client")
        )
        healthy_segment = ", ".join(healthy_labels) or "Healthy comparison cohort described by the client"
        return [
            CohortSiteAsymmetry(
                struggling_segment=struggling_segment,
                struggling_evidence=struggling,
                healthy_comparison_segment=healthy_segment,
                healthy_evidence=healthy,
            )
        ]
    return []


def _deterministic_leadership_requests(internal: object) -> List[LeadershipRequest]:
    if not isinstance(internal, dict):
        return []
    text = str(internal.get("leadership_perceptions_and_requests", ""))
    if not text:
        return []
    pattern = re.compile(
        r"\b(?P<role>(?:the\s+)?(?:VP|Vice President|Head|Director|CFO|CEO|"
        r"Finance|Marketing|Leadership)[\w /&-]{0,48}?)\s+"
        r"(?P<verb>wants|suggested|asked|requested|proposed)\s+",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    requests: List[LeadershipRequest] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        action_text = text[match.end():end].strip(" ,.;")
        if not action_text:
            continue
        lowered = action_text.casefold()
        if re.search(r"ambassador|employee advocacy|day in the life", lowered):
            category = ActionCategory.AMBASSADOR_SELECTION_ENABLEMENT
        elif re.search(r"linkedin|thought leadership|blog|content campaign", lowered):
            category = ActionCategory.TECHNICAL_LINKEDIN_STORYTELLING
        elif re.search(r"discount|pay|compensation|wage|benefit", lowered):
            category = ActionCategory.COMPENSATION_BAND_OVERHAUL
        elif re.search(r"shift|roster|schedule", lowered):
            category = ActionCategory.RETAIL_SHIFT_ROTATION
        elif re.search(r"mobile|portal|application form|apply flow", lowered):
            category = ActionCategory.MOBILE_FAST_APPLY_FLOW
        elif re.search(r"manager|coaching|feedback", lowered):
            category = ActionCategory.MANAGER_COACHING_AND_LEVELING
        elif re.search(r"job description|job ad|recruiting ad", lowered):
            category = ActionCategory.PERSONA_ALIGNED_JDS
        else:
            category = ActionCategory.COHORT_TARGETED_ORIGINAL_ACTION
        scope = _extract_cohort_labels(action_text)
        requests.append(
            LeadershipRequest(
                stakeholder_role=re.sub(r"^the\s+", "", match.group("role").strip(), flags=re.I),
                requested_action_text=action_text,
                inferred_action_category=category,
                requested_urgency=(
                    "IMMEDIATE_PHASE_1"
                    if re.search(r"\b(?:immediate(?:ly)?|urgent|next month|right away)\b", action_text, re.I)
                    else "STANDARD"
                ),
                target_scope=", ".join(scope) or "company-wide",
            )
        )
    return requests


def normalize_client_input(
    raw_bundle: RawScenarioBundle,
    llm_client: StructuredLLMClient,
) -> NormalizedClientInput:
    """Run fact-only LLM extraction followed by deterministic Python hygiene."""
    system_prompt = _build_system_prompt()
    user_prompt = json.dumps(
        {
            "scenario_code": raw_bundle.scenario_code,
            "raw_scenario": raw_bundle.raw_scenario,
            "t0_telemetry": (
                raw_bundle.t0_telemetry.model_dump(mode="json")
                if raw_bundle.t0_telemetry
                else None
            ),
            "sector_benchmarks": (
                raw_bundle.sector_benchmarks.model_dump(mode="json")
                if raw_bundle.sector_benchmarks
                else None
            ),
        },
        ensure_ascii=False,
        indent=2,
    )
    extraction = llm_client.generate_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=_LLMNormalizedClientInput,
    )

    canonical_signals, filtered_noise = filter_contaminated_signals(
        raw_bundle,
        list(extraction.canonical_signals),
    )
    raw = raw_bundle.raw_scenario
    return NormalizedClientInput(
        scenario_code=raw_bundle.scenario_code,
        company_name=str(raw.get("company_name") or extraction.company_name),
        industry_raw=str(raw.get("industry") or extraction.industry_raw),
        sector_category=extraction.sector_category,
        workforce_archetypes=extraction.workforce_archetypes,
        headcount=extraction.headcount,
        locations_count=extraction.locations_count,
        workforce_target_summary=extraction.workforce_target_summary,
        declared_evp=extraction.declared_evp,
        canonical_signals=canonical_signals,
        filtered_noise_items=filtered_noise,
        healthy_baselines=extraction.healthy_baselines,
        cohort_site_asymmetries=extraction.cohort_site_asymmetries,
        leadership_requests=extraction.leadership_requests,
        budget_and_cfo_constraints=extraction.budget_and_cfo_constraints,
        t0_telemetry=raw_bundle.t0_telemetry,
        sector_benchmarks=raw_bundle.sector_benchmarks,
    )


def _build_system_prompt() -> str:
    signals = [item.value for item in SignalCode]
    sectors = [item.value for item in SectorCategory]
    workforces = [item.value for item in WorkforceArchetype]
    actions = [item.value for item in ActionCategory]
    return (
        "You perform factual client-data normalization for a human-resources "
        "analytics pipeline. Extract facts only. Do not diagnose root causes, "
        "recommend actions, propose advice, or answer the scenario's key questions. "
        "Do not invent unsupported facts. Preserve short verbatim evidence quotes "
        "for every extracted signal. Map signals only to the supplied canonical "
        "SignalCode values. Separate verified healthy baselines, cohort/site "
        "asymmetries, leadership requests, and budget/CFO constraints into their "
        "matching fields. Keep leadership proposals as requests, not endorsed "
        "recommendations. Mark any unverified, imported, external-pilot, or "
        "physically out-of-scope feed evidence with "
        "is_unverified_or_external_noise=true; do not silently omit it. "
        "Extract SAY_DO_GAP whenever external recruiting/EVP promises conflict with "
        "employee or candidate reviews, even if the wording is qualitative. A T0 "
        "external_claims_gap_stars_5 value greater than 1.1 is strong quantitative "
        "evidence for SAY_DO_GAP. Use a verbatim quote that captures the claim/review "
        "contradiction. "
        "Map early turnover at six months or during the first year to "
        "EARLY_FIRST_YEAR_ATTRITION. Keep direct metrics and T0 telemetry grounded "
        "in the supplied values. Use null for unknown numeric profile fields. "
        "Before returning, perform a coverage pass over every raw source field: extract "
        "each distinct supported problem signal, preserve quantified healthy baselines, "
        "record explicit struggling-versus-thriving groups, retain every leadership "
        "request separately, and capture budget constraints. Do not leave a field empty "
        "when its evidence is present; leave it empty only when the input contains no "
        "supporting fact. Choose sector and workforce archetypes from company profile "
        "facts, not from unrelated or quarantined feed rows.\n\n"
        f"SignalCode values: {', '.join(signals)}\n"
        f"SectorCategory values: {', '.join(sectors)}\n"
        f"WorkforceArchetype values: {', '.join(workforces)}\n"
        f"ActionCategory values: {', '.join(actions)}"
    )


def format_normalization_report(results: Sequence[NormalizedClientInput]) -> str:
    """Render the same readable text used for the CLI and inspection report."""
    sections: List[str] = []
    for result in results:
        lines = [
            "=" * 88,
            f"Scenario: {result.scenario_code}",
            f"Company: {result.company_name}",
            f"Industry: {result.industry_raw} | Canonical sector: {result.sector_category.value}",
            "Workforce archetypes: "
            + (_join_or_none(item.value for item in result.workforce_archetypes)),
            f"Workforce target: {result.workforce_target_summary or '(not specified)' }",
            f"Headcount / locations: {result.headcount or 'unknown'} / {result.locations_count or 'unknown'}",
            f"Declared EVP: {result.declared_evp or '(not specified)' }",
            "",
            "Active Normalized Signals:",
        ]
        if result.canonical_signals:
            for signal in result.canonical_signals:
                cohorts = _join_or_none(signal.affected_cohorts)
                lines.extend(
                    [
                        f"  - {signal.signal_code.value} [{signal.severity}] | affected: {cohorts}",
                        f"    Evidence: \"{signal.evidence_quote}\"",
                    ]
                )
        else:
            lines.append("  - None identified")

        lines.extend(["", 'Healthy Baselines ("Do Not Touch"):'])
        if result.healthy_baselines:
            for baseline in result.healthy_baselines:
                lines.append(
                    f"  - {baseline.asset_or_cohort_name} [{baseline.related_signal.value}]"
                )
                lines.append(f"    Evidence: {baseline.evidence}")
                lines.append(f"    Preserve: {baseline.do_not_touch_scope}")
        else:
            lines.append("  - None identified")

        lines.extend(["", "Cohort/Site Asymmetries:"])
        if result.cohort_site_asymmetries:
            for asymmetry in result.cohort_site_asymmetries:
                lines.append(
                    f"  - Struggling: {asymmetry.struggling_segment} — "
                    f"{asymmetry.struggling_evidence}"
                )
                lines.append(
                    f"    Comparison: {asymmetry.healthy_comparison_segment} — "
                    f"{asymmetry.healthy_evidence}"
                )
        else:
            lines.append("  - None identified")

        lines.extend(["", "Leadership Requests:"])
        if result.leadership_requests:
            for request in result.leadership_requests:
                lines.append(
                    f"  - {request.stakeholder_role}: {request.requested_action_text}"
                )
                lines.append(
                    f"    Action category: {request.inferred_action_category.value} | "
                    f"urgency: {request.requested_urgency} | scope: {request.target_scope}"
                )
        else:
            lines.append("  - None identified")

        lines.extend(["", "Filtered / Quarantined Noise:"])
        if result.filtered_noise_items:
            for item in result.filtered_noise_items:
                lines.append(
                    f"  - Topic: {item.inferred_mismatched_action_or_topic}"
                )
                lines.append(f"    Evidence: \"{item.raw_excerpt}\"")
                lines.append(f"    Why filtered: {item.reason_filtered}")
        else:
            lines.append("  - None identified")

        lines.extend(["", "Budget and CFO Constraints:"])
        if result.budget_and_cfo_constraints:
            lines.extend(f"  - {item}" for item in result.budget_and_cfo_constraints)
        else:
            lines.append("  - None identified")
        sections.append("\n".join(lines))
    return "\n\n".join(sections).rstrip() + "\n"


def run_normalization_cli(
    scenario_code: Optional[str] = None,
    llm_client: Optional[StructuredLLMClient] = None,
    output_dir: Path = OUTPUT_DIR,
    file_path: Optional[Path] = None,
    input_path: Optional[Path] = None,
) -> List[NormalizedClientInput]:
    """Normalize one client JSON file into a matching intermediate-step file."""
    if input_path is not None:
        if file_path is not None:
            raise ValueError("Pass only one of file_path or the legacy input_path argument.")
        file_path = input_path
    source_path = Path(file_path) if file_path is not None else INPUT_FILE
    if source_path.suffix.casefold() != ".json":
        raise ValueError("--file accepts a .json file.")
    if not source_path.is_file():
        print(
            f"No client JSON file found at {source_path}. "
            f"Add client data to {INPUT_FILE} or pass --file <path>."
        )
        return []

    bundles = load_standalone_input(source_path)
    bundles = [bundle for bundle in bundles if _has_client_content(bundle.raw_scenario)]
    if not bundles:
        print(
            f"No client details found in {source_path}. "
            f"Add client data to {INPUT_FILE} or pass --file <path>."
        )
        return []

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    client = llm_client or StructuredLLMClient()
    if scenario_code:
        bundles = [
            bundle
            for bundle in bundles
            if bundle.scenario_code.casefold() == scenario_code.casefold()
        ]
        if not bundles:
            raise ValueError(
                f"Scenario {scenario_code!r} was not found in {source_path.name}."
            )

    results: List[NormalizedClientInput] = []
    for bundle in bundles:
        print(f"Processing {source_path.name}...")
        try:
            results.append(normalize_client_input(bundle, client))
        except RuntimeError as exc:
            if "No LLM API key is configured" not in str(exc):
                raise
            print(
                "No LLM API key is configured; using deterministic fact extraction "
                "for this input."
            )
            results = [normalize_client_input_deterministically(item) for item in bundles]
            break

    normalized_paths: List[Path] = []
    for result in results:
        safe_code = re.sub(r"[^A-Za-z0-9_.-]+", "_", result.scenario_code).strip("._") or "scenario"
        scenario_dir = output_dir / safe_code
        scenario_dir.mkdir(parents=True, exist_ok=True)
        normalized_path = scenario_dir / "step1_normalize_input.json"
        normalized_path.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        normalized_paths.append(normalized_path)
    signal_count = sum(len(result.canonical_signals) for result in results)
    noise_count = sum(len(result.filtered_noise_items) for result in results)
    print(
        f"Normalization complete: {len(results)} client(s), "
        f"{signal_count} active signal(s), {noise_count} quarantined item(s)."
    )
    for normalized_path in normalized_paths:
        print(f"Wrote normalized JSON: {normalized_path}")
    return results


def _has_client_content(raw_scenario: dict) -> bool:
    """Avoid attempting LLM normalization for an empty input.json placeholder."""
    return any(
        key not in {"scenario_code", "scenario_id"}
        and value not in (None, "", [], {})
        for key, value in raw_scenario.items()
    )


def _join_or_none(values: Sequence[str]) -> str:
    return ", ".join(values) if values else "company-wide / unspecified"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize data/client_io/input.json into per-scenario intermediate steps."
    )
    parser.add_argument(
        "--scenario",
        help="Normalize one exact scenario_code; omit to process all scenarios.",
    )
    parser.add_argument(
        "--file",
        "--input",
        dest="file_path",
        type=Path,
        help=f"Client JSON file to normalize (default: {INPUT_FILE}).",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    try:
        run_normalization_cli(
            scenario_code=args.scenario,
            file_path=args.file_path,
            output_dir=args.output_dir,
        )
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(status=2, message=f"Step 1 normalization failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
