"""Illicit structural patterns layered on top of the v1 baseline traffic.

These are ADDITIONAL transactions, generated separately from generate_transactions
and appended to it in the CLI — the baseline generator's own contract (exactly
num_transactions rows) is unchanged. All three pattern types below reuse the
entity/wallet pools already built for baseline generation; no new wallets are
created here.

Deliberately NOT corrupted by argus.synth.corrupt: that module's 0.5% data-quality
corruption is applied only to baseline rows (see cli.py), so a planted pattern's
hops never get randomly dropped by ingestion's validation and its ground-truth
txids always resolve to real ingested rows.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from argus.synth.config import SynthConfig
from argus.synth.entities import Entity
from argus.synth.transactions import (
    DST_PORT_WEIGHTS,
    FEE_RANGE,
    SCRIPT_TYPE_WEIGHTS,
    _broadcast_timestamp,
    _network_fields,
    _random_peer_ip,
    _weighted_choice,
)
from argus.synth.wallets import Wallet

# Vary hop count / decay rate / participant count per instance — documented approx
# ranges, not tuned to any real dataset.
PEELING_HOP_RANGE = (3, 8)
PEELING_DECAY_RANGE = (0.80, 0.95)
PEELING_INITIAL_VALUE_LOGNORM = (1.0, 1.0)  # the "pot" a chain peels down from

COINJOIN_N_RANGE = (3, 10)
COINJOIN_DENOMINATION_LOGNORM = (-1.5, 0.6)  # per-participant round amount

RANSOMWARE_VICTIM_RANGE = (3, 8)
RANSOMWARE_RANSOM_LOGNORM = (-1.0, 0.8)


@dataclass(frozen=True)
class PatternRecord:
    pattern_id: str
    type: str  # "peeling" | "coinjoin"
    txids: list[str]
    wallets: list[str]


def _make_txid(config: SynthConfig, label: str) -> str:
    return hashlib.sha256(f"{config.random_seed}-pattern-{label}".encode()).hexdigest()


def _base_row(entity: Entity, config: SynthConfig, rng: random.Random, txid: str) -> dict:
    src_ip, asn, geo_country = _network_fields(entity, config, rng)
    return {
        "txid": txid,
        "timestamp": _broadcast_timestamp(entity, rng),
        "src_ip": src_ip,
        "dst_ip": _random_peer_ip(rng),
        "src_port": rng.randint(1024, 65535),
        "dst_port": _weighted_choice(rng, DST_PORT_WEIGHTS),
        "geo_country": geo_country,
        "asn": asn,
        "script_type": _weighted_choice(rng, SCRIPT_TYPE_WEIGHTS),
    }


def generate_peeling_chain(
    entity: Entity,
    entity_wallets: list[Wallet],
    all_wallets: list[Wallet],
    config: SynthConfig,
    rng: random.Random,
    pattern_index: int,
) -> tuple[list[dict], PatternRecord]:
    """A single-dominant-output chain: each hop forwards most of the value to the
    next wallet in the chain and peels a small amount off to some other wallet.
    The dominant (continuation) amount strictly decreases hop over hop, by
    construction (decay_rate < 1) — that's the signal a peeling-chain detector
    looks for. With probability heuristic_break_rate, a hop also gets a small
    third noise output, breaking the "exactly two outputs" heuristic.
    """
    hop_count = max(1, min(rng.randint(*PEELING_HOP_RANGE), len(entity_wallets) - 1))
    decay_rate = rng.uniform(*PEELING_DECAY_RANGE)
    chain_wallets = entity_wallets[: hop_count + 1]
    value = rng.lognormvariate(*PEELING_INITIAL_VALUE_LOGNORM)

    rows = []
    txids = []
    involved_wallets = {w.wallet_id for w in chain_wallets}

    for hop in range(hop_count):
        source = chain_wallets[hop]
        next_wallet = chain_wallets[hop + 1]
        peel_target = rng.choice(all_wallets)
        involved_wallets.add(peel_target.wallet_id)

        fee = round(rng.uniform(*FEE_RANGE), 8)
        continuation_amount = round(value * decay_rate, 8)
        peel_amount = round(value - continuation_amount - fee, 8)

        output_addresses = [next_wallet.wallet_id, peel_target.wallet_id]
        output_amounts = [continuation_amount, peel_amount]

        if rng.random() < config.heuristic_break_rate:
            noise_amount = round(rng.uniform(0.00001, max(0.00002, peel_amount * 0.3)), 8)
            if 0 < noise_amount < peel_amount:
                noise_target = rng.choice(all_wallets)
                output_amounts[1] = round(peel_amount - noise_amount, 8)
                output_addresses.append(noise_target.wallet_id)
                output_amounts.append(noise_amount)
                involved_wallets.add(noise_target.wallet_id)

        txid = _make_txid(config, f"peeling-{pattern_index}-{hop}")
        row = _base_row(entity, config, rng, txid)
        row.update(
            {
                "input_addresses": [source.wallet_id],
                "input_amounts": [value],
                "output_addresses": output_addresses,
                "output_amounts": output_amounts,
                "fee": fee,
            }
        )
        rows.append(row)
        txids.append(txid)

        value = continuation_amount

    pattern = PatternRecord(
        pattern_id=f"peeling_{pattern_index:04d}",
        type="peeling",
        txids=txids,
        wallets=sorted(involved_wallets),
    )
    return rows, pattern


def generate_coinjoin_round(
    entity: Entity,
    entity_wallets: list[Wallet],
    all_wallets: list[Wallet],
    config: SynthConfig,
    rng: random.Random,
    pattern_index: int,
) -> tuple[list[dict], PatternRecord]:
    """One transaction with N equal-value inputs (the mixer's own wallets) and N
    equal-value outputs (fresh recipient wallets) — the classic CoinJoin signal.
    With probability heuristic_break_rate, one output amount is perturbed by a
    small epsilon (absorbed into fee, so the transaction still balances), breaking
    the "every output is exactly equal" heuristic.
    """
    n = max(2, min(rng.randint(*COINJOIN_N_RANGE), len(entity_wallets)))
    participants = entity_wallets[:n]

    denomination = round(rng.lognormvariate(*COINJOIN_DENOMINATION_LOGNORM), 8)
    fee_per_participant = round(rng.uniform(*FEE_RANGE) / n, 8)

    input_addresses = [w.wallet_id for w in participants]
    input_amounts = [round(denomination + fee_per_participant, 8) for _ in participants]

    excluded = {w.wallet_id for w in participants}
    pool = [w for w in all_wallets if w.wallet_id not in excluded]
    recipients = [rng.choice(pool) for _ in range(n)]

    output_addresses = [w.wallet_id for w in recipients]
    output_amounts = [denomination for _ in recipients]
    fee_total = round(fee_per_participant * n, 8)

    if rng.random() < config.heuristic_break_rate:
        idx = rng.randrange(n)
        epsilon = round(rng.uniform(0.00001, max(0.00002, denomination * 0.05)), 8)
        output_amounts[idx] = round(denomination - epsilon, 8)
        fee_total = round(fee_total + epsilon, 8)

    txid = _make_txid(config, f"coinjoin-{pattern_index}")
    row = _base_row(entity, config, rng, txid)
    row.update(
        {
            "input_addresses": input_addresses,
            "input_amounts": input_amounts,
            "output_addresses": output_addresses,
            "output_amounts": output_amounts,
            "fee": fee_total,
        }
    )

    involved = sorted({*input_addresses, *output_addresses})
    pattern = PatternRecord(
        pattern_id=f"coinjoin_{pattern_index:04d}",
        type="coinjoin",
        txids=[txid],
        wallets=involved,
    )
    return [row], pattern


def generate_ransomware_lifecycle(
    entity: Entity,
    entity_wallets: list[Wallet],
    all_wallets: list[Wallet],
    exchange_wallets: list[Wallet],
    config: SynthConfig,
    rng: random.Random,
    pattern_index: int,
) -> list[dict]:
    """collect (victims -> collection wallet) -> layer (1-2 hops within the
    entity's own wallets) -> cash-out (final wallet -> an exchange wallet).
    Not tracked in ground_truth/patterns.parquet (that file is peeling/coinjoin
    only, per its schema) — this lifecycle's ground truth is the entity_type
    ("ransomware") already recorded in ground_truth/entities.parquet.
    """
    if len(entity_wallets) < 2 or not exchange_wallets:
        return []

    collection_wallet = entity_wallets[0]
    layer_wallets = entity_wallets[1:3] if len(entity_wallets) >= 3 else entity_wallets[1:2]

    excluded_ids = {w.wallet_id for w in entity_wallets}
    victim_pool = [w for w in all_wallets if w.wallet_id not in excluded_ids]

    rows = []
    total_collected = 0.0
    num_victims = rng.randint(*RANSOMWARE_VICTIM_RANGE)

    for v in range(num_victims):
        victim = rng.choice(victim_pool)
        ransom = round(rng.lognormvariate(*RANSOMWARE_RANSOM_LOGNORM), 8)
        fee = round(rng.uniform(*FEE_RANGE), 8)
        txid = _make_txid(config, f"ransomware-{pattern_index}-collect-{v}")
        row = _base_row(entity, config, rng, txid)
        row.update(
            {
                "input_addresses": [victim.wallet_id],
                "input_amounts": [round(ransom + fee, 8)],
                "output_addresses": [collection_wallet.wallet_id],
                "output_amounts": [ransom],
                "fee": fee,
            }
        )
        rows.append(row)
        total_collected += ransom

    chain = [collection_wallet, *layer_wallets]
    current_value = round(total_collected, 8)
    for hop in range(len(chain) - 1):
        fee = round(rng.uniform(*FEE_RANGE), 8)
        forward_amount = round(current_value - fee, 8)
        txid = _make_txid(config, f"ransomware-{pattern_index}-layer-{hop}")
        row = _base_row(entity, config, rng, txid)
        row.update(
            {
                "input_addresses": [chain[hop].wallet_id],
                "input_amounts": [current_value],
                "output_addresses": [chain[hop + 1].wallet_id],
                "output_amounts": [forward_amount],
                "fee": fee,
            }
        )
        rows.append(row)
        current_value = forward_amount

    cashout_target = rng.choice(exchange_wallets)
    fee = round(rng.uniform(*FEE_RANGE), 8)
    final_amount = round(current_value - fee, 8)
    txid = _make_txid(config, f"ransomware-{pattern_index}-cashout")
    row = _base_row(entity, config, rng, txid)
    row.update(
        {
            "input_addresses": [chain[-1].wallet_id],
            "input_amounts": [current_value],
            "output_addresses": [cashout_target.wallet_id],
            "output_amounts": [final_amount],
            "fee": fee,
        }
    )
    rows.append(row)

    return rows


def generate_illicit_patterns(
    config: SynthConfig, rng: random.Random, entities: list[Entity], wallets: list[Wallet]
) -> tuple[list[dict], list[PatternRecord]]:
    """One peeling chain per darknet entity, one CoinJoin round per mixer entity,
    one collect->layer->cash-out lifecycle per ransomware entity. Entities without
    enough of their own wallets to support their pattern are skipped.
    """
    entities_by_id = {e.entity_id: e for e in entities}
    wallets_by_entity: dict[str, list[Wallet]] = {}
    for w in wallets:
        wallets_by_entity.setdefault(w.entity_id, []).append(w)
    exchange_wallets = [w for w in wallets if entities_by_id[w.entity_id].entity_type == "exchange"]

    all_rows: list[dict] = []
    patterns: list[PatternRecord] = []

    darknet_entities = [e for e in entities if e.entity_type == "darknet"]
    mixer_entities = [e for e in entities if e.entity_type == "mixer"]
    ransomware_entities = [e for e in entities if e.entity_type == "ransomware"]

    for i, entity in enumerate(darknet_entities):
        entity_wallets = wallets_by_entity.get(entity.entity_id, [])
        if len(entity_wallets) < 2:
            continue
        rows, pattern = generate_peeling_chain(entity, entity_wallets, wallets, config, rng, i)
        all_rows.extend(rows)
        patterns.append(pattern)

    for i, entity in enumerate(mixer_entities):
        entity_wallets = wallets_by_entity.get(entity.entity_id, [])
        if len(entity_wallets) < 2:
            continue
        rows, pattern = generate_coinjoin_round(entity, entity_wallets, wallets, config, rng, i)
        all_rows.extend(rows)
        patterns.append(pattern)

    for i, entity in enumerate(ransomware_entities):
        entity_wallets = wallets_by_entity.get(entity.entity_id, [])
        rows = generate_ransomware_lifecycle(entity, entity_wallets, wallets, exchange_wallets, config, rng, i)
        all_rows.extend(rows)

    return all_rows, patterns
