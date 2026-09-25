from __future__ import annotations

import random
from pathlib import Path

import typer

from argus.synth.config import load_config
from argus.synth.corrupt import inject_corruption
from argus.synth.entities import generate_entities
from argus.synth.export import (
    write_csv,
    write_ground_truth_entities,
    write_ground_truth_patterns,
    write_ground_truth_seeds,
    write_json,
    write_xml,
)
from argus.synth.patterns import generate_illicit_patterns
from argus.synth.seeds import generate_seed_wallets
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
    baseline_transactions = generate_transactions(cfg, rng, entities, wallets)
    pattern_transactions, patterns = generate_illicit_patterns(cfg, rng, entities, wallets)
    seed_wallets = generate_seed_wallets(rng, entities, wallets)

    # Corruption (data-quality noise) applies only to baseline rows, so a planted
    # pattern's hops never get randomly dropped by ingestion's validation — see
    # argus.synth.patterns's module docstring.
    corrupted_baseline = inject_corruption(baseline_transactions, rng)
    transactions = corrupted_baseline + pattern_transactions

    write_csv(transactions, out_dir / "raw" / "transactions.csv")
    write_json(transactions, out_dir / "raw" / "transactions.json")
    write_xml(transactions, out_dir / "raw" / "transactions.xml")
    write_ground_truth_entities(wallets, entities, out_dir / "ground_truth" / "entities.parquet")
    write_ground_truth_seeds(seed_wallets, out_dir / "ground_truth" / "seeds.parquet")
    write_ground_truth_patterns(patterns, out_dir / "ground_truth" / "patterns.parquet")

    typer.echo(
        f"entities={len(entities)} wallets={len(wallets)} "
        f"transactions={len(transactions)} (baseline={len(baseline_transactions)} "
        f"pattern={len(pattern_transactions)}) patterns={len(patterns)} seeds={len(seed_wallets)}"
    )


if __name__ == "__main__":
    app()
