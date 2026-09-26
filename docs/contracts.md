# ARGUS Data Contracts

These are the exact data contracts between pipeline stages. Do not add, remove, or reinterpret
any column without updating this document and getting explicit sign-off — downstream stages are
written against these schemas verbatim.

## `canonical/transactions.parquet`

Producer: `ingest`. One row per transaction event.

- `txid` (string, primary key)
- `timestamp` (datetime, UTC)
- `src_ip` (string)
- `dst_ip` (string)
- `src_port` (int)
- `dst_port` (int)
- `geo_country` (string)
- `asn` (int)
- `input_addresses` (array<string>)
- `input_amounts` (array<float>)
- `output_addresses` (array<string>)
- `output_amounts` (array<float>)
- `fee` (float)
- `script_type` (string)

## Graph schema

Artifacts: `artifacts/graph.pkl` + `artifacts/graph_edges.parquet`. Producer: `graph`.

**Nodes:** `Wallet`, `Transaction`, `IP`, `ASN`

**Edges:**

| Edge | Direction | Meaning | Attrs |
|---|---|---|---|
| `FUNDS` | `Wallet -> Tx` | tx input | `amount` |
| `PAYS` | `Tx -> Wallet` | tx output | `amount` |
| `BROADCAST_VIA` | `Tx -> IP` | first-seen relay | `timestamp`, `port` |
| `RESOLVES_TO` | `IP -> ASN` | geo enrichment | static |
| `CO_SPEND` | `Wallet <-> Wallet` | ER pass 1, Dev A | `confidence` |
| `SAME_ENTITY` | `Wallet <-> Wallet` | ER pass 2, Dev B — **NOT produced in this repo** | `confidence` ∈ [0,1] |

This repo produces `FUNDS`, `PAYS`, `BROADCAST_VIA`, `RESOLVES_TO` (from graph build) and
`CO_SPEND` (from ER pass 1). `SAME_ENTITY` is never produced here.

## `ground_truth/entities.parquet`

Producer: `synth`.

- `wallet_id`
- `entity_id`
- `entity_type` (licit/ransomware/darknet/mixer/exchange)

## `ground_truth/seeds.parquet`

Producer: `synth`. Known-illicit seed set, ~5-10% of illicit wallets.

- `wallet_id`

## `ground_truth/patterns.parquet`

Producer: `synth`.

- `pattern_id`
- `type` (peeling/coinjoin)
- `txids[]`
- `wallets[]`

## `artifacts/entities.parquet`

Producer: ER pass 1 only, in this repo.

- `wallet_id`
- `entity_id`
- `source` (always `"pass1"` here)
- `conf`
- `merge_split_log_ref`

## `artifacts/node_features.parquet`

Producer: `features`.

- `node_id`
- `node_type`
- `f_*` numeric columns
- no NaNs

## `artifacts/scores_pattern.parquet`

Producer: `detectors/peeling.py` + `detectors/coinjoin.py` (classical only).

- `node_id`
- `score` ∈ [0,1]
- `reason_code`
- `evidence_json`

## `artifacts/scores_risk.parquet`

Producer: `detectors/risk_ppr.py`.

- `node_id`
- `score` ∈ [0,1]
- `reason_code` (`SEED_DIST=n`)
- `evidence_json`

**Scope limitation (permanent, by design):** the architecture doc specifies personalized
PageRank propagation over `CO_SPEND` + `SAME_ENTITY` edges. This repo never produces
`SAME_ENTITY` edges — that is Dev B's ER pass 2 (`er/embed_cluster.py`, out of scope here).
`detectors/risk_ppr.py` propagates over `CO_SPEND` only. As of Phase 3, ER pass 1 also
produces zero `CO_SPEND` edges on this dataset (see the Phase 2 ER precision/recall
diagnosis), so this head currently reduces to reporting the seed set itself
(`SEED_DIST=0` for every row) with no further graph propagation — not a bug in
`risk_ppr.py`, a direct consequence of the upstream `CO_SPEND` count.

## `artifacts/scores_anomaly.parquet`

Producer: `fusion/_anomaly_placeholder.py` — **NOT a real anomaly model**. Dev B's
`models/anomaly.py` (graph autoencoder) is out of scope in this repo. This file exists
only so `fusion/blend.py` has a contract-valid input to read: every node gets a fixed
neutral score of 0.5, `reason_code=ANOMALY_PLACEHOLDER`. When Dev B's real model lands,
it replaces this file's producer; `blend.py` does not need to change.

- `node_id`
- `score` ∈ [0,1] (always exactly 0.5)
- `reason_code` (always `ANOMALY_PLACEHOLDER`)
- `evidence_json`

## `artifacts/alerts.json`

Producer: `fusion`.

- `alert_id`
- `node_id`
- `final_score`
- `components` `{pattern, risk, anomaly}`
- `evidence` `{nodes[], edges[]}`
- `rationale`

## Hard rule

Every head must emit `reason_code` + `evidence_json` — no exceptions, no retrofitting later. This
is a stated hard rule from the project plan.
