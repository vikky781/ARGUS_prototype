from __future__ import annotations

import random
from dataclasses import dataclass

from argus.synth.config import SynthConfig
from argus.synth.entities import Entity

# documented approx: relative wallet-count weight per entity_type. Exchanges custody
# the most; mixers need enough of their own wallets to supply CoinJoin participants;
# darknet needs enough for a multi-hop peeling chain; ransomware needs a handful for
# its collect/layer stages.
WALLET_WEIGHTS = {
    "licit": 1.0,
    "exchange": 50.0,
    "ransomware": 3.0,
    "darknet": 8.0,
    "mixer": 20.0,
}


@dataclass(frozen=True)
class Wallet:
    wallet_id: str
    entity_id: str


def generate_wallets(config: SynthConfig, rng: random.Random, entities: list[Entity]) -> list[Wallet]:
    weights = [WALLET_WEIGHTS[e.entity_type] for e in entities]
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
