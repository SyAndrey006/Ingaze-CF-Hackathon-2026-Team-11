"""Tests for src/offline/case_signal_bridge.py (Step 2 vocabulary -> case-store enums)."""

import ast
import json
import unittest
from pathlib import Path

from src.offline.database_loader import load_normalized_cases
from src.offline.case_signal_bridge import (
    PROFILE_TO_SECTOR_PRIORITY,
    PROFILE_TO_WORKFORCE,
    TRACK_TAG_TO_SIGNALS,
    UNMAPPED_TRACK_TAGS,
    client_match_profile,
    sector_for_profile,
    signals_for_hypothesis_scopes,
    signals_for_track_tags,
    workforce_for_profile,
    workforce_from_role_text,
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

    def test_site_scoped_hypothesis_yields_site_asymmetry(self):
        hyps = [
            {"status": "plausible", "scope": {"cohort": None, "site": None}},
            {"status": "plausible", "scope": {"cohort": None, "site": "two_of_five_hubs"}},
        ]
        self.assertEqual(signals_for_hypothesis_scopes(hyps), {SignalCode.COHORT_OR_SITE_ASYMMETRY})
        signals, _, _ = client_match_profile([], [], hyps)
        self.assertIn(SignalCode.COHORT_OR_SITE_ASYMMETRY, signals)

    def test_unscoped_conflicted_or_cohort_only_yield_nothing(self):
        for hyp in (
            {"status": "plausible", "scope": {"site": "all"}},
            {"status": "plausible", "scope": {"site": " ALL "}},
            {"status": "plausible", "scope": {"site": ""}},
            {"status": "plausible", "scope": {"cohort": "engineering_workforce", "site": None}},
            {"status": "conflicted", "scope": {"site": "north_hub"}},
            {"status": "plausible"},
        ):
            self.assertEqual(signals_for_hypothesis_scopes([hyp]), set(), hyp)

    def test_workforce_target_beats_sector_profile(self):
        # A freight company hiring software engineers is a desk-based client.
        _, wf, sector = client_match_profile(
            [], ["freight", "distributed", "tech"],
            workforce_target="Senior Software Engineers and Data Engineers for the freight platform",
        )
        self.assertEqual(wf, [WorkforceArchetype.DESK_BASED_TECH_SPECIALIST])
        self.assertEqual(sector, SectorCategory.LOGISTICS_FREIGHT)
        _, wf, _ = client_match_profile(
            [], ["freight"], workforce_target="Licensed Commercial Truck Drivers and Warehouse Operators"
        )
        self.assertEqual(wf, [WorkforceArchetype.DESKLESS_FRONTLINE_LOGISTICS])

    def test_no_role_words_falls_back_to_profile(self):
        for target in (None, "", "120 urgent openings"):
            _, wf, _ = client_match_profile([], ["freight"], workforce_target=target)
            self.assertEqual(wf, [WorkforceArchetype.DESKLESS_FRONTLINE_LOGISTICS], target)

    def test_role_patterns_agree_with_curated_cases(self):
        # Every historical case that states its target talent must be detected with the
        # curated archetypes (MIXED_DISTRIBUTED comes from footprint, not from roles).
        sandbox = json.loads((REPO_ROOT / "database" / "ingaze_sandbox_dataset.json").read_text(encoding="utf-8"))
        curated = {c.case_name: c for c in load_normalized_cases(
            REPO_ROOT / "database" / "normalized" / "normalized_cases.json").cases}
        checked = 0
        for raw in sandbox["raw_case_study_narratives"]:
            profile = raw["sector_and_profile"]
            if "Target talent:" not in profile:
                continue
            detected = set(workforce_from_role_text(profile.split("Target talent:", 1)[1]))
            expected = set(curated[raw["case_name"]].workforce_archetypes) - {WorkforceArchetype.MIXED_DISTRIBUTED}
            self.assertEqual(detected, expected, raw["case_name"])
            checked += 1
        self.assertGreaterEqual(checked, 10)

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
