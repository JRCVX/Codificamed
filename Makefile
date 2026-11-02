PYTHON ?= .venv/bin/python
UV ?= uv
PY_VERSION ?= 3.11.17

.PHONY: help setup data audit figures test lint smoke app clean

help:
	@echo "CodificaMed — comandos disponibles"
	@echo "  make setup     Crea .venv con Python $(PY_VERSION) e instala dependencias"
	@echo "  make data      Descarga y verifica CodiEsp desde Zenodo"
	@echo "  make audit     Audita catálogo, corpus y spans"
	@echo "  make figures   Genera el diagrama de arquitectura"
	@echo "  make test      Ejecuta pytest (sin tests de red)"
	@echo "  make lint      Ejecuta ruff"
	@echo "  make smoke     Verificación mínima de imports y configuración"
	@echo "  make app       Lanza Streamlit (fase 5)"
	@echo "  make clean     Elimina cachés de Python y pytest"

setup:
	$(UV) venv --python $(PY_VERSION) --clear .venv
	$(UV) pip install --python .venv/bin/python --index-strategy unsafe-best-match -r requirements-dev.txt

data:
	$(PYTHON) scripts/download_data.py

audit:
	$(PYTHON) scripts/audit_data.py

figures:
	$(PYTHON) scripts/make_figures.py

test:
	$(PYTHON) -m pytest -m "not network" -q

lint:
	.venv/bin/ruff check src scripts tests app

smoke:
	$(PYTHON) scripts/smoke_test.py

app:
	$(PYTHON) -m streamlit run app/streamlit_app.py

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
