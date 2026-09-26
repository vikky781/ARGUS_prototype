"""Calibrated fusion of the three score heads into artifacts/alerts.json.

This is the one place Dev A's scope hard-depends on Dev B's missing work: the
anomaly score. scores_anomaly.parquet is produced by
argus.fusion._anomaly_placeholder, NOT by a real model — see that module's
docstring and docs/contracts.md.

Rationale strings here are a simple, fixed template built from reason_codes
(architecture-doc §4.4 style) — NOT the full rationale-templating engine,
which is Dev B's detectors/rationale.py, out of scope in this repo.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression

from argus.fusion._anomaly_placeholder import PLACEHOLDER_SCORE

ILLICIT_TYPES = ("ransomware", "darknet", "mixer")

# Below this many labeled nodes (or with only one class present), a 3-feature
# logistic regression is more likely to overfit/degenerate than to calibrate
# anything meaningful — fall back to a fixed blend instead.
MIN_LABELED_NODES = 30

# Fallback weights when calibration can't be trained. Pattern and risk carry
# real structural signal; anomaly is a known-constant placeholder, so it gets
# a small, harmless residual weight — a constant term added to every score
# doesn't change any two nodes' RELATIVE ranking, but the weight is already
# correct and nonzero for the day a real anomaly score replaces the constant.
FALLBACK_WEIGHTS = {"pattern": 0.5, "risk": 0.4, "anomaly": 0.1}

# Tuned against the real fused-score distribution, which turned out bimodal:
# nodes flagged ONLY by a pattern detector (real peeling/coinjoin structure)
# cluster near 0.67; nodes flagged ONLY by the risk head (currently just the
# seed set itself, per risk_ppr.py's documented CO_SPEND=0 limitation)
# cluster near 0.9998 — with nothing in between. A threshold ABOVE ~0.67
# would perversely keep the seed-echo cluster while dropping the real
# structural detections, which is backwards. Set below the low cluster, this
# threshold keeps the entire fusion universe (every node with ANY pattern or
# risk signal) as the alert list — ~2,249 of ~343,000 total graph nodes
# (~0.65%) on the full dataset, already a curated, reasonably-sized watchlist
# by construction (component_table only considers nodes with SOME signal).
ALERT_THRESHOLD = 0.6


def component_table(scores_pattern: pd.DataFrame, scores_risk: pd.DataFrame, scores_anomaly: pd.DataFrame) -> pd.DataFrame:
    """One row per node with ANY pattern or risk signal. The anomaly
    placeholder alone (being constant across every graph node) is never a
    reason to consider a node — including it would blow up the fusion
    universe to ~340k trivial rows for zero benefit.
    """
    pattern_max = scores_pattern.groupby("node_id")["score"].max().rename("pattern")
    risk_max = scores_risk.groupby("node_id")["score"].max().rename("risk")
    universe = pattern_max.index.union(risk_max.index)

    anomaly_by_node = scores_anomaly.set_index("node_id")["score"]

    table = pd.DataFrame(index=universe)
    table["pattern"] = pattern_max.reindex(universe).fillna(0.0)
    table["risk"] = risk_max.reindex(universe).fillna(0.0)
    table["anomaly"] = anomaly_by_node.reindex(universe).fillna(PLACEHOLDER_SCORE)
    return table.reset_index(names="node_id")


def _labeled_rows(table: pd.DataFrame, ground_truth_entities: pd.DataFrame) -> pd.DataFrame:
    labels = ground_truth_entities[["wallet_id", "entity_type"]].rename(columns={"wallet_id": "node_id"})
    labels["label"] = labels["entity_type"].isin(ILLICIT_TYPES).astype(int)
    return table.merge(labels[["node_id", "label"]], on="node_id", how="inner")


def _fit_calibrated_blend(labeled: pd.DataFrame) -> LogisticRegression | None:
    if len(labeled) < MIN_LABELED_NODES or labeled["label"].nunique() < 2:
        return None
    model = LogisticRegression()
    model.fit(labeled[["pattern", "risk", "anomaly"]].to_numpy(), labeled["label"].to_numpy())
    return model


def compute_final_scores(table: pd.DataFrame, ground_truth_entities: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Trains a calibrated logistic blend on synthetic labels from
    ground_truth/entities.parquet when enough labeled nodes exist (>=
    MIN_LABELED_NODES, both classes present); otherwise falls back to a fixed
    weighted average. Both paths are implemented and exercised by tests —
    which one runs depends on the data, not a flag.
    """
    labeled = _labeled_rows(table, ground_truth_entities)
    model = _fit_calibrated_blend(labeled)

    table = table.copy()
    if model is not None:
        table["final_score"] = model.predict_proba(table[["pattern", "risk", "anomaly"]].to_numpy())[:, 1]
        method = "calibrated_logistic"
    else:
        table["final_score"] = (
            FALLBACK_WEIGHTS["pattern"] * table["pattern"]
            + FALLBACK_WEIGHTS["risk"] * table["risk"]
            + FALLBACK_WEIGHTS["anomaly"] * table["anomaly"]
        )
        method = "fallback_weighted_average"
    return table, method


