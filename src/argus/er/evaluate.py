"""Pairwise precision/recall/F1 of a resolved clustering against ground truth.

Computed via cluster-size combinatorics (a contingency table between the two
clusterings), not by enumerating all O(n^2) wallet pairs directly — with 50,000
wallets that would be ~1.25 billion pairs. This is the standard efficient way to
compute pairwise clustering metrics: for two clusterings A and B,
    TP = sum over (a, b) contingency cells of C(|a ∩ b|, 2)
    TP + FP = sum over clusters a in A of C(|a|, 2)
    TP + FN = sum over clusters b in B of C(|b|, 2)
"""
from __future__ import annotations

import pandas as pd


def _pair_count(sizes: pd.Series) -> int:
    return int((sizes * (sizes - 1) // 2).sum())


def evaluate_pairwise(predicted: pd.DataFrame, ground_truth: pd.DataFrame) -> dict:
    """predicted/ground_truth: DataFrames with wallet_id, entity_id columns."""
    merged = predicted[["wallet_id", "entity_id"]].merge(
        ground_truth[["wallet_id", "entity_id"]],
        on="wallet_id",
        suffixes=("_pred", "_true"),
    )

    pred_sizes = merged.groupby("entity_id_pred").size()
    true_sizes = merged.groupby("entity_id_true").size()
    pair_sizes = merged.groupby(["entity_id_pred", "entity_id_true"]).size()

    tp = _pair_count(pair_sizes)
    predicted_pairs = _pair_count(pred_sizes)
    true_pairs = _pair_count(true_sizes)

    precision = tp / predicted_pairs if predicted_pairs else 1.0
    recall = tp / true_pairs if true_pairs else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp_pairs": tp,
        "predicted_pairs": predicted_pairs,
        "true_pairs": true_pairs,
    }
