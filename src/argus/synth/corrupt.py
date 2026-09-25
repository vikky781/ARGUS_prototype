"""Injects deliberate corruption into a copy of the generated transactions, so the
raw exports (CSV/JSON/XML) contain messy real-world-like rows for the ingestion
phase to detect and handle. Ground truth artifacts are never corrupted.

Exactly three corruption types are injected, round-robin across the corrupted rows,
so ingestion tests can target each one precisely:

1. "bad_checksum"     -> txid is replaced with f"{CORRUPT_CHECKSUM_PREFIX}{row_index}",
                          which violates the expected 64-char lowercase-hex txid format.
2. "negative_amount"  -> output_amounts[0] is negated (becomes < 0).
3. "bad_timestamp"    -> timestamp is replaced with the literal string
                          CORRUPT_TIMESTAMP_VALUE, which is not parseable as a date.

CORRUPTION_RATE of all rows are corrupted. Which rows, and which corruption type each
gets, is chosen via the shared seeded rng, so results are reproducible for a given
seed and the count matches CORRUPTION_RATE exactly rather than approximately.
"""
from __future__ import annotations

import copy
import random

CORRUPTION_RATE = 0.005
CORRUPT_CHECKSUM_PREFIX = "BADCHECKSUM_"
CORRUPT_TIMESTAMP_VALUE = "NOT-A-TIMESTAMP"
CORRUPTION_TYPES = ("bad_checksum", "negative_amount", "bad_timestamp")


def inject_corruption(transactions: list[dict], rng: random.Random) -> list[dict]:
    corrupted = copy.deepcopy(transactions)
    n = len(corrupted)
    num_corrupt = round(n * CORRUPTION_RATE)

    indices = list(range(n))
    rng.shuffle(indices)
    target_indices = indices[:num_corrupt]

    for slot, idx in enumerate(target_indices):
        corruption_type = CORRUPTION_TYPES[slot % len(CORRUPTION_TYPES)]
        row = corrupted[idx]
        if corruption_type == "bad_checksum":
            row["txid"] = f"{CORRUPT_CHECKSUM_PREFIX}{idx}"
        elif corruption_type == "negative_amount":
            row["output_amounts"][0] = -abs(row["output_amounts"][0])
        elif corruption_type == "bad_timestamp":
            row["timestamp"] = CORRUPT_TIMESTAMP_VALUE

    return corrupted
