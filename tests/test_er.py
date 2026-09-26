import random

import pandas as pd

from argus.er.evaluate import evaluate_pairwise
from argus.er.union_find import UnionFind, resolve_entities
from argus.ingest.pipeline import run_ingest
from argus.synth.config import SynthConfig
from argus.synth.corrupt import inject_corruption
from argus.synth.entities import generate_entities
from argus.synth.export import write_csv
from argus.synth.patterns import generate_illicit_patterns
from argus.synth.transactions import generate_transactions
from argus.synth.wallets import generate_wallets


def test_union_find_merge_correctness():
    uf = UnionFind(["a", "b", "c", "d"])
    uf.union("a", "b")
    uf.union("c", "d")
    groups = uf.groups()
    assert len(groups) == 2
    assert sorted(sorted(g) for g in groups.values()) == [["a", "b"], ["c", "d"]]

    uf.union("b", "c")
    groups = uf.groups()
    assert len(groups) == 1
    assert sorted(next(iter(groups.values()))) == ["a", "b", "c", "d"]


def _dataset_with_patterns(tmp_path, seed: int = 17):
    cfg = SynthConfig(
        random_seed=seed,
        num_entities=300,
        num_wallets=3000,
        num_transactions=1000,
        ip_noise=0.05,
        heuristic_break_rate=0.0,  # keep CoinJoin outputs perfectly equal for this test
        mixer_fraction=0.05,
    )
    rng = random.Random(cfg.random_seed)
    entities = generate_entities(cfg, rng)
    wallets = generate_wallets(cfg, rng, entities)
    baseline = generate_transactions(cfg, rng, entities, wallets)
    pattern_rows, patterns = generate_illicit_patterns(cfg, rng, entities, wallets)
    corrupted_baseline = inject_corruption(baseline, rng)
    all_rows = corrupted_baseline + pattern_rows

    csv_path = tmp_path / "transactions.csv"
    write_csv(all_rows, csv_path)
    rejects_path = tmp_path / "rejects.log"
    df = run_ingest(csv_path, "csv", rejects_path)
    return df, entities, wallets, patterns


def test_coinjoin_guard_prevents_over_merge(tmp_path):
    df, entities, wallets, patterns = _dataset_with_patterns(tmp_path)
    coinjoin_patterns = [p for p in patterns if p.type == "coinjoin"]
    assert coinjoin_patterns

    uf, _ = resolve_entities(df)

    for pattern in coinjoin_patterns:
        roots = {uf.find(w) for w in pattern.wallets if w in uf}
        # The structural guard must have stopped heuristic 1 from fusing this
        # round's many distinct participants into one cluster.
        assert len(roots) > 1


def test_pairwise_precision_on_full_dataset(tmp_path):
    df, entities, wallets, _ = _dataset_with_patterns(tmp_path)
    uf, _ = resolve_entities(df)

    rows = [
        {"wallet_id": wallet_id, "entity_id": f"resolved_{root}"}
        for root, members in uf.groups().items()
        for wallet_id in members
    ]
    predicted = pd.DataFrame(rows)
    resolved_ids = set(predicted["wallet_id"])

    ground_truth = pd.DataFrame(
        [{"wallet_id": w.wallet_id, "entity_id": w.entity_id} for w in wallets if w.wallet_id in resolved_ids]
    )

    metrics = evaluate_pairwise(predicted, ground_truth)
    assert metrics["precision"] >= 0.95
