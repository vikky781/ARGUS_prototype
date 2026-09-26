VENV := .venv

ifeq ($(OS),Windows_NT)
VENV_BIN := $(VENV)/Scripts
else
VENV_BIN := $(VENV)/bin
endif

PY_CREATE := $(shell command -v py >/dev/null 2>&1 && echo "py -3.12" || echo python3)
PY := $(shell if [ -x "$(VENV_BIN)/python" ] || [ -x "$(VENV_BIN)/python.exe" ]; then echo "$(VENV_BIN)/python"; else echo python; fi)

.PHONY: env test data ingest graph er features detect fusion eval pipeline

env:
	$(PY_CREATE) -m venv $(VENV)
	"$(VENV_BIN)/python" -m pip install --upgrade pip
	"$(VENV_BIN)/python" -m pip install -r requirements.txt

test:
	@"$(PY)" -m pytest tests/ -v; ec=$$?; if [ $$ec -eq 5 ]; then exit 0; else exit $$ec; fi

data:
	PYTHONPATH=src "$(PY)" -m argus.synth.cli

ingest: data
	PYTHONPATH=src "$(PY)" -m argus.ingest.cli

graph: ingest
	PYTHONPATH=src "$(PY)" -m argus.graph.cli

er: graph
	PYTHONPATH=src "$(PY)" -m argus.er.cli

features: er
	PYTHONPATH=src "$(PY)" -m argus.features.cli

detect: features
	PYTHONPATH=src "$(PY)" -m argus.detectors.cli

fusion: detect
	PYTHONPATH=src "$(PY)" -m argus.fusion.cli

eval: graph
	PYTHONPATH=src "$(PY)" -m argus.eval.cli

# data -> ingest -> graph -> er -> features -> detect -> fusion, via the
# existing dependency chain above. Named "pipeline", not "demo": there is no
# dashboard here (Dev B's, out of scope), so this is not a complete
# end-user-facing deliverable, just the full Dev-A pipeline through alerts.json.
pipeline: fusion
	@echo "pipeline complete: data/artifacts/alerts.json"
