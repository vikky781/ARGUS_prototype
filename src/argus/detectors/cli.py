from __future__ import annotations

from pathlib import Path

import pandas as pd
import typer

from argus.detectors.coinjoin import detect_coinjoin_rounds
from argus.detectors.peeling import detect_peeling_chains
from argus.detectors.risk_ppr import compute_risk_scores, risk_score_rows
from argus.detectors.scores import coinjoin_round_rows, peeling_chain_rows, write_scores
from argus.graph.export import read_graph_pickle

app = typer.Typer()


@app.command()
def run(data_dir: Path = typer.Option(Path("data"), "--data-dir")) -> None:
    g = read_graph_pickle(data_dir / "artifacts" / "graph.pkl")

    chains = detect_peeling_chains(g)
    rounds = detect_coinjoin_rounds(g)
    pattern_rows = peeling_chain_rows(chains) + coinjoin_round_rows(rounds)
    write_scores(pattern_rows, data_dir / "artifacts" / "scores_pattern.parquet")

    seeds = pd.read_parquet(data_dir / "ground_truth" / "seeds.parquet")
    risk_scores = compute_risk_scores(g, seeds["wallet_id"].tolist())
    risk_rows = risk_score_rows(risk_scores)
    write_scores(risk_rows, data_dir / "artifacts" / "scores_risk.parquet")

    typer.echo(
        f"peeling_chains={len(chains)} coinjoin_rounds={len(rounds)} pattern_score_rows={len(pattern_rows)} "
        f"risk_score_rows={len(risk_rows)} seeds={len(seeds)}"
    )


if __name__ == "__main__":
    app()
