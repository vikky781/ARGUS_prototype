"""Reusable metric computations for the Dev-A pipeline, shared by the main
evaluation harness (argus.eval.report) and the dual-layer ablation
(argus.eval.ablation). Each function re-runs the relevant detector directly
against a graph/dataframe rather than reading persisted scores_*.parquet
files, so results are always current and structured (chain/round objects,
not flattened rows) — cheap, since none of these detectors are slow.
"""
from __future__ import annotations

import igraph as ig
import pandas as pd

from argus.detectors.coinjoin import detect_coinjoin_rounds
from argus.detectors.peeling import detect_peeling_chains
from argus.detectors.risk_ppr import compute_risk_scores
from argus.er.evaluate import evaluate_pairwise
from argus.er.union_find import resolve_entities
from argus.synth.seeds import ILLICIT_TYPES

OVERLAP_THRESHOLD = 0.5


def er_metrics(canonical_df: pd.DataFrame, ground_truth_entities: pd.DataFrame) -> dict:
    uf, _ = resolve_entities(canonical_df)
    rows = [
        {"wallet_id": wallet_id, "entity_id": f"resolved_{root}"}
        for root, members in uf.groups().items()
        for wallet_id in members
    ]
    predicted = pd.DataFrame(rows, columns=["wallet_id", "entity_id"])
    result = evaluate_pairwise(predicted, ground_truth_entities)
    return {"er_precision": result["precision"], "er_recall": result["recall"], "er_f1": result["f1"]}


def _pairwise_recall_precision(detected_sets: list[set], ground_truth_sets: list[set]) -> tuple[float, float]:
    if not ground_truth_sets:
        return float("nan"), float("nan")
    gt_matched = sum(
        1
        for gt in ground_truth_sets
        if max((len(gt & d) / len(gt) for d in detected_sets), default=0) >= OVERLAP_THRESHOLD
    )
    det_matched = sum(
        1
        for d in detected_sets
        if max((len(gt & d) / len(gt) for gt in ground_truth_sets), default=0) >= OVERLAP_THRESHOLD
    )
    recall = gt_matched / len(ground_truth_sets)
    precision = det_matched / len(detected_sets) if detected_sets else float("nan")
    return recall, precision


def pattern_metrics(g: ig.Graph, ground_truth_patterns: pd.DataFrame) -> dict:
    gt_peeling = [set(row.txids) for row in ground_truth_patterns.itertuples(index=False) if row.type == "peeling"]
    gt_coinjoin = {row.txids[0] for row in ground_truth_patterns.itertuples(index=False) if row.type == "coinjoin"}

    chains = detect_peeling_chains(g)
    peel_recall, peel_precision = _pairwise_recall_precision([set(c.txids) for c in chains], gt_peeling)

    rounds = detect_coinjoin_rounds(g)
    detected_cj = {r.txid for r in rounds}
    cj_recall = len(detected_cj & gt_coinjoin) / len(gt_coinjoin) if gt_coinjoin else float("nan")
    cj_precision = len(detected_cj & gt_coinjoin) / len(detected_cj) if detected_cj else float("nan")

    return {
        "peeling_recall": peel_recall,
        "peeling_precision": peel_precision,
        "coinjoin_recall": cj_recall,
        "coinjoin_precision": cj_precision,
    }


def risk_metrics(g: ig.Graph, seed_wallets: list[str], ground_truth_entities: pd.DataFrame, k: int = 50) -> dict:
    scores = compute_risk_scores(g, seed_wallets)
    top_k = sorted(scores, key=lambda r: r.score, reverse=True)[:k]

    illicit = set(ground_truth_entities[ground_truth_entities["entity_type"].isin(ILLICIT_TYPES)]["wallet_id"])
    hits = sum(1 for r in top_k if r.node_id in illicit)
    precision_at_k = hits / len(top_k) if top_k else float("nan")
    return {f"risk_precision_at_{k}": precision_at_k}
