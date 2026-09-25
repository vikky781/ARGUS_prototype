"""Baseline (v1) transaction generation.

No illicit patterns yet: every input of a transaction comes from a single sender
wallet (no CoinJoin-style multi-party inputs), and outputs are a plain payment plus
an optional change-back-to-sender output. Peeling/CoinJoin arrive in a later phase.
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone

from argus.synth.config import SynthConfig
from argus.synth.entities import BROADCAST_SPREAD_HOURS, Entity
from argus.synth.networks import NETWORK_POOL, random_ip_and_geo
from argus.synth.wallets import Wallet

# Fixed anchor date (not wall-clock "now") so identical seeds give byte-identical
# timestamps regardless of which day the generator is actually run on.
BASE_DATE = datetime(2024, 1, 1, tzinfo=timezone.utc)
WINDOW_DAYS = 90

# Documented approx distributions — loosely modeled on real-world mainnet mix, not
# claimed to be exact.
SCRIPT_TYPE_WEIGHTS = [
    ("P2WPKH", 0.45),
    ("P2PKH", 0.35),
    ("P2SH", 0.12),
    ("P2WSH", 0.08),
]
DST_PORT_WEIGHTS = [(8333, 0.90), (18333, 0.05), (28333, 0.05)]
FEE_RANGE = (0.00001, 0.0005)  # documented approx flat range for the synthetic fee
AMOUNT_LOGNORM_PARAMS = (-2.0, 1.5)  # (mu, sigma) for the base transacted amount


def _weighted_choice(rng: random.Random, weights: list[tuple[object, float]]):
    r = rng.random()
    cumulative = 0.0
    for value, w in weights:
        cumulative += w
        if r < cumulative:
            return value
    return weights[-1][0]


def _broadcast_timestamp(entity: Entity, rng: random.Random) -> datetime:
    day_offset = rng.uniform(0, WINDOW_DAYS)
    hour = rng.gauss(entity.peak_hour, BROADCAST_SPREAD_HOURS) % 24
    minute = rng.uniform(0, 60)
    return BASE_DATE + timedelta(days=day_offset, hours=hour, minutes=minute)


def _split_amount(total: float, parts: int, rng: random.Random) -> list[float]:
    if parts == 1:
        return [round(total, 8)]
    cut = rng.uniform(0.15, 0.85) * total
    return [round(cut, 8), round(total - cut, 8)]


def generate_transactions(
    config: SynthConfig,
    rng: random.Random,
    entities: list[Entity],
    wallets: list[Wallet],
) -> list[dict]:
    entities_by_id = {e.entity_id: e for e in entities}
    transactions = []

    for i in range(config.num_transactions):
        sender = rng.choice(wallets)
        sender_entity = entities_by_id[sender.entity_id]

        num_inputs = 1 if rng.random() < 0.85 else 2
        num_outputs = 1 if rng.random() < 0.5 else 2

        base_amount = rng.lognormvariate(*AMOUNT_LOGNORM_PARAMS)
        fee = round(rng.uniform(*FEE_RANGE), 8)
        total_input = base_amount + fee

        input_amounts = _split_amount(total_input, num_inputs, rng)
        output_amounts = _split_amount(base_amount, num_outputs, rng)

        # v1 baseline: all inputs come from the sender's own wallet (no CoinJoin yet).
        input_addresses = [sender.wallet_id] * num_inputs

        output_addresses = []
        for j in range(num_outputs):
            if j == 0:
                recipient = rng.choice(wallets)
            else:
                recipient = sender  # simulated change output
            output_addresses.append(recipient.wallet_id)

        if rng.random() < config.ip_noise:
            noise_net = rng.choice(NETWORK_POOL)
            src_ip, asn, geo_country = random_ip_and_geo(noise_net, None, rng)
        else:
            src_ip, asn, geo_country = random_ip_and_geo(
                sender_entity.home_network, sender_entity.home_third_octet, rng
            )

        dst_net = rng.choice(NETWORK_POOL)
        dst_ip, _, _ = random_ip_and_geo(dst_net, None, rng)

        txid = hashlib.sha256(f"{config.random_seed}-tx-{i}".encode()).hexdigest()

        transactions.append(
            {
                "txid": txid,
                "timestamp": _broadcast_timestamp(sender_entity, rng),
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": rng.randint(1024, 65535),
                "dst_port": _weighted_choice(rng, DST_PORT_WEIGHTS),
                "geo_country": geo_country,
                "asn": asn,
                "input_addresses": input_addresses,
                "input_amounts": input_amounts,
                "output_addresses": output_addresses,
                "output_amounts": output_amounts,
                "fee": fee,
                "script_type": _weighted_choice(rng, SCRIPT_TYPE_WEIGHTS),
            }
        )

    return transactions
