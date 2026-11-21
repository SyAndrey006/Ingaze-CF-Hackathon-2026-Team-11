"""
Module: case_curation_drafter.py
Stage: Offline Indexing (curation maintenance)
Execution Type: AI (drafting) + Formula (verification)

Description:
    Keeps `database/curation/case_curation.json` in sync with the raw case narratives
    without manual typing. For every raw case in
    `database/ingaze_sandbox_dataset.json -> raw_case_study_narratives` that has no
    curation entry yet, it:
      1. asks `StructuredLLMClient` (temperature 0) to map the narrative to canonical
         enums (sector, workforce, problem/healthy signals with verbatim quotes,
         intervention steps with phase buckets, research snippet numbers),
         using reviewed curation entries as few-shot examples,
      2. verifies the draft with `case_normalizer.verify_curation` (quotes must be
         verbatim, enums valid, snippets exist) and re-prompts with the exact errors,
      3. drops anything that still fails after the last attempt (recorded in
         `draft_notes`), and appends the entry with `review_status: "llm_draft"`.

    A human then reviews the draft in the JSON file and approves it with `--approve`.
    Drafts are built into normalized_cases.json with a warning until approved.

    Anti-hardcoding: only historical case narratives and research snippets are sent to
    the LLM. `company_scenarios_to_diagnose` is never read.

Usage:
    python -m src.offline.case_curation_drafter                 # draft all uncurated cases
    python -m src.offline.case_curation_drafter --dry-run       # print drafts, don't write
    python -m src.offline.case_curation_drafter --case-name "X" # draft only this raw case
    python -m src.offline.case_curation_drafter --list-drafts   # show unreviewed drafts
    python -m src.offline.case_curation_drafter --approve CASE_12_FOO [CASE_13_BAR ...]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Set

from pydantic import BaseModel, Field

from src.offline.case_normalizer import (
    DEFAULT_CURATION,
    DEFAULT_SANDBOX,
    DRAFT_STATUS,
    research_snippet_nos,
    verify_curation,
)
from src.schemas.domain_models import (
    ActionCategory,
    SectorCategory,
    SignalCode,
    WorkforceArchetype,
)

DEFAULT_MAX_ATTEMPTS = 3
MAX_FEW_SHOT_EXAMPLES = 3

PHASE_GUIDANCE = (
    "phase_bucket 1 = diagnostics, audits, listening and foundations; "
    "2 = core structural fixes (process, management, compensation, portal, EVP); "
    "3 = downstream scaling and amplification (advocacy, storytelling, dashboards rolled out at scale). "
    "Follow the order the narrative gives; if it states a timing (e.g. 'only after X'), respect it."
)


# -----------------------------------------------------------------------------
# LLM response schema (no numeric constraints so strict structured output works on
# every provider; ranges are checked by verify_curation instead).
# -----------------------------------------------------------------------------

class DraftSignal(BaseModel):
    signal: SignalCode
    evidence: Literal["stated", "inferred"]
    quote: str = Field(description="Exact, character-for-character substring of the raw case text.")


class DraftStep(BaseModel):
    step_order: int
    action_category: ActionCategory
    action_title: str
    phase_bucket: int


class CaseCurationDraft(BaseModel):
    sector_category: SectorCategory
    workforce_archetypes: List[WorkforceArchetype]
    problem_signals: List[DraftSignal]
    healthy_signals: List[DraftSignal]
    steps: List[DraftStep]
    snippets: List[int]


# -----------------------------------------------------------------------------
# Curation file helpers
# -----------------------------------------------------------------------------

def read_json(path: Path) -> Dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)


def write_curation(curation: Dict[str, Any], path: Path) -> None:
    Path(path).write_text(json.dumps(curation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def uncurated_raw_cases(raw_sandbox_data: Dict[str, Any], curation: Dict[str, Any]) -> List[Dict[str, Any]]:
    curated = {e["case_name"] for e in curation.get("cases", [])}
    return [c for c in raw_sandbox_data["raw_case_study_narratives"] if c["case_name"] not in curated]


def next_case_id(case_name: str, existing_ids: Sequence[str]) -> str:
    """`CASE_<nn>_<SLUG>` with nn = highest existing number + 1, slug from the name before '('."""
    numbers = [int(m.group(1)) for cid in existing_ids if (m := re.match(r"CASE_(\d+)_", cid))]
    base = unicodedata.normalize("NFKD", case_name.split("(")[0]).encode("ascii", "ignore").decode()
    slug = "_".join(re.findall(r"[A-Za-z0-9]+", base)).upper()[:24].strip("_") or "CASE"
    candidate = f"CASE_{max(numbers, default=0) + 1:02d}_{slug}"
    while candidate in existing_ids:  # defensive, numbers already make it unique
        candidate += "_X"
    return candidate


def approve(curation: Dict[str, Any], case_ids: Sequence[str]) -> List[str]:
    """Mark drafts as human-reviewed. Returns the ids that were not found as drafts."""
    wanted = set(case_ids)
    for entry in curation.get("cases", []):
        if entry["case_id"] in wanted and entry.get("review_status") == DRAFT_STATUS:
            entry["review_status"] = "reviewed"
            entry.pop("draft_notes", None)
            wanted.discard(entry["case_id"])
    return sorted(wanted)


# -----------------------------------------------------------------------------
# Prompting
# -----------------------------------------------------------------------------

def _pick_examples(curation: Dict[str, Any], limit: int = MAX_FEW_SHOT_EXAMPLES) -> List[Dict[str, Any]]:
    """Reviewed entries chosen greedily to cover as many workforce archetypes as possible."""
    reviewed = [e for e in curation.get("cases", []) if e.get("review_status") == "reviewed"]
    picked: List[Dict[str, Any]] = []
    covered: Set[str] = set()
    while reviewed and len(picked) < limit:
        best = max(reviewed, key=lambda e: (len(set(e["workforce_archetypes"]) - covered), len(e["problem_signals"])))
        picked.append(best)
        covered |= set(best["workforce_archetypes"])
        reviewed.remove(best)
    return picked


def _example_payload(entry: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("sector_category", "workforce_archetypes", "problem_signals", "healthy_signals", "steps", "snippets")
    return {k: entry[k] for k in keys}


def build_prompts(
    raw_case: Dict[str, Any],
    raw_sandbox_data: Dict[str, Any],
    curation: Dict[str, Any],
) -> tuple[str, str]:
    raw_by_name = {c["case_name"]: c for c in raw_sandbox_data["raw_case_study_narratives"]}
    snippets = [
        {"snippet_no": s["snippet_no"], "source": s.get("source", ""), "finding": s.get("finding", "")}
        for s in raw_sandbox_data.get("raw_empirical_research_snippets", [])
    ]

    system = (
        "You map historical HR case-study narratives to a fixed, company-agnostic ontology. "
        "Output only values from the allowed enums.\n\n"
        "Rules:\n"
        "- problem_signals: problems/root causes present BEFORE the intervention. "
        "healthy_signals: strengths already present before the intervention (often empty).\n"
        "- quote: copy an exact substring of the raw case text, character for character "
        "(same casing and punctuation), 3-15 words. Never paraphrase. If no sentence states the "
        "signal directly, quote the passage it is derived from and set evidence='inferred'; "
        "otherwise evidence='stated'.\n"
        "- Only tag signals the text supports. Do not invent problems to fill the list.\n"
        "- steps: one per intervention in the narrative, in narrative order, step_order starting at 1. "
        "action_title: short wording taken from the narrative. " + PHASE_GUIDANCE + "\n"
        "- snippets: REQUIRED, never empty. The 1-3 research snippet numbers whose finding best supports "
        "this case's problems or interventions. Only use numbers from the list.\n"
        "- workforce_archetypes: who the HR problem is about (target talent / employees), not the customers.\n\n"
        f"Allowed sector_category: {[s.value for s in SectorCategory]}\n"
        f"Allowed workforce_archetypes: {[w.value for w in WorkforceArchetype]}\n"
        f"Allowed signal codes: {[s.value for s in SignalCode]}\n"
        f"Allowed action_category: {[a.value for a in ActionCategory]}\n\n"
        f"Research snippets:\n{json.dumps(snippets, ensure_ascii=False, indent=1)}"
    )

    examples = []
    for entry in _pick_examples(curation):
        raw = raw_by_name.get(entry["case_name"])
        if raw is not None:
            examples.append(
                "RAW CASE:\n" + json.dumps(raw, ensure_ascii=False, indent=1)
                + "\nCURATION:\n" + json.dumps(_example_payload(entry), ensure_ascii=False, indent=1)
            )

    user = (
        "Reviewed examples:\n\n" + "\n\n---\n\n".join(examples)
        + "\n\n=====\n\nNow curate this RAW CASE:\n" + json.dumps(raw_case, ensure_ascii=False, indent=1)
    )
    return system, user


# -----------------------------------------------------------------------------
# Drafting
# -----------------------------------------------------------------------------

def _to_entry(case_id: str, case_name: str, draft: CaseCurationDraft) -> Dict[str, Any]:
    data = draft.model_dump(mode="json")
    return {
        "case_id": case_id,
        "case_name": case_name,
        "review_status": DRAFT_STATUS,
        "sector_category": data["sector_category"],
        "workforce_archetypes": list(dict.fromkeys(data["workforce_archetypes"])),
        "problem_signals": data["problem_signals"],
        "healthy_signals": data["healthy_signals"],
        # The list is in narrative order; models sometimes put the phase into step_order.
        "steps": [dict(s, step_order=i) for i, s in enumerate(data["steps"], start=1)],
        "snippets": list(dict.fromkeys(data["snippets"])),
    }


def _soft_issues(entry: Dict[str, Any]) -> List[str]:
    """Quality gaps worth a retry but not a reason to drop anything."""
    issues = []
    if not entry["snippets"]:
        issues.append(
            "snippets is empty: pick the 1-3 research snippets whose finding best supports this case's "
            "problems or interventions (every reviewed example cites at least 2)"
        )
    return issues


def _errors_for(entry: Dict[str, Any], raw_case: Dict[str, Any], valid_snippets: Set[int]) -> List[str]:
    return verify_curation(
        {"cases": [entry]}, [raw_case], valid_snippet_nos=valid_snippets, require_all_raw_cases=False
    )


def _drop_invalid(entry: Dict[str, Any], raw_case: Dict[str, Any], valid_snippets: Set[int]) -> List[str]:
    """Remove items that still fail verification; return notes describing what was dropped."""
    text = " ".join(str(v) for v in raw_case.values())
    notes: List[str] = []
    for group in ("problem_signals", "healthy_signals"):
        kept = []
        for sig in entry[group]:
            if sig.get("quote") and sig["quote"] in text:
                kept.append(sig)
            else:
                notes.append(f"dropped {group[:-1]} {sig['signal']}: quote not verbatim ({sig.get('quote')!r})")
        entry[group] = kept
    kept_steps = [s for s in entry["steps"] if s["phase_bucket"] in (1, 2, 3)]
    for s in entry["steps"]:
        if s not in kept_steps:
            notes.append(f"dropped step {s['action_title']!r}: phase_bucket {s['phase_bucket']} not in 1..3")
    entry["steps"] = [dict(s, step_order=i) for i, s in enumerate(kept_steps, start=1)]
    bad = [n for n in entry["snippets"] if n not in valid_snippets]
    if bad:
        notes.append(f"dropped unknown research snippets {bad}")
    entry["snippets"] = [n for n in entry["snippets"] if n in valid_snippets]
    return notes


def draft_case_entry(
    raw_case: Dict[str, Any],
    raw_sandbox_data: Dict[str, Any],
    curation: Dict[str, Any],
    llm_client: Any,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> Dict[str, Any]:
    """Draft one verified curation entry (review_status='llm_draft') for a raw case."""
    valid_snippets = research_snippet_nos(raw_sandbox_data)
    case_id = next_case_id(raw_case["case_name"], [e["case_id"] for e in curation.get("cases", [])])
    system, user = build_prompts(raw_case, raw_sandbox_data, curation)

    entry: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    prompt = user
    for attempt in range(1, max_attempts + 1):
        draft = llm_client.generate_structured(
            system_prompt=system, user_prompt=prompt, response_model=CaseCurationDraft
        )
        entry = _to_entry(case_id, raw_case["case_name"], draft)
        errors = _errors_for(entry, raw_case, valid_snippets)
        problems = errors + _soft_issues(entry)
        if not problems:
            break
        prompt = (
            f"{user}\n\nYour previous answer had these problems:\n- " + "\n- ".join(problems)
            + "\nFix them. Quotes must be copied exactly from the RAW CASE text."
        )

    assert entry is not None
    notes = _drop_invalid(entry, raw_case, valid_snippets) if errors else []
    notes += [f"needs review: {issue}" for issue in _soft_issues(entry)]
    remaining = _errors_for(entry, raw_case, valid_snippets)
    if remaining:
        raise ValueError(f"Draft for {raw_case['case_name']!r} is still invalid:\n  - " + "\n  - ".join(remaining))
    if not entry["steps"]:
        raise ValueError(f"Draft for {raw_case['case_name']!r} has no valid intervention steps.")

    entry["draft_notes"] = [f"drafted {dt.date.today().isoformat()}"] + notes
    return entry


def draft_missing_cases(
    raw_sandbox_data: Dict[str, Any],
    curation: Dict[str, Any],
    llm_client: Any,
    only_case_name: Optional[str] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> List[Dict[str, Any]]:
    """Draft entries for all uncurated raw cases and append them to `curation` (in place)."""
    todo = uncurated_raw_cases(raw_sandbox_data, curation)
    if only_case_name is not None:
        todo = [c for c in todo if c["case_name"] == only_case_name]
    new_entries = []
    for raw_case in todo:
        entry = draft_case_entry(raw_case, raw_sandbox_data, curation, llm_client, max_attempts)
        curation.setdefault("cases", []).append(entry)
        new_entries.append(entry)
    return new_entries


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Draft or approve case curation entries.")
    parser.add_argument("--sandbox", type=Path, default=DEFAULT_SANDBOX)
    parser.add_argument("--curation", type=Path, default=DEFAULT_CURATION)
    parser.add_argument("--case-name", help="Only draft this raw case_name.")
    parser.add_argument("--dry-run", action="store_true", help="Print drafts, do not write the curation file.")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--list-drafts", action="store_true", help="List unreviewed drafts and exit.")
    parser.add_argument("--approve", nargs="+", metavar="CASE_ID", help="Mark drafts as human-reviewed.")
    args = parser.parse_args(argv)

    curation = read_json(args.curation)

    if args.list_drafts:
        drafts = [e for e in curation.get("cases", []) if e.get("review_status") == DRAFT_STATUS]
        for e in drafts:
            print(f"{e['case_id']:<28} {e['case_name']}")
            for note in e.get("draft_notes", []):
                print(f"    - {note}")
        print(f"{len(drafts)} unreviewed draft(s)")
        return 0

    if args.approve:
        missing = approve(curation, args.approve)
        write_curation(curation, args.curation)
        for cid in args.approve:
            if cid not in missing:
                print(f"approved {cid}")
        for cid in missing:
            print(f"not an unreviewed draft: {cid}")
        print("Rebuild with `python -m src.offline.case_normalizer`.")
        return 1 if missing else 0

    sandbox = read_json(args.sandbox)
    if not uncurated_raw_cases(sandbox, curation):
        print("All raw cases are already curated. Nothing to draft.")
        return 0

    from src.utils.llm_client import StructuredLLMClient

    try:
        new_entries = draft_missing_cases(
            sandbox, curation, StructuredLLMClient(), args.case_name, args.max_attempts
        )
    except (ValueError, RuntimeError) as exc:
        print(f"Drafting failed: {exc}")
        return 1

    for entry in new_entries:
        print(json.dumps(entry, indent=2, ensure_ascii=False))
    if not args.dry_run and new_entries:
        write_curation(curation, args.curation)
        print(
            f"\nAppended {len(new_entries)} draft(s) to {args.curation}. Review them, then run "
            "`python -m src.offline.case_curation_drafter --approve <CASE_ID>` and "
            "`python -m src.offline.case_normalizer`."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
