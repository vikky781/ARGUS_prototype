import random

import pandas as pd

from argus.er.union_find import resolve_entities, write_entities_parquet
from argus.features.build import compute_node_features
from argus.graph.build import build_graph
from argus.ingest.pipeline import run_ingest
from argus.synth.config import SynthConfig
from argus.synth.corrupt import inject_corruption
from argus.synth.entities import generate_entities
from argus.synth.export import write_csv
from argus.synth.patterns import generate_illicit_patterns
from argus.synth.transactions import generate_transactions
from argus.synth.wallets import generate_wallets


def _feature_table(tmp_path, seed: int = 5):
    cfg = SynthConfig(
        random_seed=seed,
        num_entities=100,
        num_wallets=500,
        num_transactions=800,
        ip_noise=0.05,
        heuristic_break_rate=0.1,
        mixer_fraction=0.05,
    )
    rng = random.Random(cfg.random_seed)
    entities = generate_entities(cfg, rng)
    wallets = generate_wallets(cfg, rng, entities)
    baseline = generate_transactions(cfg, rng, entities, wallets)
    pattern_rows, _ = generate_illicit_patterns(cfg, rng, entities, wallets)
    corrupted = inject_corruption(baseline, rng)
    all_rows = corrupted + pattern_rows

    csv_path = tmp_path / "transactions.csv"
    write_csv(all_rows, csv_path)
    df = run_ingest(csv_path, "csv", tmp_path / "rejects.log")

    g = build_graph(df)
    uf, _ = resolve_entities(df)
    entities_path = tmp_path / "entities.parquet"
    write_entities_parquet(uf, entities_path)
    resolved_entities = pd.read_parquet(entities_path)

    return compute_node_features(g, df, resolved_entities), g


def test_no_nans_in_any_f_column(tmp_path):
    features, _ = _feature_table(tmp_path)
    f_cols = [c for c in features.columns if c.startswith("f_")]
    assert f_cols
    assert features[f_cols].isna().sum().sum() == 0


def test_sane_ranges(tmp_path):
    features, _ = _feature_table(tmp_path)

    assert (features["f_degree_total"] >= 0).all()
    assert (features["f_degree_in"] >= 0).all()
    assert (features["f_degree_out"] >= 0).all()
    assert (features["f_fan_in"] >= 0).all()
    assert (features["f_fan_out"] >= 0).all()
    assert (features["f_temporal_tx_count"] >= 0).all()
    assert (features["f_geo_hop_rate"] >= 0).all()
    assert (features["f_geo_hop_rate"] <= 1).all()
    assert (features["f_entity_asn_entropy"] >= 0).all()
    # burstiness (Goh & Barabási) is bounded in [-1, 1] by construction
    assert (features["f_temporal_burstiness"] >= -1).all()
    assert (features["f_temporal_burstiness"] <= 1).all()
    # fan-in/out never exceed raw degree (fan counts distinct neighbors only)
    assert (features["f_fan_in"] <= features["f_degree_in"]).all()
    assert (features["f_fan_out"] <= features["f_degree_out"]).all()


def test_row_count_matches_graph_node_count(tmp_path):
    features, g = _feature_table(tmp_path)
    assert len(features) == g.vcount()
    assert set(features["node_id"]) == set(g.vs["name"])
