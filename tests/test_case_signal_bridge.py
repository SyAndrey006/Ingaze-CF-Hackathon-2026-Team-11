"""Tests for src/offline/case_signal_bridge.py (Step 2 vocabulary -> case-store enums)."""

import ast
import unittest
from pathlib import Path

from src.offline.case_signal_bridge import (
    PROFILE_TO_SECTOR_PRIORITY,
    PROFILE_TO_WORKFORCE,
    TRACK_TAG_TO_SIGNALS,
    UNMAPPED_TRACK_TAGS,
    client_match_profile,
    sector_for_profile,
    signals_for_track_tags,
    workforce_for_profile,
)
from src.pipeline.step2_root_cause_analysis import PROFILE, load_graph
from src.schemas.domain_models import SectorCategory, SignalCode, WorkforceArchetype

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestVocabularyCoverage(unittest.TestCase):
    def test_every_graph_track_tag_is_mapped_or_explicitly_unmapped(self):
        graph_tags = {
            tag for rule in load_graph()["rules"].values() for tag in rule.get("track_tags", [])
        }
        unknown = graph_tags - set(TRACK_TAG_TO_SIGNALS) - UNMAPPED_TRACK_TAGS
        self.assertFalse(unknown, f"New graph track tags need a case-store mapping: {sorted(unknown)}")

    def test_mapped_and_unmapped_are_disjoint(self):
        self.assertFalse(set(TRACK_TAG_TO_SIGNALS) & UNMAPPED_TRACK_TAGS)

    def test_every_step2_profile_tag_is_used(self):
        used = set(PROFILE_TO_WORKFORCE) | {tag for tag, _ in PROFILE_TO_SECTOR_PRIORITY} | {"distributed"}
        self.assertFalse(set(PROFILE) - used, f"Unmapped profile tags: {sorted(set(PROFILE) - used)}")

    def test_targets_are_valid_enums(self):
        for signals in TRACK_TAG_TO_SIGNALS.values():
            self.assertTrue(signals)
            for signal in signals:
                self.assertIsInstance(signal, SignalCode)


class TestTranslation(unittest.TestCase):
    def test_signals_union_and_unknown_ignored(self):
        self.assertEqual(
            signals_for_track_tags({"mobile_friction", "agency_spend", "internal_mobility", "nope"}),
            {
                SignalCode.MOBILE_PORTAL_FRICTION,
                SignalCode.HIGH_APPLICATION_DROPOFF,
                SignalCode.HIGH_EXTERNAL_AGENCY_DEPENDENCY,
            },
        )

    def test_distributed_only_as_fallback_workforce(self):
        self.assertEqual(
            workforce_for_profile({"freight", "distributed"}),
            [WorkforceArchetype.DESKLESS_FRONTLINE_LOGISTICS],
        )
        self.assertEqual(workforce_for_profile({"distributed"}), [WorkforceArchetype.MIXED_DISTRIBUTED])
        self.assertEqual(workforce_for_profile(set()), [])

    def test_sector_priority(self):
        self.assertEqual(sector_for_profile({"tech", "fintech"}), SectorCategory.FINTECH_PAYMENTS)
        self.assertEqual(sector_for_profile({"sustainability", "care"}), SectorCategory.HEALTHCARE_CLINICAL)
        self.assertEqual(sector_for_profile({"sustainability"}), SectorCategory.CLEANTECH_SUSTAINABILITY_BCORP)
        self.assertIsNone(sector_for_profile({"distributed"}))

    def test_client_match_profile_is_deterministic(self):
        a = client_match_profile(["post_tracking", "burnout", "emv"], ["tech", "distributed"])
        b = client_match_profile(["emv", "burnout", "post_tracking"], ["distributed", "tech"])
        self.assertEqual(a, b)


class TestNoCaseNameHardcoding(unittest.TestCase):
    def test_step2_and_step3_have_no_per_case_tag_table(self):
        for rel in ("src/pipeline/step2_root_cause_analysis.py", "src/pipeline/step3_conditions_scoring.py",
                    "src/reasoning/hr_policy.py", "src/offline/case_signal_bridge.py"):
            tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            self.assertNotIn("CASE_TAGS", names, rel)


if __name__ == "__main__":
    unittest.main()
