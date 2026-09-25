from __future__ import annotations

import random
from dataclasses import dataclass

from argus.synth.config import SynthConfig
from argus.synth.networks import NETWORK_POOL, Network

# v1 baseline only — ransomware/darknet/mixer types arrive with the illicit-patterns phase.
ENTITY_TYPES_V1 = ("licit", "exchange")
EXCHANGE_FRACTION = 0.05  # documented approx: exchanges are rare but wallet-heavy (see wallets.py)
BROADCAST_SPREAD_HOURS = 2.5  # documented approx std-dev of an entity's broadcast-hour clustering


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: str  # "licit" | "exchange" (v1 baseline only)
    home_network: Network  # this entity's IP subnet affinity
    home_third_octet: int  # picks a specific /24 within home_network's /16
    peak_hour: int  # 0-23, center of this entity's broadcast-time profile


def generate_entities(config: SynthConfig, rng: random.Random) -> list[Entity]:
    entities = []
    for i in range(config.num_entities):
        entity_type = "exchange" if rng.random() < EXCHANGE_FRACTION else "licit"
        home_network = rng.choice(NETWORK_POOL)
        home_third_octet = rng.randint(0, 255)
        peak_hour = rng.randint(0, 23)
        entities.append(
            Entity(
                entity_id=f"entity_{i:05d}",
                entity_type=entity_type,
                home_network=home_network,
                home_third_octet=home_third_octet,
                peak_hour=peak_hour,
            )
        )
    return entities
