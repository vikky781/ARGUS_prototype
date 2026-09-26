"""Dual-layer vs on-chain-only ablation, swept across ip_noise.

Re-runs ER/pattern/risk metrics with BROADCAST_VIA/RESOLVES_TO edges (the
network layer) dropped, and compares against the full dual-layer graph, at
several ip_noise values.

IMPORTANT — read before interpreting the results: as of this phase, NONE of
argus.er.union_find, argus.detectors.peeling, argus.detectors.coinjoin, or
argus.detectors.risk_ppr ever reads a BROADCAST_VIA or RESOLVES_TO edge, or
any node_features.parquet column — they operate purely on FUNDS/PAYS/CO_SPEND
edges and raw canonical amounts. This was verified directly (grep found zero
references) before writing this module. So this ablation is expected to show
ZERO measurable difference between the two conditions, at every noise level —
not because the network layer carries no signal, but because none of the
classical detectors implemented in this repo were ever wired to consume it.
That is the actual, honest finding; see the Phase 4 report for the numbers.

Uses a smaller, self-contained synth run per (noise, condition) cell rather
than the full 200k-transaction dataset: this sweep is 3 noise levels x 2
conditions = 6 full pipeline runs, and full scale would make that
prohibitively slow for what is fundamentally a methodology check, not the
headline numbers (`make eval`'s main summary already reports those at full
scale from the real `make pipeline` artifacts).
"""
from __future__ import annotations

import random
from pathlib import Path

import igraph as ig
import pandas as pd

from argus.eval.metrics import er_metrics, pattern_metrics, risk_metrics
from argus.graph.build import build_graph
from argus.ingest.pipeline import run_ingest
from argus.synth.config import SynthConfig
from argus.synth.corrupt import inject_corruption
from argus.synth.entities import generate_entities
from argus.synth.export import write_csv
from argus.synth.patterns import generate_illicit_patterns
from argus.synth.seeds import generate_seed_wallets
from argus.synth.transactions import generate_transactions
from argus.synth.wallets import generate_wallets

NOISE_LEVELS = {"low": 0.01, "medium": 0.05, "high": 0.20}

ABLATION_SEED = 71
ABLATION_NUM_ENTITIES = 500
ABLATION_NUM_WALLETS = 5000
ABLATION_NUM_TRANSACTIONS = 5000


def drop_network_layer(g: ig.Graph) -> ig.Graph:
    """The "on-chain-only" condition: removes BROADCAST_VIA/RESOLVES_TO edges.
    Nodes are kept (IP/ASN nodes become edgeless) — only the edges matter,
    since no detector here ever queries IP/ASN nodes directly either.
    """
    edge_ids = [e.index for e in g.es if e["type"] not in ("BROADCAST_VIA", "RESOLVES_TO")]
    return g.subgraph_edges(edge_ids, delete_vertices=False)


def _generate_dataset(ip_noise: float, tmp_dir: Path, label: str):
    cfg = SynthConfig(
        random_seed=ABLATION_SEED,
        num_entities=ABLATION_NUM_ENTITIES,
        num_wallets=ABLATION_NUM_WALLETS,
        num_transactions=ABLATION_NUM_TRANSACTIONS,
        ip_noise=ip_noise,
        heuristic_break_rate=0.1,
        mixer_fraction=0.05,
    )
    rng = random.Random(cfg.random_seed)
    entities = generate_entities(cfg, rng)
    wallets = generate_wallets(cfg, rng, entities)
    baseline = generate_transactions(cfg, rng, entities, wallets)
    pattern_rows, patterns = generate_illicit_patterns(cfg, rng, entities, wallets)
    corrupted_baseline = inject_corruption(baseline, rng)
    all_rows = corrupted_baseline + pattern_rows
    seed_wallets = generate_seed_wallets(rng, entities, wallets)

    csv_path = tmp_dir / f"transactions_{label}.csv"
    write_csv(all_rows, csv_path)
    canonical_df = run_ingest(csv_path, "csv", tmp_dir / f"rejects_{label}.log")

    entities_by_id = {e.entity_id: e.entity_type for e in entities}
    ground_truth_entities = pd.DataFrame(
        [
            {"wallet_id": w.wallet_id, "entity_id": w.entity_id, "entity_type": entities_by_id[w.entity_id]}
            for w in wallets
        ]
    )
    ground_truth_patterns = pd.DataFrame(
        [{"pattern_id": p.pattern_id, "type": p.type, "txids": p.txids, "wallets": p.wallets} for p in patterns]
    )

    return canonical_df, ground_truth_entities, ground_truth_patterns, seed_wallets


def run_ablation_sweep(tmp_dir: Path) -> pd.DataFrame:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for label, ip_noise in NOISE_LEVELS.items():
        canonical_df, ground_truth_entities, ground_truth_patterns, seed_wallets = _generate_dataset(
            ip_noise, tmp_dir, label
        )
        g_full = build_graph(canonical_df)
        g_onchain = drop_network_layer(g_full)

        for condition, g in (("dual_layer", g_full), ("on_chain_only", g_onchain)):
            metrics: dict = {}
            metrics.update(er_metrics(canonical_df, ground_truth_entities))
            metrics.update(pattern_metrics(g, ground_truth_patterns))
            metrics.update(risk_metrics(g, seed_wallets, ground_truth_entities))
            rows.append({"noise_level": label, "ip_noise": ip_noise, "condition": condition, **metrics})

    return pd.DataFrame(rows)
