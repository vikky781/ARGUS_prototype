import random

from argus.detectors.coinjoin import detect_coinjoin_rounds
from argus.detectors.peeling import detect_peeling_chains
from argus.graph.build import build_graph
from argus.ingest.pipeline import run_ingest
from argus.synth.config import SynthConfig
from argus.synth.corrupt import inject_corruption
from argus.synth.entities import generate_entities
from argus.synth.export import write_csv
from argus.synth.patterns import generate_illicit_patterns
from argus.synth.transactions import generate_transactions
from argus.synth.wallets import generate_wallets

OVERLAP_THRESHOLD = 0.5


def _dataset_with_graph(tmp_path, seed: int = 23):
    cfg = SynthConfig(
        random_seed=seed,
        num_entities=300,
        num_wallets=3000,
        num_transactions=3000,
        ip_noise=0.05,
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

    csv_path = tmp_path / "transactions.csv"
    write_csv(all_rows, csv_path)
    df = run_ingest(csv_path, "csv", tmp_path / "rejects.log")
    g = build_graph(df)
    return g, patterns


def _pairwise_recall_precision(detected_txid_sets, ground_truth_txid_sets):
    gt_matched = sum(
        1
        for gt in ground_truth_txid_sets
        if max((len(gt & d) / len(gt) for d in detected_txid_sets), default=0) >= OVERLAP_THRESHOLD
    )
    det_matched = sum(
        1
        for d in detected_txid_sets
        if max((len(gt & d) / len(gt) for gt in ground_truth_txid_sets), default=0) >= OVERLAP_THRESHOLD
    )
    recall = gt_matched / len(ground_truth_txid_sets) if ground_truth_txid_sets else 1.0
    precision = det_matched / len(detected_txid_sets) if detected_txid_sets else 1.0
    return recall, precision


def test_planted_peeling_chains_are_detected(tmp_path):
    g, patterns = _dataset_with_graph(tmp_path)
    gt_peeling = [set(p.txids) for p in patterns if p.type == "peeling"]
    assert gt_peeling

    chains = detect_peeling_chains(g)
    detected = [set(c.txids) for c in chains]

    recall, precision = _pairwise_recall_precision(detected, gt_peeling)
    assert recall >= 0.90, f"peeling recall {recall} below target"
    assert precision >= 0.85, f"peeling precision {precision} below target"


def test_planted_coinjoin_rounds_are_detected(tmp_path):
    g, patterns = _dataset_with_graph(tmp_path)
    gt_coinjoin_txids = {p.txids[0] for p in patterns if p.type == "coinjoin"}
    assert gt_coinjoin_txids

    rounds = detect_coinjoin_rounds(g)
    detected_txids = {r.txid for r in rounds}

    recall = len(detected_txids & gt_coinjoin_txids) / len(gt_coinjoin_txids)
    precision = len(detected_txids & gt_coinjoin_txids) / len(detected_txids) if detected_txids else 1.0
    assert recall >= 0.90, f"coinjoin recall {recall} below target"
    assert precision >= 0.85, f"coinjoin precision {precision} below target"
