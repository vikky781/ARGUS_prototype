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

graph:
	@echo "not implemented yet"

er:
	@echo "not implemented yet"

features:
	@echo "not implemented yet"

detect:
	@echo "not implemented yet"

fusion:
	@echo "not implemented yet"

eval:
	@echo "not implemented yet"

pipeline:
	@echo "not implemented yet"
