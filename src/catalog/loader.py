"""Carga y validación del catálogo CIE-10 procesado.

El catálogo procesado se genera con ``scripts/prepare_catalog.py`` y contiene
una cabecera ``code``, ``description_es``, ``description_en``. El cargador
rechaza duplicados y códigos con formato inválido para que ningún módulo aguas
abajo trabaje con un catálogo inconsistente.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from pathlib import Path

from src.catalog.models import CatalogEntry

# ICD-10-CM permite letras en la tercera posición (p. ej. C4A, C7A, D3A).
CODE_PATTERN = re.compile(r"^[A-Z][0-9][A-Z0-9](?:\.[A-Z0-9]{1,4})?$")
HEADER = ("code", "description_es", "description_en")


class CatalogError(ValueError):
    """Error de integridad del catálogo."""


class Catalog:
    """Catálogo inmutable en memoria, indexado por código."""

    def __init__(self, entries: dict[str, CatalogEntry], source: Path | None = None) -> None:
        if not entries:
            raise CatalogError("El catálogo no puede estar vacío")
        self._entries = entries
        self.source = source

    @classmethod
    def from_tsv(cls, path: Path | str, *, validate: bool = True) -> Catalog:
        """Carga un TSV con cabecera o sin ella.

        Si la primera fila empieza por ``code`` se trata como cabecera. En caso
        contrario se asume el orden ``code, description_es, description_en``.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"No existe el catálogo: {path}")

        entries: dict[str, CatalogEntry] = {}
        duplicates: list[str] = []
        invalid: list[str] = []

        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            for line_number, row in enumerate(reader, start=1):
                if not row or not any(cell.strip() for cell in row):
                    continue
                if line_number == 1 and row[0].strip().lower() == "code":
                    continue
                if len(row) < 2:
                    invalid.append(f"línea {line_number}: se esperaban al menos 2 columnas")
                    continue

                code = row[0].strip().upper()
                description_es = row[1].strip()
                description_en = row[2].strip() if len(row) > 2 and row[2].strip() else None

                if validate and not CODE_PATTERN.match(code):
                    invalid.append(f"línea {line_number}: código inválido {code!r}")
                    continue
                if not description_es:
                    invalid.append(f"línea {line_number}: descripción vacía para {code}")
                    continue
                if code in entries:
                    duplicates.append(code)
                    continue

                entries[code] = CatalogEntry(
                    code=code,
                    description_es=description_es,
                    description_en=description_en,
                )

        if invalid:
            preview = "; ".join(invalid[:5])
            raise CatalogError(f"Catálogo inválido ({len(invalid)} problemas): {preview}")
        if duplicates:
            preview = ", ".join(sorted(set(duplicates))[:10])
            raise CatalogError(f"Códigos duplicados ({len(set(duplicates))}): {preview}")
        if not entries:
            raise CatalogError(f"El catálogo está vacío: {path}")

        return cls(entries, source=path)

    def get(self, code: str) -> CatalogEntry | None:
        """Devuelve la entrada o ``None`` si el código no existe."""
        return self._entries.get(code.strip().upper())

    def require(self, code: str) -> CatalogEntry:
        """Devuelve la entrada o lanza ``KeyError`` con un mensaje claro."""
        normalized = code.strip().upper()
        try:
            return self._entries[normalized]
        except KeyError as exc:
            raise KeyError(f"Código no presente en el catálogo: {normalized}") from exc

    def contains(self, code: str) -> bool:
        return code.strip().upper() in self._entries

    def codes(self) -> list[str]:
        return list(self._entries)

    def entries(self) -> Iterator[CatalogEntry]:
        return iter(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, code: object) -> bool:
        return isinstance(code, str) and self.contains(code)

    def __repr__(self) -> str:
        return f"Catalog(entries={len(self._entries)}, source={self.source!r})"
