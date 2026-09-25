import random

from argus.synth.config import SynthConfig
from argus.synth.corrupt import CORRUPTION_RATE, inject_corruption
from argus.synth.entities import generate_entities
from argus.synth.transactions import generate_transactions
from argus.synth.wallets import generate_wallets


def _small_config(seed: int = 123) -> SynthConfig:
    return SynthConfig(
        random_seed=seed,
        num_entities=50,
        num_wallets=300,
        num_transactions=2000,
        ip_noise=0.1,
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
