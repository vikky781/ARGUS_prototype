# ARGUS — Dev A Write-Up

This document covers **Dev A's owned sections only** (SIH26146 / NTRO Bitcoin transaction
monitoring, team Doomsbyte). See `CLAUDE.md` for the exact scope boundary and the list of
files this repo deliberately never implements. Dev B's sections are left as marked TODOs
below — not drafted here.

## Scale tested

All results in this document are from the scale configured in `configs/default.yaml`:

- 2,000 entities, 50,000 wallets
- 200,000 baseline transactions + several hundred planted illicit-pattern transactions
  (200,784 total in the run these numbers come from)
- Raw exports at this scale: ~46 MB CSV, ~120 MB JSON, ~159 MB XML

This is **not** the plan's optional 1M-transaction stretch goal, which was not attempted (per
instruction — see `docs/offline_install.md`'s sibling scale note, or the section below). A
rough scaling estimate for 1M transactions (5x this run):

- Raw export sizes scale roughly linearly with row count: ~230 MB CSV, ~600 MB JSON, ~800 MB
  XML — the XML format in particular becomes a meaningful disk-space and parse-time cost at
  that scale, more so than the other two.
- Graph size scales with transaction count too: this run produced ~343k nodes / ~824k edges;
  5x would land near ~1.7M nodes / ~4M edges, still well within what `python-igraph`'s C
  backend handles in memory on ordinary hardware, but `node_features.parquet` and
  `graph_edges.parquet` would grow proportionally (a few hundred MB each).
