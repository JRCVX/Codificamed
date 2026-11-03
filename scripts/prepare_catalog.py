"""Genera el catálogo CIE-10 procesado y el vocabulario clínico.

Entradas:
    data/raw/codiesp_codes/codiesp-D_codes.tsv

Salidas:
    data/catalog/cie10_d_codes.tsv      catálogo con cabecera
    data/catalog/clinical_vocab.txt     vocabulario para corrección de typos
    reports/catalog_summary.json        métricas reproducibles

Los marcadores de capítulo ``CAP.xx`` no son códigos facturables y se excluyen.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_CATALOG = PROJECT_ROOT / "data" / "raw" / "codiesp_codes" / "codiesp-D_codes.tsv"
OUTPUT_CATALOG = PROJECT_ROOT / "data" / "catalog" / "cie10_d_codes.tsv"
OUTPUT_VOCAB = PROJECT_ROOT / "data" / "catalog" / "clinical_vocab.txt"
OUTPUT_SUMMARY = PROJECT_ROOT / "reports" / "catalog_summary.json"

CODE_PATTERN = re.compile(r"^[A-Z][0-9][A-Z0-9](?:\.[A-Z0-9]{1,4})?$")
WORD_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_CATALOG)
    parser.add_argument("--catalog", type=Path, default=OUTPUT_CATALOG)
    parser.add_argument("--vocab", type=Path, default=OUTPUT_VOCAB)
    parser.add_argument("--summary", type=Path, default=OUTPUT_SUMMARY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.raw.is_file():
        raise SystemExit(f"No existe el catálogo crudo: {args.raw}")

    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    excluded_markers: list[str] = []
    invalid: list[str] = []
    duplicate: list[str] = []

    with args.raw.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for line_number, row in enumerate(reader, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) < 2:
                invalid.append(f"línea {line_number}: columnas insuficientes")
                continue

            code = row[0].strip().upper()
            description_es = row[1].strip()
            description_en = row[2].strip() if len(row) > 2 else ""

            if code.startswith("CAP."):
                excluded_markers.append(code)
                continue
            if not CODE_PATTERN.match(code):
                invalid.append(f"línea {line_number}: código {code!r}")
                continue
            if not description_es:
                invalid.append(f"línea {line_number}: descripción vacía para {code}")
                continue
            if code in seen:
                duplicate.append(code)
                continue

            seen.add(code)
            rows.append((code, description_es, description_en))

    if invalid:
        raise SystemExit(f"Catálogo inválido ({len(invalid)}): {invalid[:5]}")
    if duplicate:
        raise SystemExit(f"Códigos duplicados ({len(duplicate)}): {sorted(set(duplicate))[:10]}")
    if not rows:
        raise SystemExit("El catálogo procesado quedaría vacío")

    args.catalog.parent.mkdir(parents=True, exist_ok=True)
    with args.catalog.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("code", "description_es", "description_en"))
        writer.writerows(rows)

    counter: Counter[str] = Counter()
    for _, description_es, description_en in rows:
        for word in WORD_PATTERN.findall(f"{description_es} {description_en}".lower()):
            counter[word] += 1

    args.vocab.parent.mkdir(parents=True, exist_ok=True)
    with args.vocab.open("w", encoding="utf-8") as handle:
        for word in sorted(counter):
            handle.write(f"{word}\n")

    summary = {
        "raw_rows": len(rows) + len(excluded_markers),
        "valid_codes": len(rows),
        "excluded_markers": sorted(excluded_markers),
        "invalid_rows": invalid,
        "duplicate_codes": sorted(set(duplicate)),
        "vocabulary_terms": len(counter),
        "catalog_path": str(args.catalog.relative_to(PROJECT_ROOT)),
        "vocab_path": str(args.vocab.relative_to(PROJECT_ROOT)),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"OK catálogo: {len(rows):,} códigos -> {args.catalog}")
    print(f"OK vocabulario: {len(counter):,} términos -> {args.vocab}")
    print(f"Marcadores CAP excluidos: {len(excluded_markers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
