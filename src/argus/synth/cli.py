from __future__ import annotations

import random
from pathlib import Path

import typer

from argus.synth.config import load_config
from argus.synth.corrupt import inject_corruption
from argus.synth.entities import generate_entities
from argus.synth.export import write_csv, write_ground_truth_entities, write_json, write_xml
from argus.synth.transactions import generate_transactions
from argus.synth.wallets import generate_wallets

app = typer.Typer()


@app.command()
def generate(
    config: Path = typer.Option(Path("configs/default.yaml"), "--config"),
    out_dir: Path = typer.Option(Path("data"), "--out-dir"),
) -> None:
    cfg = load_config(config)
    rng = random.Random(cfg.random_seed)

    entities = generate_entities(cfg, rng)
    wallets = generate_wallets(cfg, rng, entities)
    transactions = generate_transactions(cfg, rng, entities, wallets)
    corrupted = inject_corruption(transactions, rng)

    write_csv(corrupted, out_dir / "raw" / "transactions.csv")
    write_json(corrupted, out_dir / "raw" / "transactions.json")
    write_xml(corrupted, out_dir / "raw" / "transactions.xml")
    write_ground_truth_entities(wallets, entities, out_dir / "ground_truth" / "entities.parquet")

    typer.echo(f"entities={len(entities)} wallets={len(wallets)} transactions={len(transactions)}")


if __name__ == "__main__":
    app()
