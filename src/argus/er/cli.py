from __future__ import annotations

from pathlib import Path

import pandas as pd
import typer

from argus.er.evaluate import evaluate_pairwise
from argus.er.union_find import add_co_spend_edges, resolve_entities, write_entities_parquet
from argus.graph.export import export_edges, read_graph_pickle, write_graph_pickle

app = typer.Typer()


@app.command()
def resolve(data_dir: Path = typer.Option(Path("data"), "--data-dir")) -> None:
    canonical_path = data_dir / "canonical" / "transactions.parquet"
    df = pd.read_parquet(canonical_path)

    uf, links = resolve_entities(df)

    graph_path = data_dir / "artifacts" / "graph.pkl"
    g = read_graph_pickle(graph_path)
    g = add_co_spend_edges(g, links)
    write_graph_pickle(g, graph_path)
    export_edges(g, data_dir / "artifacts" / "graph_edges.parquet")

    entities_path = data_dir / "artifacts" / "entities.parquet"
    write_entities_parquet(uf, entities_path)

    ground_truth = pd.read_parquet(data_dir / "ground_truth" / "entities.parquet")
    predicted = pd.read_parquet(entities_path)
    metrics = evaluate_pairwise(predicted, ground_truth)

    typer.echo(
        f"clusters={len(uf.groups())} co_spend_links={len(links)} "
        f"precision={metrics['precision']:.4f} recall={metrics['recall']:.4f} f1={metrics['f1']:.4f} "
        f"tp_pairs={metrics['tp_pairs']} predicted_pairs={metrics['predicted_pairs']} true_pairs={metrics['true_pairs']}"
    )


if __name__ == "__main__":
    app()
