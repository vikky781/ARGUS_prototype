from __future__ import annotations

from pathlib import Path

import typer

from argus.ingest.pipeline import run_ingest, write_canonical

app = typer.Typer()

RAW_FILENAMES = {"csv": "transactions.csv", "json": "transactions.json", "xml": "transactions.xml"}


@app.command()
def ingest(
    fmt: str = typer.Option("csv", "--format"),
    data_dir: Path = typer.Option(Path("data"), "--data-dir"),
) -> None:
    input_path = data_dir / "raw" / RAW_FILENAMES[fmt]
    rejects_path = data_dir / "artifacts" / "rejects.log"
    canonical_path = data_dir / "canonical" / "transactions.parquet"

    df = run_ingest(input_path, fmt, rejects_path)
    write_canonical(df, canonical_path)

    with open(rejects_path, encoding="utf-8") as f:
        total_rejected = sum(1 for _ in f)

    typer.echo(f"ingested={len(df)} rejected={total_rejected} format={fmt}")


if __name__ == "__main__":
    app()
