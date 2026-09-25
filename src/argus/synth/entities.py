from __future__ import annotations

import random
from dataclasses import dataclass

from argus.synth.config import SynthConfig
from argus.synth.networks import NETWORK_POOL, Network

# Documented approx fractions. exchange/ransomware/darknet are fixed constants;
# mixer is config-driven (mixer_fraction) since it's a swept difficulty knob —
# see docs/contracts.md's ground_truth/entities.parquet entity_type values.
EXCHANGE_FRACTION = 0.05
RANSOMWARE_FRACTION = 0.02
DARKNET_FRACTION = 0.03
BROADCAST_SPREAD_HOURS = 2.5  # documented approx std-dev of an entity's broadcast-hour clustering


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: str  # "licit" | "exchange" | "ransomware" | "darknet" | "mixer"
    home_network: Network  # this entity's IP subnet affinity
    home_third_octet: int  # picks a specific /24 within home_network's /16
    peak_hour: int  # 0-23, center of this entity's broadcast-time profile


def _pick_entity_type(config: SynthConfig, rng: random.Random) -> str:
    r = rng.random()
    cumulative = 0.0
    for entity_type, fraction in (
        ("exchange", EXCHANGE_FRACTION),
        ("ransomware", RANSOMWARE_FRACTION),
        ("darknet", DARKNET_FRACTION),
        ("mixer", config.mixer_fraction),
    ):
        cumulative += fraction
        if r < cumulative:
            return entity_type
    return "licit"


def generate_entities(config: SynthConfig, rng: random.Random) -> list[Entity]:
    entities = []
    for i in range(config.num_entities):
        entity_type = _pick_entity_type(config, rng)
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
