import pickle
import random
from pathlib import Path

from argus.graph.build import build_graph
from argus.ingest.pipeline import run_ingest
from argus.synth.config import SynthConfig
from argus.synth.corrupt import inject_corruption
from argus.synth.entities import generate_entities
from argus.synth.export import write_csv
from argus.synth.transactions import generate_transactions
from argus.synth.wallets import generate_wallets


def _small_canonical_df(tmp_path: Path, seed: int = 11):
    cfg = SynthConfig(random_seed=seed, num_entities=20, num_wallets=100, num_transactions=1000, ip_noise=0.1)
    rng = random.Random(cfg.random_seed)
    entities = generate_entities(cfg, rng)
    wallets = generate_wallets(cfg, rng, entities)
    transactions = generate_transactions(cfg, rng, entities, wallets)
    corrupted = inject_corruption(transactions, rng)

    csv_path = tmp_path / "transactions.csv"
    write_csv(corrupted, csv_path)
    rejects_path = tmp_path / "rejects.log"
    return run_ingest(csv_path, "csv", rejects_path)


def test_node_counts_match_ingestion(tmp_path):
    df = _small_canonical_df(tmp_path)
    g = build_graph(df)

    expected_wallets = set()
    for col in ("input_addresses", "output_addresses"):
        for arr in df[col]:
            expected_wallets.update(arr)
    expected_ips = set(df["src_ip"])

    counts = {}
    for t in g.vs["type"]:
        counts[t] = counts.get(t, 0) + 1

    assert counts["Wallet"] == len(expected_wallets)
    assert counts["Transaction"] == len(df)
    assert counts["IP"] == len(expected_ips)


def test_transaction_edge_invariants(tmp_path):
    df = _small_canonical_df(tmp_path)
    g = build_graph(df)

    for v in g.vs.select(type_eq="Transaction"):
        in_types = [g.es[e]["type"] for e in g.incident(v.index, mode="in")]
        out_types = [g.es[e]["type"] for e in g.incident(v.index, mode="out")]
        assert in_types.count("FUNDS") >= 1
        assert out_types.count("PAYS") >= 1
        assert out_types.count("BROADCAST_VIA") == 1


def test_ip_nodes_have_resolves_to(tmp_path):
    df = _small_canonical_df(tmp_path)
    g = build_graph(df)

    for v in g.vs.select(type_eq="IP"):
        out_types = [g.es[e]["type"] for e in g.incident(v.index, mode="out")]
        assert out_types.count("RESOLVES_TO") == 1


def test_pickle_roundtrip(tmp_path):
    df = _small_canonical_df(tmp_path)
    g = build_graph(df)

    path = tmp_path / "graph.pkl"
    with open(path, "wb") as f:
        pickle.dump(g, f)
    with open(path, "rb") as f:
        g2 = pickle.load(f)

    assert g2.vcount() == g.vcount()
    assert g2.ecount() == g.ecount()
    assert g2.vs["name"] == g.vs["name"]
    assert g2.vs["type"] == g.vs["type"]
    assert g2.es["type"] == g.es["type"]
