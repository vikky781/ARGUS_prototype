from __future__ import annotations

import pickle
from pathlib import Path

import igraph as ig
import pandas as pd


def write_graph_pickle(g: ig.Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(g, f)


def read_graph_pickle(path: Path) -> ig.Graph:
    with open(path, "rb") as f:
        return pickle.load(f)


def export_edges(g: ig.Graph, path: Path) -> None:
    """Flat edge table: edge_type, source, target, amount, timestamp, port.

    docs/contracts.md defines each edge type's direction/meaning/attrs but not a
    literal column list for this artifact — this is that column choice. source/
    target are vertex name strings (wallet_id/txid/ip/asn), not igraph's internal
    integer ids, so the file is meaningful without the pickle.
    """
    edgelist = g.get_edgelist()
    names = g.vs["name"]
    df = pd.DataFrame(
        {
            "edge_type": g.es["type"],
            "source": [names[s] for s, _ in edgelist],
            "target": [names[t] for _, t in edgelist],
            "amount": g.es["amount"],
            "timestamp": g.es["timestamp"],
            "port": g.es["port"],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
