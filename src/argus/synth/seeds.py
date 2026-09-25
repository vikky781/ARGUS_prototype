"""Marks a random ~5-10% of illicit wallets as a known-illicit seed set, per
docs/contracts.md's ground_truth/seeds.parquet schema.
"""
from __future__ import annotations

import random

from argus.synth.entities import Entity
from argus.synth.wallets import Wallet

ILLICIT_TYPES = ("ransomware", "darknet", "mixer")
SEED_FRACTION_RANGE = (0.05, 0.10)


def generate_seed_wallets(rng: random.Random, entities: list[Entity], wallets: list[Wallet]) -> list[str]:
    entities_by_id = {e.entity_id: e for e in entities}
    illicit_wallet_ids = [
        w.wallet_id for w in wallets if entities_by_id[w.entity_id].entity_type in ILLICIT_TYPES
    ]
    if not illicit_wallet_ids:
        return []

    fraction = rng.uniform(*SEED_FRACTION_RANGE)
    k = round(len(illicit_wallet_ids) * fraction)
    k = max(0, min(k, len(illicit_wallet_ids)))
    return sorted(rng.sample(illicit_wallet_ids, k))
