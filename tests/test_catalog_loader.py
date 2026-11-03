"""Pruebas del cargador de catálogo."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.catalog.loader import Catalog, CatalogError


def _write_tsv(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_load_catalog_with_header(tmp_path: Path) -> None:
    path = _write_tsv(
        tmp_path / "catalog.tsv",
        "code\tdescription_es\tdescription_en\n"
        "I10\tHipertensión esencial\tEssential hypertension\n"
        "E11.9\tDiabetes mellitus tipo 2\tType 2 diabetes\n",
    )
    catalog = Catalog.from_tsv(path)
    assert len(catalog) == 2
    assert catalog.get("i10") is not None
    assert catalog.get("I10").description_es == "Hipertensión esencial"  # type: ignore[union-attr]
    assert "E11.9" in catalog
    assert catalog.get("NOEXISTE") is None


def test_load_catalog_without_header(tmp_path: Path) -> None:
    path = _write_tsv(
        tmp_path / "catalog.tsv",
        "C4A.0\tTumor carcinoide de intestino delgado\t\n"
        "A09\tDiarrea y gastroenteritis de presunto origen infeccioso\t\n",
    )
    catalog = Catalog.from_tsv(path)
    assert len(catalog) == 2
    assert catalog.get("C4A.0") is not None
    assert catalog.get("A09") is not None


def test_duplicate_code_is_rejected(tmp_path: Path) -> None:
    path = _write_tsv(
        tmp_path / "catalog.tsv",
        "I10\tHipertensión\t\nI10\tOtra descripción\t\n",
    )
    with pytest.raises(CatalogError, match="duplicados"):
        Catalog.from_tsv(path)


def test_invalid_code_is_rejected(tmp_path: Path) -> None:
    path = _write_tsv(tmp_path / "catalog.tsv", "CAP.02\tCapítulo\t\n")
    with pytest.raises(CatalogError, match="inválido"):
        Catalog.from_tsv(path)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Catalog.from_tsv(tmp_path / "no-existe.tsv")


def test_require_reports_unknown_code(tmp_path: Path) -> None:
    path = _write_tsv(tmp_path / "catalog.tsv", "I10\tHipertensión\t\n")
    catalog = Catalog.from_tsv(path)
    with pytest.raises(KeyError, match="Z99"):
        catalog.require("Z99")


def test_processed_catalog_if_available() -> None:
    path = Path("data/catalog/cie10_d_codes.tsv")
    if not path.is_file():
        pytest.skip("Ejecutar scripts/prepare_catalog.py para la prueba de integración")
    catalog = Catalog.from_tsv(path)
    assert len(catalog) == 98_268
    assert catalog.require("I10").description_es.startswith("Hipertensión")
    assert catalog.require("E11.9").description_es.startswith("Diabetes mellitus tipo 2")
    assert catalog.require("A09").description_es.startswith("Gastroenteritis")
