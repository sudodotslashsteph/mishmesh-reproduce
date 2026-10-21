"""Scientific regression checks for the bounded Rule 30 reproduction."""

import importlib.util
import json
from math import lcm
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "rule30_reproduction", ROOT / "experiments" / "rule30-flanks" / "reproduce.py")
ca = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ca)


class Rule30Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.direct = ca.cone(96)
        cls.cycles, cls.records = ca.right_cycles(39)

    def test_all_eight_truth_table_counterfactuals(self):
        for code in range(8):
            p, q, r = code >> 2, (code >> 1) & 1, code & 1
            with self.subTest(parents=f"{code:03b}"):
                self.assertEqual(ca.rule30(p, q, r), p ^ (q | r))
                self.assertEqual(ca.strict_mask(p, q, r), (True, not r, not q))
                self.assertEqual(sum(ca.strict_mask(p, q, r)), 3 - q - r)

    def test_both_moving_frames_match_direct_cone_including_background(self):
        for side in ("left", "right"):
            moving = ca.moving_flank(96, 39, side)
            for t, row in enumerate(moving):
                for d, value in enumerate(row):
                    x = -t + d if side == "left" else t - d
                    self.assertEqual(value, ca.cone_cell(self.direct, t, x),
                                     (side, t, d, x))

    def test_exact_cycles_match_separate_truth_table_simulation(self):
        for d, cycle in enumerate(self.cycles):
            for t in range(97):
                self.assertEqual(cycle[t % len(cycle)],
                                 ca.cone_cell(self.direct, t, t - d), (t, d))

    def test_complete_cycles_close_and_obey_recurrence_at_every_phase(self):
        for d in range(1, 40):
            current, one = self.cycles[d], self.cycles[d - 1]
            two = self.cycles[d - 2] if d >= 2 else bytes([0])
            joint = lcm(len(current), len(one), len(two))
            self.assertEqual(current[0], 0)
            for t in range(joint):
                self.assertEqual(current[(t + 1) % len(current)],
                                 current[t % len(current)] ^
                                 (one[t % len(one)] | two[t % len(two)]), (d, t))

    def test_minimality_independent_of_border_algorithm(self):
        for d, cycle in enumerate(self.cycles):
            n = len(cycle)
            self.assertEqual(n & (n - 1), 0, d)
            # Every proper divisor of a power of two divides n/2. If the
            # two halves differ, no smaller repeating block can exist.
            if n > 1:
                self.assertNotEqual(cycle[:n // 2], cycle[n // 2:], d)
        for word, expected in [(b"abcabc", b"abc"), (b"aaaa", b"a"),
                               (b"ababa", b"ababa"), (b"0", b"0")]:
            self.assertEqual(ca.minimal_cycle(word), expected)

    def test_all_published_right_flank_anchors(self):
        # Fixed claims transcribed from the supplied Argon report. These
        # are input expectations, never computed by the algorithm under test.
        anchors = {1: (2, 0), 3: (4, 1), 4: (8, 1), 6: (16, 3),
                   7: (32, 5), 9: (64, 11), 15: (128, 23), 16: (256, 35),
                   24: (512, 69), 25: (1024, 131), 39: (65536, 8263)}
        for d, (period, degree3) in anchors.items():
            with self.subTest(depth=d):
                result = self.records[d]
                self.assertEqual(result["period"], period)
                self.assertEqual(result["prefix_period"], period)
                self.assertEqual(self.records[d - 1]["prefix_period"] * 2, period)
                self.assertEqual(result["degree_3_steps_in_parent_cycle"], degree3)
                self.assertEqual(result["parent_joint_period"], period // 2)
                self.assertEqual(result["forcing_parity"], 1)

    def test_published_results_match_fresh_complete_report(self):
        # Guard the committed, reader-facing artifact as well as the numeric
        # anchors: computed periods, phase digest, scope and counts must all
        # agree with a fresh run. The other tests establish the mathematics;
        # this one prevents an outdated published results file.
        saved_path = ROOT / "experiments" / "rule30-flanks" / "results.json"
        saved = json.loads(saved_path.read_text(encoding="utf-8"))
        self.assertEqual(ca.report(), saved,
                         "results.json is stale; review the change and regenerate it")

    def test_zero_transient_and_opening_background(self):
        self.assertEqual(self.cycles[0], bytes([1]))
        for d, cycle in enumerate(self.cycles[1:], start=1):
            # t < d/2 is outside the opposite edge; this is an initial
            # segment of the genuine cycle, not a discarded transient.
            for t in range((d + 1) // 2):
                self.assertEqual(cycle[t % len(cycle)], 0, (d, t))

    def test_negative_control_rejects_xor_in_place_of_or(self):
        # A common wrong rewrite yields Rule 150. Evolve it independently
        # on coordinates, then require the reference comparison to detect
        # its first disagreement at t=2, x=-1.
        wrong = {0: 1}
        mismatch = None
        for t in range(1, 5):
            wrong = {x: wrong.get(x - 1, 0) ^ wrong.get(x, 0) ^ wrong.get(x + 1, 0)
                     for x in range(-t, t + 1)}
            differences = [x for x in range(-t, t + 1)
                           if wrong[x] != ca.cone_cell(self.direct, t, x)]
            if differences:
                mismatch = (t, differences[0])
                break
        self.assertEqual(mismatch, (2, -1))
        self.assertEqual(ca.cone_cell(self.direct, 2, -1), 1)
        self.assertEqual(wrong[-1], 0)


if __name__ == "__main__":
    unittest.main()
