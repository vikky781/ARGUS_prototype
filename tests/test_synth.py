import random
from collections import Counter

from argus.synth.config import SynthConfig
from argus.synth.corrupt import CORRUPTION_RATE, inject_corruption
from argus.synth.entities import generate_entities
from argus.synth.patterns import generate_illicit_patterns
from argus.synth.seeds import ILLICIT_TYPES, generate_seed_wallets
from argus.synth.transactions import generate_transactions
from argus.synth.wallets import generate_wallets


def _small_config(seed: int = 123) -> SynthConfig:
    return SynthConfig(
        random_seed=seed,
        num_entities=50,
        num_wallets=300,
        num_transactions=2000,
        ip_noise=0.1,
        heuristic_break_rate=0.1,
        mixer_fraction=0.02,
    )


def _run(cfg: SynthConfig):
    rng = random.Random(cfg.random_seed)
    entities = generate_entities(cfg, rng)
    wallets = generate_wallets(cfg, rng, entities)
    transactions = generate_transactions(cfg, rng, entities, wallets)
    corrupted = inject_corruption(transactions, rng)
    return entities, wallets, transactions, corrupted


def test_same_seed_is_byte_identical():
    cfg = _small_config()
    _, _, tx_a, corrupted_a = _run(cfg)
    _, _, tx_b, corrupted_b = _run(cfg)
    assert tx_a == tx_b
    assert corrupted_a == corrupted_b


def test_counts_match_config():
    cfg = _small_config()
    entities, wallets, transactions, _ = _run(cfg)
    assert len(entities) == cfg.num_entities
    assert len(wallets) == cfg.num_wallets
    assert len(transactions) == cfg.num_transactions


def test_corruption_rate_within_tolerance():
    cfg = _small_config()
    _, _, transactions, corrupted = _run(cfg)
    changed = sum(1 for orig, corr in zip(transactions, corrupted) if orig != corr)
    expected = round(cfg.num_transactions * CORRUPTION_RATE)
    assert changed == expected
    assert abs(changed / cfg.num_transactions - CORRUPTION_RATE) < 0.001


def _pattern_config(seed: int = 99, mixer_fraction: float = 0.03) -> SynthConfig:
    # Larger num_entities than _small_config so the ~2-3% illicit-type fractions
    # reliably produce several instances of each pattern, not zero-by-chance.
    return SynthConfig(
        random_seed=seed,
        num_entities=300,
        num_wallets=3000,
        num_transactions=1000,
        ip_noise=0.05,
        heuristic_break_rate=0.1,
        mixer_fraction=mixer_fraction,
    )


def _run_patterns(cfg: SynthConfig):
    rng = random.Random(cfg.random_seed)
    entities = generate_entities(cfg, rng)
    wallets = generate_wallets(cfg, rng, entities)
    pattern_rows, patterns = generate_illicit_patterns(cfg, rng, entities, wallets)
    seed_wallets = generate_seed_wallets(rng, entities, wallets)
    return entities, wallets, pattern_rows, patterns, seed_wallets


def test_peeling_chains_have_decreasing_value():
    cfg = _pattern_config()
    _, _, pattern_rows, patterns, _ = _run_patterns(cfg)
    rows_by_txid = {r["txid"]: r for r in pattern_rows}

    peeling_patterns = [p for p in patterns if p.type == "peeling"]
    assert peeling_patterns

    for pattern in peeling_patterns:
        values = [rows_by_txid[txid]["input_amounts"][0] for txid in pattern.txids]
        assert len(values) >= 2
        assert all(values[i] > values[i + 1] for i in range(len(values) - 1))


def test_coinjoin_rounds_have_equal_value_outputs():
    cfg = _pattern_config()
    _, _, pattern_rows, patterns, _ = _run_patterns(cfg)
    rows_by_txid = {r["txid"]: r for r in pattern_rows}

    coinjoin_patterns = [p for p in patterns if p.type == "coinjoin"]
    assert coinjoin_patterns

    for pattern in coinjoin_patterns:
        row = rows_by_txid[pattern.txids[0]]
        amounts = row["output_amounts"]
        assert len(amounts) >= 3
        # heuristic_break_rate may perturb at most one output amount.
        most_common_count = Counter(round(a, 6) for a in amounts).most_common(1)[0][1]
        assert most_common_count >= len(amounts) - 1


def test_patterns_and_seeds_are_nonempty_and_consistent():
    cfg = _pattern_config()
    entities, wallets, pattern_rows, patterns, seed_wallets = _run_patterns(cfg)

    assert patterns
    assert seed_wallets

    all_wallet_ids = {w.wallet_id for w in wallets}
    all_pattern_txids = {r["txid"] for r in pattern_rows}

    for pattern in patterns:
        assert set(pattern.wallets) <= all_wallet_ids
        assert set(pattern.txids) <= all_pattern_txids

    entities_by_id = {e.entity_id: e for e in entities}
    illicit_wallet_ids = {
        w.wallet_id for w in wallets if entities_by_id[w.entity_id].entity_type in ILLICIT_TYPES
    }
    assert set(seed_wallets) <= illicit_wallet_ids
    # ~5-10% with slack for rounding at small counts.
    assert 0.03 <= len(seed_wallets) / len(illicit_wallet_ids) <= 0.12


def test_noise_knobs_change_generation_output():
    low = _pattern_config(mixer_fraction=0.0)
    high = _pattern_config(mixer_fraction=0.10)

    rng_low = random.Random(low.random_seed)
    mixer_count_low = sum(1 for e in generate_entities(low, rng_low) if e.entity_type == "mixer")

    rng_high = random.Random(high.random_seed)
    entities_high = generate_entities(high, rng_high)
    mixer_count_high = sum(1 for e in entities_high if e.entity_type == "mixer")

    assert mixer_count_high > mixer_count_low

    wallets_high = generate_wallets(high, rng_high, entities_high)
    always_break = SynthConfig(**{**vars(high), "heuristic_break_rate": 1.0})
    rng_break = random.Random(always_break.random_seed)
    entities_break = generate_entities(always_break, rng_break)
    wallets_break = generate_wallets(always_break, rng_break, entities_break)
    pattern_rows, patterns = generate_illicit_patterns(always_break, rng_break, entities_break, wallets_break)

    coinjoin_patterns = [p for p in patterns if p.type == "coinjoin"]
    assert coinjoin_patterns
    rows_by_txid = {r["txid"]: r for r in pattern_rows}
    for pattern in coinjoin_patterns:
        amounts = rows_by_txid[pattern.txids[0]]["output_amounts"]
        assert len({round(a, 6) for a in amounts}) > 1  # heuristic_break_rate=1.0 always perturbs
