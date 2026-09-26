"""Evaluation harness: reproduces every metric from the ER (Phase 2), pattern
detector (Phase 3), and risk (Phase 3) prompts in one run, as a single summary
table — using the artifacts already produced by `make pipeline`
(data/canonical, data/artifacts/graph.pkl, data/ground_truth). Does NOT
regenerate the dataset; run `make pipeline` first if artifacts are stale.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from argus.eval.metrics import er_metrics, pattern_metrics, risk_metrics
from argus.graph.export import read_graph_pickle


def run_full_summary(data_dir: Path) -> pd.DataFrame:
    canonical_df = pd.read_parquet(data_dir / "canonical" / "transactions.parquet")
    ground_truth_entities = pd.read_parquet(data_dir / "ground_truth" / "entities.parquet")
    ground_truth_patterns = pd.read_parquet(data_dir / "ground_truth" / "patterns.parquet")
    seeds = pd.read_parquet(data_dir / "ground_truth" / "seeds.parquet")
    g = read_graph_pickle(data_dir / "artifacts" / "graph.pkl")

    metrics: dict = {}
    metrics.update(er_metrics(canonical_df, ground_truth_entities))
    metrics.update(pattern_metrics(g, ground_truth_patterns))
    metrics.update(risk_metrics(g, seeds["wallet_id"].tolist(), ground_truth_entities))

    return pd.DataFrame([{"metric": k, "value": v} for k, v in metrics.items()])
