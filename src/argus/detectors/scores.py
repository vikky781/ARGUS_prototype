"""Converts peeling/coinjoin detector output into artifacts/scores_pattern.parquet
rows: node_id, score, reason_code, evidence_json — per docs/contracts.md's hard
rule that every head emits reason_code + evidence_json, no exceptions.

This artifact currently contains ONLY classical (structural) detections from
argus.detectors.peeling and argus.detectors.coinjoin. Dev B's
detectors/pattern_sim.py (embedding-similarity variant) would append MORE rows
to this SAME artifact later — not implemented in this repo. A node touched by
more than one detection (e.g. two different chains) gets one row per
detection, not a collapsed/deduplicated single row — evidence is never merged
away.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from argus.detectors.coinjoin import CoinjoinRound
from argus.detectors.peeling import PeelingChain


def peeling_chain_rows(chains: list[PeelingChain]) -> list[dict]:
    rows = []
    for chain in chains:
        reason_code = f"PEEL_CHAIN_HOPS={chain.hop_count}"
        evidence_json = json.dumps(
            {
                "chain_id": chain.chain_id,
                "hop_count": chain.hop_count,
                "txids": chain.txids,
                "wallets": chain.wallets,
            }
        )
        for node_id in (*chain.wallets, *chain.txids):
            rows.append(
                {"node_id": node_id, "score": chain.confidence, "reason_code": reason_code, "evidence_json": evidence_json}
            )
    return rows


def coinjoin_round_rows(rounds: list[CoinjoinRound]) -> list[dict]:
    rows = []
    for r in rounds:
        reason_code = f"COINJOIN_ROUND_N={r.participant_count}"
        evidence_json = json.dumps(
            {
                "txid": r.txid,
                "participant_count": r.participant_count,
                "denomination": r.denomination,
                "input_wallets": r.input_wallets,
                "output_wallets": r.output_wallets,
            }
        )
        score = r.equal_output_fraction
        node_ids = {r.txid, *r.input_wallets, *r.output_wallets}
        for node_id in node_ids:
            rows.append({"node_id": node_id, "score": score, "reason_code": reason_code, "evidence_json": evidence_json})
    return rows


def write_scores_pattern(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=["node_id", "score", "reason_code", "evidence_json"])
    df.to_parquet(path, index=False)
