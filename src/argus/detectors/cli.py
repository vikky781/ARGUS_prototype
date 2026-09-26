from __future__ import annotations

from pathlib import Path

import typer

from argus.detectors.coinjoin import detect_coinjoin_rounds
from argus.detectors.peeling import detect_peeling_chains
from argus.detectors.scores import coinjoin_round_rows, peeling_chain_rows, write_scores_pattern
from argus.graph.export import read_graph_pickle

app = typer.Typer()


@app.command()
def run(data_dir: Path = typer.Option(Path("data"), "--data-dir")) -> None:
    g = read_graph_pickle(data_dir / "artifacts" / "graph.pkl")

    chains = detect_peeling_chains(g)
    rounds = detect_coinjoin_rounds(g)

    rows = peeling_chain_rows(chains) + coinjoin_round_rows(rounds)
    write_scores_pattern(rows, data_dir / "artifacts" / "scores_pattern.parquet")

    typer.echo(f"peeling_chains={len(chains)} coinjoin_rounds={len(rounds)} score_rows={len(rows)}")


if __name__ == "__main__":
    app()
