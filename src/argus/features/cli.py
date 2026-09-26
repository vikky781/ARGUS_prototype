from __future__ import annotations

from pathlib import Path

import pandas as pd
import typer

from argus.features.build import compute_node_features
from argus.graph.export import read_graph_pickle

app = typer.Typer()


@app.command()
def build(data_dir: Path = typer.Option(Path("data"), "--data-dir")) -> None:
    g = read_graph_pickle(data_dir / "artifacts" / "graph.pkl")
    df = pd.read_parquet(data_dir / "canonical" / "transactions.parquet")
    resolved_entities = pd.read_parquet(data_dir / "artifacts" / "entities.parquet")

    features = compute_node_features(g, df, resolved_entities)

    out_path = data_dir / "artifacts" / "node_features.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(out_path, index=False)

    f_cols = [c for c in features.columns if c.startswith("f_")]
    nan_count = int(features[f_cols].isna().sum().sum())
    typer.echo(f"rows={len(features)} f_columns={len(f_cols)} nan_count={nan_count}")


if __name__ == "__main__":
    app()
