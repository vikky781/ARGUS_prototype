"""Classical CoinJoin detector.

Flags transactions with many distinct FUNDS inputs and many roughly-equal-value
PAYS outputs, using the SAME structural check argus.er.union_find uses to guard
against ER pass-1 over-merging — kept as a single source of truth for "what
counts as CoinJoin-like" rather than reimplementing the tolerance logic here.

This is Dev A's classical/structural detector only. Dev B's
detectors/pattern_sim.py (embedding-similarity variant) would append MORE rows
to the same artifacts/scores_pattern.parquet later — not implemented here.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import igraph as ig

from argus.er.union_find import is_coinjoin_like


@dataclass
class CoinjoinRound:
    txid: str
    input_wallets: list[str]
    output_wallets: list[str]
    denomination: float
    equal_output_fraction: float  # confidence: fraction of outputs at the modal amount

    @property
    def participant_count(self) -> int:
        return len(self.input_wallets)


def detect_coinjoin_rounds(g: ig.Graph) -> list[CoinjoinRound]:
    names = g.vs["name"]
    edgelist = g.get_edgelist()
    edge_types = g.es["type"]
    amounts = g.es["amount"]

    funds_in: dict[str, list[str]] = {}
    pays_out: dict[str, list[tuple[str, float]]] = {}
    for (s, t), et, amt in zip(edgelist, edge_types, amounts):
        if et == "FUNDS":
            funds_in.setdefault(names[t], []).append(names[s])
        elif et == "PAYS":
            pays_out.setdefault(names[s], []).append((names[t], amt))

    rounds: list[CoinjoinRound] = []
    for txid, inputs in funds_in.items():
        outputs = pays_out.get(txid, [])
        output_amounts = [a for _, a in outputs]
        if not is_coinjoin_like(inputs, output_amounts):
            continue

        rounded = [round(a, 6) for a in output_amounts]
        denomination, modal_count = Counter(rounded).most_common(1)[0]

        rounds.append(
            CoinjoinRound(
                txid=txid,
                input_wallets=sorted(set(inputs)),
                output_wallets=[w for w, _ in outputs],
                denomination=denomination,
                equal_output_fraction=modal_count / len(rounded),
            )
        )
    return rounds
