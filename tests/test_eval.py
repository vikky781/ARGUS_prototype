import math

from argus.eval.ablation import NOISE_LEVELS, run_ablation_sweep


def test_ablation_sweep_runs_and_produces_nonempty_metrics(tmp_path):
    df = run_ablation_sweep(tmp_path)

    assert len(df) == len(NOISE_LEVELS) * 2  # 3 noise levels x 2 conditions
    assert set(df["condition"]) == {"dual_layer", "on_chain_only"}
    assert set(df["noise_level"]) == set(NOISE_LEVELS)

    metric_cols = [
        "er_precision",
        "er_recall",
        "er_f1",
        "peeling_recall",
        "peeling_precision",
        "coinjoin_recall",
        "coinjoin_precision",
        "risk_precision_at_50",
    ]
    for col in metric_cols:
        assert col in df.columns
        assert not df[col].isna().any(), f"{col} produced a NaN — non-empty output required for every metric"


def test_ablation_shows_no_measurable_dual_layer_difference(tmp_path):
    """Documents the actual finding, doesn't just assume it: none of the
    classical detectors in this repo read BROADCAST_VIA/RESOLVES_TO edges or
    node_features.parquet columns, so dropping them changes nothing. If a
    future detector starts consuming that signal, this test should start
    failing — which is the correct, informative outcome, not a false alarm.
    """
    df = run_ablation_sweep(tmp_path)
    metric_cols = [
        "er_precision",
        "er_recall",
        "er_f1",
        "peeling_recall",
        "peeling_precision",
        "coinjoin_recall",
        "coinjoin_precision",
        "risk_precision_at_50",
    ]

    for noise_level in NOISE_LEVELS:
        rows = df[df["noise_level"] == noise_level]
        dual = rows[rows["condition"] == "dual_layer"].iloc[0]
        onchain = rows[rows["condition"] == "on_chain_only"].iloc[0]
        for col in metric_cols:
            assert math.isclose(dual[col], onchain[col], abs_tol=1e-9), (
                f"{col} differs between conditions at noise_level={noise_level} "
                f"({dual[col]} vs {onchain[col]}) — unexpected given no detector reads network-layer signal"
            )
