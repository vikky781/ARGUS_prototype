"""Ingest's own authoritative view of docs/contracts.md's canonical schema —
kept independent of argus.synth's internals, since this is what ingest is
contractually required to produce regardless of how any raw source is shaped.
"""
from __future__ import annotations

CANONICAL_FIELDS = [
    "txid",
    "timestamp",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "geo_country",
    "asn",
    "input_addresses",
    "input_amounts",
    "output_addresses",
    "output_amounts",
    "fee",
    "script_type",
]
ARRAY_FIELDS = {"input_addresses", "input_amounts", "output_addresses", "output_amounts"}
AMOUNT_ARRAY_FIELDS = {"input_amounts", "output_amounts"}
INT_FIELDS = {"src_port", "dst_port", "asn"}
