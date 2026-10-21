"""Regression and analytical checks for the preserved self-caused-silence model.

Authored by Astra (OpenAI). These tests exercise Claude's model; they are not an
independent implementation or evidence about real-world failure probabilities.
"""

import hashlib
import json
import math
from pathlib import Path
import runpy
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/self-caused-silence"
UPSTREAM = EXPERIMENT / "upstream"


class SelfCausedSilenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The runner copies the script before execution because upstream writes
        # results.json beside itself. The preserved source and fixture stay put.
        run = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/reproduce.py")],
            check=True,
            capture_output=True,
            text=True,
            timeout=70,
        )
        cls.actual = json.loads(run.stdout)
        cls.recorded = json.loads((UPSTREAM / "results.json").read_text())
        cls.model = runpy.run_path(str(UPSTREAM / "self_caused_silence.py"))

    def test_preserved_inputs_match_recorded_source_hashes(self):
        provenance = json.loads((EXPERIMENT / "provenance.json").read_text())
        for record in provenance["files"]:
            with self.subTest(path=record["path"]):
                digest = hashlib.sha256((EXPERIMENT / record["path"]).read_bytes()).hexdigest()
                self.assertEqual(digest, record["sha256"])

    def test_regenerated_results_match_the_complete_recorded_fixture(self):
        # Upstream rounds to 12 significant figures before serializing. Compare
        # that complete published representation, rather than exact raw floats.
        self.assertEqual(self.actual, self.recorded)

    def test_opportunity_accounting_eliminates_living_releases_in_finite_universe(self):
        result = self.actual["part_a"]
        counts = {"timeout": 445, "any_route_open_at_end": 445,
                  "announced_open_at_end": 104, "certified_opportunity": 0}
        for policy, living_releases in counts.items():
            with self.subTest(policy=policy):
                self.assertEqual(result[policy]["cases"], 13122)
                self.assertEqual(result[policy]["living_releases"], living_releases)
        self.assertEqual(result["certified_opportunity"]["unearned_credits"], 0)
        self.assertGreater(result["certified_opportunity"]["dead_releases"], 0)

    def test_equal_route_uptime_can_have_different_response_opportunities(self):
        usable = self.model["usable"]
        a, b = {"A"}, {"B"}
        self.assertTrue(usable((a, a, b, b), {"A", "B"}))
        self.assertFalse(usable((a, b, a, b), {"A", "B"}))

    def test_naive_threshold_erasure_matches_independent_closed_form(self):
        probability = self.model["living_false_release"]
        horizon = 40
        for p in (0.002, 0.08, 0.21):
            for threshold in (2, 4, 8):
                with self.subTest(p=p, threshold=threshold):
                    observed = probability("naive", p, p, 1, threshold, None, 0.0, horizon)
                    # The first missed response permanently blocks recovery.
                    # It causes release iff it arrives with M-1 windows left.
                    expected = 1 - (1 - p) ** (horizon - threshold + 1)
                    self.assertTrue(math.isclose(observed, expected, rel_tol=1e-12, abs_tol=1e-12))

    def test_reserved_channel_matches_no_lock_even_for_bursty_absences(self):
        probability = self.model["living_false_release"]
        for enter, stay in ((0.05, 0.05), (0.01, 0.8)):
            for lock_length, alternate_recovery in ((None, 0.0), (30, 0.25)):
                with self.subTest(enter=enter, stay=stay, lock_length=lock_length):
                    args = (enter, stay, 7, 30, lock_length, alternate_recovery, 365)
                    self.assertTrue(math.isclose(
                        probability("reserved", *args), probability("nolock", *args),
                        rel_tol=1e-12, abs_tol=1e-12,
                    ))

    def test_censoring_tradeoffs_and_broken_lock_negative_control(self):
        delay = self.model["dead_release_delay"]
        for policy in ("nolock", "naive", "reserved"):
            self.assertEqual(delay(policy, 7, 30, 30), 30)
        self.assertEqual(delay("censored", 7, 30, 30), 60)
        self.assertIsNone(delay("censored", 7, 30, None))
        self.assertIsNone(self.model["dead_delay_level_triggered"](7, 30, 30))

    def test_reported_independent_window_property_checks_pass(self):
        properties = self.actual["part_b"]["property_checks_independent_windows"]
        self.assertEqual(properties["cases"], 12)
        self.assertEqual(properties["violations"], [])


if __name__ == "__main__":
    unittest.main()
