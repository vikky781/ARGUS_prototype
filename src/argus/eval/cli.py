from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import typer

from argus.eval.ablation import run_ablation_sweep
from argus.eval.report import run_full_summary

app = typer.Typer()

DETECTION_SCORE_COLUMNS = ["peeling_recall", "coinjoin_recall", "risk_precision_at_50"]


def _save_plot(df: pd.DataFrame, path: Path) -> None:
    plot_df = df.copy()
    plot_df["detection_score"] = plot_df[DETECTION_SCORE_COLUMNS].mean(axis=1)
    pivot = plot_df.pivot(index="ip_noise", columns="condition", values="detection_score")

    fig, ax = plt.subplots(figsize=(6, 4))
    pivot.plot(marker="o", ax=ax)
    ax.set_xlabel("ip_noise")
    ax.set_ylabel("mean(peeling recall, coinjoin recall, risk P@50)")
    ax.set_title("Dual-layer vs on-chain-only detection score by noise level")
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


@app.command()
def run(
    data_dir: Path = typer.Option(Path("data"), "--data-dir"),
    docs_dir: Path = typer.Option(Path("docs"), "--docs-dir"),
) -> None:
    summary = run_full_summary(data_dir)
    typer.echo("=== Full-pipeline metric summary (ER / pattern detectors / risk) ===")
    typer.echo(summary.to_string(index=False))

    tmp_dir = data_dir / "artifacts" / "_ablation_tmp"
    ablation_df = run_ablation_sweep(tmp_dir)

    csv_path = docs_dir / "ablation_results.csv"
    ablation_df.to_csv(csv_path, index=False)

    plot_path = docs_dir / "ablation_plot.png"
    _save_plot(ablation_df, plot_path)

    typer.echo()
    typer.echo("=== Dual-layer vs on-chain-only ablation ===")
    typer.echo(ablation_df.to_string(index=False))
    typer.echo(f"saved: {csv_path}, {plot_path}")


if __name__ == "__main__":
    app()