def _extract_evidence(reason_code: str, evidence: dict) -> tuple[list[str], list[tuple[str, str]]]:
    if reason_code.startswith("PEEL_CHAIN_HOPS"):
        wallets = evidence.get("wallets", [])
        txids = evidence.get("txids", [])
        return [*wallets, *txids], list(zip(wallets[:-1], wallets[1:]))
    if reason_code.startswith("COINJOIN_ROUND_N"):
        txid = evidence["txid"]
        inputs = evidence.get("input_wallets", [])
        outputs = evidence.get("output_wallets", [])
        edges = [(w, txid) for w in inputs] + [(txid, w) for w in outputs]
        return [txid, *inputs, *outputs], edges
    if reason_code.startswith("SEED_DIST"):
        path = evidence.get("path", [])
        return path, list(zip(path[:-1], path[1:]))
    return [], []


def _rationale(node_id: str, final_score: float, reason_codes: list[str]) -> str:
    clauses = []
    for rc in sorted(set(reason_codes)):
        if rc.startswith("PEEL_CHAIN_HOPS="):
            clauses.append(f"part of a peeling chain with {rc.split('=')[1]} hops")
        elif rc.startswith("COINJOIN_ROUND_N="):
            clauses.append(f"a participant in a CoinJoin round with {rc.split('=')[1]} participants")
        elif rc.startswith("SEED_DIST="):
            n = rc.split("=")[1]
            clauses.append("a known-illicit seed wallet" if n == "0" else f"{n} hop(s) from a known-illicit seed")
        else:
            clauses.append(rc)
    body = "; ".join(clauses) if clauses else "no specific structural signal"
    return f"{node_id} flagged (confidence {final_score:.2f}). {body[0].upper() + body[1:]}."


def build_alerts(
    final_table: pd.DataFrame, scores_pattern: pd.DataFrame, scores_risk: pd.DataFrame, threshold: float
) -> list[dict]:
    reasons_by_node: dict[str, list[tuple[str, dict]]] = {}
    for source in (scores_pattern, scores_risk):
        for row in source.itertuples(index=False):
            reasons_by_node.setdefault(row.node_id, []).append((row.reason_code, json.loads(row.evidence_json)))

    flagged = final_table[final_table["final_score"] >= threshold].sort_values("final_score", ascending=False)

    alerts = []
    for i, row in enumerate(flagged.itertuples(index=False)):
        node_reasons = reasons_by_node.get(row.node_id, [])
        reason_codes = [rc for rc, _ in node_reasons]

        nodes_ev: set[str] = {row.node_id}
        edges_ev: set[tuple[str, str]] = set()
        for rc, ev in node_reasons:
            ns, es = _extract_evidence(rc, ev)
            nodes_ev.update(ns)
            edges_ev.update(es)

        alerts.append(
            {
                "alert_id": f"alert_{i:05d}",
                "node_id": row.node_id,
                "final_score": float(row.final_score),
                "components": {"pattern": float(row.pattern), "risk": float(row.risk), "anomaly": float(row.anomaly)},
                "evidence": {"nodes": sorted(nodes_ev), "edges": sorted(list(e) for e in edges_ev)},
                "rationale": _rationale(row.node_id, row.final_score, reason_codes),
            }
        )
    return alerts


def write_alerts(alerts: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2)
