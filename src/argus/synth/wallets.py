from __future__ import annotations

import random
from dataclasses import dataclass

from argus.synth.config import SynthConfig
from argus.synth.entities import Entity

# documented approx: exchanges custody far more wallets than an individual licit entity
EXCHANGE_WALLET_WEIGHT = 50.0
LICIT_WALLET_WEIGHT = 1.0


@dataclass(frozen=True)
class Wallet:
    wallet_id: str
    entity_id: str


def generate_wallets(config: SynthConfig, rng: random.Random, entities: list[Entity]) -> list[Wallet]:
    weights = [
        EXCHANGE_WALLET_WEIGHT if e.entity_type == "exchange" else LICIT_WALLET_WEIGHT
        for e in entities
    ]
    total_weight = sum(weights)
    counts = [int(w / total_weight * config.num_wallets) for w in weights]

    # Deterministically hand out the rounding remainder so sum(counts) == num_wallets exactly.
    remainder = config.num_wallets - sum(counts)
    for i in range(remainder):
        counts[i % len(counts)] += 1

    wallets = []
    idx = 0
    for entity, count in zip(entities, counts):
        for _ in range(count):
            wallets.append(Wallet(wallet_id=f"wallet_{idx:06d}", entity_id=entity.entity_id))
            idx += 1
    return wallets
