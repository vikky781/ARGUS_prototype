from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd
import typer

from argus.graph.build import build_graph
from argus.graph.export import export_edges, write_graph_pickle

app = typer.Typer()


@app.command()
def build(data_dir: Path = typer.Option(Path("data"), "--data-dir")) -> None:
    canonical_path = data_dir / "canonical" / "transactions.parquet"
    df = pd.read_parquet(canonical_path)

    g = build_graph(df)

    write_graph_pickle(g, data_dir / "artifacts" / "graph.pkl")
    export_edges(g, data_dir / "artifacts" / "graph_edges.parquet")

    node_counts = dict(Counter(g.vs["type"]))
    edge_counts = dict(Counter(g.es["type"]))
    typer.echo(f"nodes={node_counts} edges={edge_counts}")


if __name__ == "__main__":
    app()
