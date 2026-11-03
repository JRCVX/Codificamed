PYTHON ?= .venv/bin/python
UV ?= uv
PY_VERSION ?= 3.11.17
HOST ?= 0.0.0.0
PORT ?= 8010

.PHONY: help setup data audit index retrieval-eval figures test lint smoke api clean

help:
	@echo "CodificaMed — comandos disponibles"
	@echo "  make setup     Crea .venv con Python $(PY_VERSION) e instala dependencias"
	@echo "  make data      Descarga y verifica CodiEsp desde Zenodo"
	@echo "  make audit     Audita catálogo, corpus y spans"
	@echo "  make index     Construye el índice denso FAISS del catálogo"
	@echo "  make retrieval-eval Evalúa recall@30 en CodiEsp dev"
	@echo "  make figures   Genera el diagrama de arquitectura"
	@echo "  make test      Ejecuta pytest (sin tests de red)"
	@echo "  make lint      Ejecuta ruff"
	@echo "  make smoke     Verificación mínima de imports y configuración"
	@echo "  make api       Lanza la API FastAPI y sirve el frontend desde frontend/"
	@echo "  make clean     Elimina cachés de Python y pytest"

setup:
	$(UV) venv --python $(PY_VERSION) --clear .venv
	$(UV) pip install --python .venv/bin/python --index-strategy unsafe-best-match -r requirements-dev.txt

data:
	$(PYTHON) scripts/download_data.py

audit:
	$(PYTHON) scripts/audit_data.py

index:
	$(PYTHON) scripts/build_index.py

retrieval-eval:
	$(PYTHON) scripts/evaluate_retrieval.py

figures:
	$(PYTHON) scripts/make_figures.py

test:
	$(PYTHON) -m pytest -m "not network" -q

lint:
	.venv/bin/ruff check src scripts tests app

smoke:
	$(PYTHON) scripts/smoke_test.py

api:
	PORT=$(PORT) $(PYTHON) -m uvicorn backend.main:app --host $(HOST) --port $(PORT) --reload

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
