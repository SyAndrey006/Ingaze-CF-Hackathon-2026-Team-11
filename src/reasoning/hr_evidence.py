"""Load provenance-bearing evidence packs and rank entries by topic."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

BUILTIN_LIBRARY = Path(__file__).resolve().parents[2] / "database" / "knowledge" / "hr_evidence_library.json"
TEXT_FIELDS = ("id", "kind", "title", "url", "finding", "applicability")


def load_library(extra_packs=()):
    entries = {}
    for path in (BUILTIN_LIBRARY, *extra_packs):
        records = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(records, list):
            raise ValueError(f"{path}: expected a list of evidence records")
        for index, record in enumerate(records, start=1):
            location = f"{path}, record {index}"
            if not isinstance(record, dict) or any(
                not isinstance(record.get(key), str) or not record[key].strip()
                for key in TEXT_FIELDS
            ):
                raise ValueError(f"{location}: expected non-empty fields {', '.join(TEXT_FIELDS)}")
            url = urlsplit(record["url"])
            if url.scheme != "https" or not url.hostname:
                raise ValueError(f"{location}: expected an HTTPS source URL")
            topics = record.get("topics")
            if not isinstance(topics, list) or not topics or any(
                not isinstance(topic, str) or not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", topic)
                for topic in topics
            ):
                raise ValueError(f"{location}: expected non-empty snake_case topics")
            if record["id"] in entries:
                raise ValueError(f"{location}: duplicate evidence ID {record['id']}")
            entries[record["id"]] = record
    return list(entries.values())


def search_library(entries, topics=(), query="", limit=3):
    """Rank topic matches first, then matches in the title and finding."""
    query_words = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored = []
    for entry in entries:
        matched_topics = sorted(set(topics).intersection(entry["topics"]))
        topic_words = set(re.findall(r"[a-z0-9]+", " ".join(entry["topics"])))
        body_words = set(re.findall(r"[a-z0-9]+", f"{entry['title']} {entry['finding']}".lower()))
        score = 4 * len(matched_topics)
        score += 2 * len(query_words & topic_words) + len(query_words & body_words)
        if score:
            scored.append({**entry, "matched_topics": matched_topics, "score": score})
    return sorted(scored, key=lambda entry: (-entry["score"], entry["id"]))[:limit]
