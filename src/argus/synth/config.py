from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SynthConfig:
    random_seed: int
    num_entities: int
    num_wallets: int
    num_transactions: int
    ip_noise: float
    heuristic_break_rate: float
    mixer_fraction: float


def load_config(path: Path) -> SynthConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return SynthConfig(
        random_seed=raw["random_seed"],
        num_entities=raw["num_entities"],
        num_wallets=raw["num_wallets"],
        num_transactions=raw["num_transactions"],
        ip_noise=raw["ip_noise"],
        heuristic_break_rate=raw["heuristic_break_rate"],
        mixer_fraction=raw["mixer_fraction"],
    )
