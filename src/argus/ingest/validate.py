"""Boundary validation for parsed-but-not-yet-canonical transaction rows.

The three reasons below are exactly the three corruption types
argus.synth.corrupt injects (see that module's docstring), so a row corrupted by
the synthetic generator is rejected here under the matching reason string,
letting ingestion tests target each one precisely.
"""
from __future__ import annotations

import re
from datetime import datetime

CHECKSUM_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def validate_and_coerce(row: dict) -> tuple[dict | None, str | None]:
    """Returns (coerced_row, None) if row passes, else (None, reason)."""
    if not CHECKSUM_PATTERN.match(row["txid"]):
        return None, "bad_checksum"

    try:
        timestamp = datetime.fromisoformat(row["timestamp"])
    except (ValueError, TypeError):
        return None, "bad_timestamp"

    input_amounts = [float(a) for a in row["input_amounts"]]
    output_amounts = [float(a) for a in row["output_amounts"]]
    fee = float(row["fee"])
    if any(a < 0 for a in (*input_amounts, *output_amounts, fee)):
        return None, "negative_amount"

    coerced = dict(row)
    coerced["timestamp"] = timestamp
    coerced["input_amounts"] = input_amounts
    coerced["output_amounts"] = output_amounts
    coerced["fee"] = fee
    return coerced, None
