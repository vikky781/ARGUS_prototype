"""Placeholder for Dev B's models/anomaly.py (graph autoencoder), out of scope
in this repo per CLAUDE.md.

THIS IS NOT A REAL ANOMALY MODEL — it exists only so blend.py has a
contract-valid input until Dev B's models/anomaly.py replaces it. Every node
gets the same fixed neutral score (0.5): "no information either way" on a
[0,1] scale, chosen because it is also self-correcting — a constant feature
has zero variance, so blend.py's logistic-calibration path automatically
learns to give it ~zero weight rather than needing to be told to ignore it.
See docs/contracts.md's scores_anomaly.parquet section for the same note.
"""
from __future__ import annotations

import json
from pathlib import Path

import igraph as ig
import pandas as pd

PLACEHOLDER_SCORE = 0.5
PLACEHOLDER_REASON_CODE = "ANOMALY_PLACEHOLDER"
PLACEHOLDER_NOTE = "not a real anomaly model — fixed neutral placeholder pending Dev B's models/anomaly.py"


def write_anomaly_placeholder(g: ig.Graph, path: Path) -> None:
    evidence_json = json.dumps({"note": PLACEHOLDER_NOTE})
    rows = [
        {
            "node_id": name,
            "score": PLACEHOLDER_SCORE,
            "reason_code": PLACEHOLDER_REASON_CODE,
            "evidence_json": evidence_json,
        }
        for name in g.vs["name"]
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["node_id", "score", "reason_code", "evidence_json"]).to_parquet(path, index=False)