- The full pipeline (`data` through `fusion`) took 1.5-3.5 minutes wall-clock at 200k
  transactions on the development machine across several runs; naive linear scaling would put
  1M transactions at roughly 10-20 minutes, though several stages (ER pass 1's transaction
  scan, feature engineering's per-wallet grouping) are closer to O(n) than O(n²), so this is
  a rough upper bound rather than a hard prediction.
- This was not run. If asked to attempt 1M transactions, expect to hit the Windows long-path
  `pip install` issue documented in the Phase 1 fresh-clone verification again if working from
  a deeply-nested directory — unrelated to scale, but worth flagging alongside it.

## Data generation & ingestion

`src/argus/synth/` generates a fully-seeded synthetic dataset: entities (licit, exchange,
ransomware, darknet, mixer), wallets, and transactions, with an IP-subnet affinity and
broadcast-time profile per entity, three illicit structural patterns (peeling chains, CoinJoin
rounds, ransomware collect→layer→cash-out lifecycles), a known-illicit seed set, and
deliberate small-scale data-quality corruption (~0.5% of baseline rows: bad checksum, negative
amount, unparseable timestamp) — all exported identically to CSV, JSON, and XML.

`src/argus/ingest/` streams all three formats back in (`csv.DictReader`, `ijson`,
`lxml.iterparse` — never loading a whole file into memory), rejects the corrupted rows to
`data/artifacts/rejects.log` with a specific reason per row (never silently dropped), enriches
each row with `geo_country`/`asn` via an offline synthetic GeoIP lookup (see
`src/argus/ingest/geoip.py`'s docstring for why this is not a real MaxMind database — the
dataset's IPs are synthetic, so a real lookup would be meaningless), and writes the validated
rows to `canonical/transactions.parquet` with exactly the contracted columns. A dedicated test
(`test_cross_format_equality`) asserts all three input formats parse to row-for-row identical
canonical output.

## Entity resolution (pass 1)

`src/argus/er/union_find.py` implements the two classical heuristics — common-input-ownership
and change-address-return — over a Union-Find structure, with an explicit structural guard
against CoinJoin over-merging (transactions with many distinct FUNDS inputs and many
near-equal-value PAYS outputs are skipped for the common-input heuristic).

**Measured result: precision 1.0000, recall 0.0000.** This is not a bug being hidden — it's a
real, verified finding. The only transactions in this dataset with more than one genuinely
distinct input wallet are CoinJoin rounds, which the guard must skip; every other transaction
either has a single input or repeats the same wallet as "multiple inputs." The change-address
heuristic only ever fires when an output literally equals one of the transaction's own inputs
— in this dataset, that only happens when it's the same wallet (baseline's own change output),
never two different wallets. Net effect: heuristic 1 has zero real material to act on once the
CoinJoin guard is applied, and heuristic 2 never produces a new cross-wallet link. Every wallet
resolves to its own singleton cluster, `CO_SPEND` edges never materialize (0 in every run of
this generator), and precision is a vacuous 1.0 (zero false merges among zero merges) rather
than a real success. See the Phase 2 commit message and this repo's test suite
(`tests/test_er.py`) for the same finding, verified directly against the canonical data before
any code was written to explain it away.

This has a direct, documented downstream consequence: `src/argus/detectors/risk_ppr.py`'s
seeded Personalized PageRank propagates over `CO_SPEND` edges only (the architecture doc's
`SAME_ENTITY` edge type is Dev B's, never produced here) — with zero `CO_SPEND` edges, that
propagation is currently a no-op beyond the seed set itself. `docs/contracts.md` documents
both limitations explicitly.

## Classical pattern detection

`src/argus/detectors/peeling.py` walks `FUNDS`/`PAYS` edges to find single-input,
single-dominant-output transaction chains with strictly decreasing value hop-over-hop.
`src/argus/detectors/coinjoin.py` flags transactions with many distinct `FUNDS` inputs and
many near-equal-value `PAYS` outputs (the same structural check ER pass 1 uses for its guard,
shared as a single source of truth).

**Measured result** (full dataset, overlap-based matching against
`ground_truth/patterns.parquet`): peeling recall 1.0000 / precision 0.9836 (60/61 detected
chains correct); CoinJoin recall 1.0000 / precision 1.0000.

The peeling detector went through a real debugging cycle worth recording here, not just the
final number: an early version's "value must decrease" check compared a hop's output against
that same transaction's own input, which is trivially true for any transaction with a positive
fee and provided no actual discrimination — precision was 0.008 (4,365 false positives from
purely coincidental baseline structure). Requiring genuine amount continuity between
consecutive hops (next hop's input must match the previous hop's output to within 2%) fixed
that, but surfaced two further bugs in how chain "start" wallets were selected (picking the
largest-amount candidate could lock onto an unrelated coincidental transaction instead of the
real chain; a wallet whose own baseline "change" output happened to be dominant was wrongly
excluded as a candidate start because it looked like someone else's target). Fixing both
brought recall to 1.0 with precision 0.28; the final fix — requiring at least 3 hops, matching
`argus.synth.patterns.PEELING_HOP_RANGE`'s actual minimum — removed all but one residual false
positive, a single coincidental 3-hop chain that is expected statistical noise at this scale.

CoinJoin detection reached perfect scores immediately because it reuses the exact structural
check ER pass 1 already uses, and CoinJoin rounds are provably the only transactions in this
dataset with ≥3 genuinely distinct input wallets.

## Ablation: dual-layer vs on-chain-only

`src/argus/eval/ablation.py` reruns ER/pattern/risk metrics with `BROADCAST_VIA`/`RESOLVES_TO`
edges dropped, swept across `ip_noise ∈ {0.01, 0.05, 0.20}` ("low"/"medium"/"high"). Results:
`docs/ablation_results.csv` (raw), `docs/ablation_plot.png` (plot).

**Every metric is byte-identical between the `dual_layer` and `on_chain_only` conditions, at
every noise level tested.** This was verified directly, not assumed: `grep` across
`er/union_find.py`, `detectors/peeling.py`, `detectors/coinjoin.py`, and
`detectors/risk_ppr.py` found zero references to `BROADCAST_VIA`, `RESOLVES_TO`, or
`node_features.parquet` anywhere. None of the classical detectors implemented in this repo
were ever wired to consume network-layer or cross-layer signal — they operate purely on
`FUNDS`/`PAYS`/`CO_SPEND` and raw canonical amounts. The dual-layer graph and cross-layer
features (`f_ip_reuse_count`, `f_entity_asn_entropy`, `f_geo_hop_count`/`f_geo_hop_rate`) are
correctly computed and NaN-free (Phase 2), but nothing downstream currently reads them for a
detection decision.

This is the honest, unadjusted result. Per instruction, the generator and detectors were not
modified to manufacture a difference. If dual-layer signal is to demonstrate measurable value,
it needs a detector that actually incorporates it — e.g. a peeling-chain confidence adjustment
based on IP reuse across hops, or an ER heuristic considering shared broadcast infrastructure
— which does not exist in this repo as of this write-up.

## Score fusion

`src/argus/fusion/blend.py` combines `scores_pattern`, `scores_risk`, and a documented,
explicitly-labeled placeholder `scores_anomaly` (fixed 0.5 for every node — Dev B's
`models/anomaly.py` is out of scope; see `docs/contracts.md`) via a logistic regression
calibrated on `ground_truth/entities.parquet`'s labels when enough labeled nodes exist (both
paths — calibrated and fixed-weight fallback — are implemented and tested). The resulting
fused-score distribution is bimodal: pattern-only detections cluster near 0.67, risk-only
detections (currently just the seed set, per the ER finding above) cluster near 0.9998, with
nothing between. The alert threshold (0.6) was set below both clusters specifically to avoid
the wrong prioritization a naively "high" threshold would create — it would keep the trivial
seed-echo cluster while dropping the real structural detections. See `blend.py`'s inline
comments for the full reasoning.

## Offline / install

See `docs/offline_install.md` for the offline-runtime verification procedure, what was
actually run and how, and the codebase audit for accidental network calls.

---

## Dev B's sections (out of scope in this repo — not drafted)

- **TODO (Dev B): Temporal hetero GAT-v2 encoder** (`models/encoder.py`)
- **TODO (Dev B): Graph autoencoder anomaly detection** (`models/anomaly.py`) — this repo only
  ships a documented placeholder; see "Score fusion" above and `docs/contracts.md`.
- **TODO (Dev B): ER pass 2 — GraphSAGE + HDBSCAN embedding-based clustering**
  (`er/embed_cluster.py`) — would be the natural next step given pass 1's diagnosed 0.0
  recall on this dataset.
- **TODO (Dev B): Embedding-similarity pattern detector** (`detectors/pattern_sim.py`)
- **TODO (Dev B): Attention-based evidence extractor** (`fusion/evidence.py`)
- **TODO (Dev B): Full rationale-templating engine** (`fusion/rationale.py`) — this repo only
  ships a simple fixed-template rationale string; see `fusion/blend.py`'s docstring.
- **TODO (Dev B): Streamlit dashboard** (`dashboard/`)
