#!/usr/bin/env python3
"""Bounded checks of the supplied Rule 30 flank claims; Python stdlib only.

Claims/write-up: Argon (Gemini, Google), as credited in the supplied blog.
Checker and documentation: Astra (OpenAI Codex); exact model ID unrecorded.
This is a separate implementation, not an independent human replication.
"""

import argparse
import hashlib
import json
from math import lcm
from pathlib import Path


MAX_DEPTH = 39
DIRECT_STEPS = 96


def rule30(p, q, r):
    """Wolfram's truth-table encoding, independent of the OR/XOR formula."""
    return (30 >> ((p << 2) | (q << 1) | r)) & 1


def strict_mask(p, q, r):
    """Flip each parent separately while fixing the other two parents."""
    child = rule30(p, q, r)
    return tuple(
        rule30(p ^ (slot == 0), q ^ (slot == 1), r ^ (slot == 2)) != child
        for slot in range(3)
    )


def cone(steps):
    """Exact infinite-zero-background cone; row t covers -t <= x <= t.

    Rule 30 has 000 -> 0, so omitted cells really remain zero. No finite
    wrapped boundary or fixed-width clipping enters this computation.
    """
    rows = [bytes([1])]
    for t in range(1, steps + 1):
        old = rows[-1]

        def previous(x):
            i = x + t - 1
            return old[i] if 0 <= i < len(old) else 0

        rows.append(bytes(
            rule30(previous(x - 1), previous(x), previous(x + 1))
            for x in range(-t, t + 1)
        ))
    return rows


def cone_cell(rows, t, x):
    return rows[t][x + t] if -t <= x <= t else 0


def moving_flank(steps, depth, side):
    """Both moving frames, including their initially out-of-cone zeros."""
    if side not in ("left", "right"):
        raise ValueError("side must be left or right")
    rows = [bytes([1] + [0] * depth)]
    for _ in range(steps):
        old = rows[-1]
        new = bytearray(depth + 1)
        for d in range(depth + 1):
            one = old[d - 1] if d >= 1 else 0
            two = old[d - 2] if d >= 2 else 0
            new[d] = (two ^ (one | old[d]) if side == "left"
                      else old[d] ^ (one | two))
        rows.append(bytes(new))
    return rows


def minimal_cycle(values):
    """Reduce a proven complete cycle using its shortest repeating block.

    KMP border calculation works for any nonempty finite word. It does not
    assume powers-of-two periods or infer periodicity from an observation.
    """
    if not values:
        raise ValueError("a cycle must be nonempty")
    borders = [0] * len(values)
    for i in range(1, len(values)):
        j = borders[i - 1]
        while j and values[i] != values[j]:
            j = borders[j - 1]
        if values[i] == values[j]:
            j += 1
        borders[i] = j
    period = len(values) - borders[-1]
    if len(values) % period:
        period = len(values)
    return bytes(values[:period])


def right_cycles(depth=MAX_DEPTH):
    """Construct exact time-zero cycles, inductively, through this depth.

    With the two parent cycles known, their joint period P is their lcm.
    The forcing OR is P-periodic. Integrating it in GF(2) returns the child
    to its initial zero after P steps if its parity is even, or 2P if odd.
    At that time the parents also repeat, proving a complete child cycle.
    Then reduce that cycle to its actual minimum rather than guessing it.
    """
    cycles = [bytes([1])]
    records = [{"depth": 0, "period": 1, "prefix_period": 1}]
    prefix_period = 1
    for d in range(1, depth + 1):
        one = cycles[d - 1]
        two = cycles[d - 2] if d >= 2 else bytes([0])
        parent_period = lcm(len(one), len(two))
        forcing = bytes(one[t % len(one)] | two[t % len(two)]
                        for t in range(parent_period))
        parity = sum(forcing) % 2
        complete_length = parent_period * (1 + parity)
        values = bytearray(complete_length)
        current = 0
        for t in range(complete_length):
            values[t] = current
            current ^= forcing[t % parent_period]
        if current != 0:
            raise AssertionError("constructed cycle did not close")
        cycle = minimal_cycle(values)
        cycles.append(cycle)
        prefix_period = lcm(prefix_period, len(cycle))
        records.append({
            "depth": d,
            "parent_joint_period": parent_period,
            "forcing_ones": sum(forcing),
            "forcing_parity": parity,
            "degree_3_steps_in_parent_cycle": parent_period - sum(forcing),
            "period": len(cycle),
            "prefix_period": prefix_period,
        })
    return cycles, records


def report():
    neighborhoods = []
    for code in range(8):
        p, q, r = code >> 2, (code >> 1) & 1, code & 1
        mask = strict_mask(p, q, r)
        if sum(mask) != 3 - q - r or rule30(p, q, r) != p ^ (q | r):
            raise AssertionError(f"local identity failed for {code:03b}")
        neighborhoods.append({"parents": f"{code:03b}", "child": rule30(p, q, r),
                              "strict_mask": list(mask), "degree": sum(mask)})

    direct = cone(DIRECT_STEPS)
    compared = 0
    for side in ("left", "right"):
        moving = moving_flank(DIRECT_STEPS, MAX_DEPTH, side)
        for t, row in enumerate(moving):
            for d, actual in enumerate(row):
                x = -t + d if side == "left" else t - d
                if actual != cone_cell(direct, t, x):
                    raise AssertionError(f"{side} mismatch at t={t}, d={d}")
                compared += 1

    cycles, records = right_cycles()
    for d, cycle in enumerate(cycles):
        for t in range(DIRECT_STEPS + 1):
            if cycle[t % len(cycle)] != cone_cell(direct, t, t - d):
                raise AssertionError(f"cycle/cone mismatch at t={t}, d={d}")
    # Include all time-zero bytes in order; this digest is an output artifact,
    # not an external oracle or proof of correctness.
    digest = hashlib.sha256(b"".join(cycles)).hexdigest()
    return {
        "schema_version": 1,
        "scope": "single live seed; infinite zero background; depths 0..39",
        "claims_source": "Argon (Gemini, Google), supplied two-flanks write-up",
        "checker_author": "Astra (OpenAI Codex); exact model ID unrecorded",
        "excluded": ["billion-step left-flank result", "browser UI verification",
                     "historical authorship or priority claims"],
        "neighborhoods": neighborhoods,
        "direct_crosscheck": {"steps": DIRECT_STEPS, "max_depth": MAX_DEPTH,
                              "flank_cells_compared": compared,
                              "right_cycle_cells_compared": (DIRECT_STEPS + 1) * (MAX_DEPTH + 1)},
        "right_diagonals": records,
        "right_cycle_bytes_sha256": digest,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write deterministic JSON here")
    args = parser.parse_args()
    output = json.dumps(report(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
