#!/usr/bin/env python3
"""Verificación mínima de que el esqueleto y la configuración funcionan.

Uso:
    python scripts/smoke_test.py
"""

from __future__ import annotations

import importlib
import importlib.metadata as metadata
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src  # noqa: E402
from src.config import Settings  # noqa: E402


def paquete_version(nombre: str) -> str:
    try:
        return metadata.version(nombre)
    except metadata.PackageNotFoundError:
        return "no instalado"


def main() -> int:
    errores: list[str] = []
    print("CodificaMed — smoke test")
    print(f"Python: {sys.version.split()[0]}")
    if sys.version_info[:2] != (3, 11):
        errores.append("Se esperaba Python 3.11")
    print(f"CodificaMed: {src.__version__}")
    print(f"pydantic: {paquete_version('pydantic')}")
    print(f"pydantic-settings: {paquete_version('pydantic-settings')}")

    for paquete in (
        "src.preprocess",
        "src.catalog",
        "src.retrieval",
        "src.negation",
        "src.ner",
        "src.llm",
        "src.pipeline",
        "src.eval",
    ):
        try:
            importlib.import_module(paquete)
        except Exception as exc:  # noqa: BLE001
            errores.append(f"No se pudo importar {paquete}: {exc}")

    settings = Settings()
    settings.ensure_directories()
    print(f"Proveedor por defecto: {settings.llm_provider} / {settings.llm_model}")
    print(f"Catálogo configurado: {settings.catalog_path}")
    print(f"Índice configurado: {settings.faiss_index_path}")

    env_example = ROOT / ".env.example"
    if not env_example.is_file():
        errores.append("Falta .env.example")
    else:
        texto = env_example.read_text(encoding="utf-8")
        for patron in ("sk-", "sk-ant-", "AIza"):
            if patron in texto:
                errores.append(f"Posible clave real en .env.example: {patron}")

    for ruta in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "docs/ESTADO.md"):
        if not (ROOT / ruta).is_file():
            errores.append(f"Falta {ruta}")

    if errores:
        print("\nERRORES:")
        for error in errores:
            print(f"  - {error}")
        return 1

    print("\nOK: esqueleto, imports y configuración válidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
