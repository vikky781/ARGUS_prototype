"""Builds the typed dual-layer transaction graph from canonical/transactions.parquet.

Only the four structural edge types derivable directly from ingested transaction
rows are built here: FUNDS, PAYS, BROADCAST_VIA, RESOLVES_TO. CO_SPEND (entity
resolution pass 1) and SAME_ENTITY (Dev B, never produced in this repo) are not
built here — see docs/contracts.md.
"""
from __future__ import annotations

import igraph as ig
import pandas as pd


def build_graph(df: pd.DataFrame) -> ig.Graph:
    wallets: set[str] = set()
    for col in ("input_addresses", "output_addresses"):
        for arr in df[col]:
            wallets.update(arr)
    wallets = sorted(wallets)

    txids = df["txid"].tolist()

    ip_asn: dict[str, int] = {}
    for src_ip, asn in zip(df["src_ip"], df["asn"]):
        ip_asn.setdefault(src_ip, asn)
    ips = sorted(ip_asn)
    asns = sorted(set(ip_asn.values()))

    vertex_names: list[str] = []
    vertex_types: list[str] = []
    for w in wallets:
        vertex_names.append(w)
        vertex_types.append("Wallet")
    for t in txids:
        vertex_names.append(t)
        vertex_types.append("Transaction")
    for ip in ips:
        vertex_names.append(ip)
        vertex_types.append("IP")
    for asn in asns:
        vertex_names.append(str(asn))
        vertex_types.append("ASN")

    index = {name: i for i, name in enumerate(vertex_names)}

    g = ig.Graph(directed=True)
    g.add_vertices(len(vertex_names))
    g.vs["name"] = vertex_names
    g.vs["type"] = vertex_types

    edges: list[tuple[int, int]] = []
    edge_types: list[str] = []
    amounts: list[float | None] = []
    timestamps: list[object] = []
    ports: list[int | None] = []

    for row in df.itertuples(index=False):
        tx_idx = index[row.txid]

        for addr, amt in zip(row.input_addresses, row.input_amounts):
            edges.append((index[addr], tx_idx))
            edge_types.append("FUNDS")
            amounts.append(amt)
            timestamps.append(None)
            ports.append(None)

        for addr, amt in zip(row.output_addresses, row.output_amounts):
            edges.append((tx_idx, index[addr]))
            edge_types.append("PAYS")
            amounts.append(amt)
            timestamps.append(None)
            ports.append(None)

        edges.append((tx_idx, index[row.src_ip]))
        edge_types.append("BROADCAST_VIA")
        amounts.append(None)
        timestamps.append(row.timestamp)
        ports.append(row.src_port)

    for ip, asn in ip_asn.items():
        edges.append((index[ip], index[str(asn)]))
        edge_types.append("RESOLVES_TO")
        amounts.append(None)
        timestamps.append(None)
        ports.append(None)

    g.add_edges(edges)
    g.es["type"] = edge_types
    g.es["amount"] = amounts
    g.es["timestamp"] = timestamps
    g.es["port"] = ports

    return g
