# CLAUDE.md

## Scope: Dev A only

This repository implements **only "Dev A"'s half** of the ARGUS project (SIH26146 / NTRO Bitcoin
transaction monitoring, team Doomsbyte). Dev A owns: synthetic data generation, ingestion,
dual-layer graph construction, entity resolution pass 1, feature engineering, classical pattern
detectors (peeling/CoinJoin), seeded PageRank risk scoring, score fusion, and the evaluation
harness.

**Dev B's modules are never implemented in this repo.** If any future prompt seems to ask for one
of these, stop and tell the user instead of doing it. The excluded files are:

- `models/encoder.py` (temporal hetero GAT-v2)
- `models/anomaly.py` (graph autoencoder)
- `models/sage.py` + `er/embed_cluster.py` (GraphSAGE + HDBSCAN, ER pass 2)
- `detectors/pattern_sim.py` (embedding-similarity pattern variant)
- `fusion/evidence.py` (attention-based evidence extractor)
- `fusion/rationale.py` (full rationale templating engine)
- `dashboard/` (Streamlit app)

## Repo layout

```
Makefile
requirements.txt
configs/default.yaml
data/                       (gitignored: raw, canonical, ground_truth, artifacts, geoip)
src/argus/synth/
src/argus/ingest/
src/argus/graph/
src/argus/er/
src/argus/features/
src/argus/detectors/
src/argus/fusion/
src/argus/eval/
tests/
docs/
```

See `docs/contracts.md` for the exact data contracts (schemas) between pipeline stages.

## Offline requirement

**No step in this repo may make a network call at pipeline runtime.** Install-time package
downloads (e.g. `pip install`) are fine. Runtime calls (data generation, ingestion, graph
construction, entity resolution, feature engineering, detection, fusion, evaluation) are not.
