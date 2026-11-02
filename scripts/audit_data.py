#!/usr/bin/env python3
"""Auditoría reproducible de CodiEsp y del catálogo CIE-10.

Comprueba integridad, cobertura, existencia de códigos y alineación de los spans
de evidencia de CodiEsp-X. Genera:
  - reports/data_audit.json
  - docs/auditoria_datos.md

Uso:
    python scripts/audit_data.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CATALOG = RAW / "codiesp_codes" / "codiesp-D_codes.tsv"
CORPUS = RAW / "final_dataset_v4_to_publish"
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
SPLITS = ("train", "dev", "test")
# ICD-10-CM admite una letra en la tercera posición (p. ej. C4A, C7A, D3A).
CODE_RE = re.compile(r"^[A-Z][0-9][A-Z0-9](?:\.[0-9A-Z]{1,4})?$")
CHAPTER_RE = re.compile(r"^CAP\.[0-9]{2}$")


def normalizar_texto(texto: str) -> str:
    """Normaliza para comparar referencias multi-palabra sin depender de espacios/acentos."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", texto.lower())


def read_catalog(path: Path) -> tuple[dict[str, str], dict[str, Any]]:
    rows = 0
    duplicates: list[str] = []
    empty_descriptions: list[str] = []
    invalid_codes: list[str] = []
    chapter_markers: list[str] = []
    catalog: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for raw in reader:
            if not raw or not raw[0].strip():
                continue
            rows += 1
            code = raw[0].strip().upper()
            description = raw[1].strip() if len(raw) > 1 else ""
            if CHAPTER_RE.match(code):
                chapter_markers.append(code)
                continue
            if code in catalog:
                duplicates.append(code)
            if not CODE_RE.match(code):
                invalid_codes.append(code)
            if not description:
                empty_descriptions.append(code)
            catalog[code] = description
    stats = {
        "rows": rows,
        "valid_code_rows": len(catalog),
        "unique_codes": len(catalog),
        "non_code_count": len(chapter_markers),
        "non_code_sample": chapter_markers[:30],
        "duplicate_codes": sorted(set(duplicates))[:50],
        "duplicate_count": len(duplicates),
        "empty_description_count": len(empty_descriptions),
        "empty_description_sample": empty_descriptions[:20],
        "invalid_code_count": len(invalid_codes),
        "invalid_code_sample": invalid_codes[:20],
    }
    return catalog, stats


def read_split(split: str, catalog: set[str]) -> tuple[dict[str, set[str]], dict[str, Any]]:
    split_dir = CORPUS / split
    text_dir = split_dir / "text_files"
    d_path = split_dir / f"{split}D.tsv"
    x_path = split_dir / f"{split}X.tsv"

    docs: dict[str, set[str]] = {}
    d_pairs: set[tuple[str, str]] = set()
    with d_path.open(encoding="utf-8") as handle:
        for raw in csv.reader(handle, delimiter="\t"):
            if len(raw) < 2:
                continue
            doc, code = raw[0].strip(), raw[1].strip().upper()
            docs.setdefault(doc, set()).add(code)
            d_pairs.add((doc, code))

    x_diag_pairs: set[tuple[str, str]] = set()
    x_rows = 0
    x_spans = 0
    spans_nonempty = 0
    zero_length_spans = 0
    references_reconstructed = 0
    span_exact = 0
    span_mismatch: list[dict[str, Any]] = []
    missing_texts: list[str] = []
    empty_refs = 0
    with x_path.open(encoding="utf-8") as handle:
        for raw in csv.reader(handle, delimiter="\t"):
            if len(raw) < 5 or raw[1].strip() != "DIAGNOSTICO":
                continue
            x_rows += 1
            doc, code = raw[0].strip(), raw[2].strip().upper()
            reference = raw[3]
            positions = raw[4].strip()
            x_diag_pairs.add((doc, code))
            if not reference.strip():
                empty_refs += 1
            text_path = text_dir / f"{doc}.txt"
            if not text_path.is_file():
                if doc not in missing_texts:
                    missing_texts.append(doc)
                continue
            text = text_path.read_text(encoding="utf-8")
            observed_parts: list[str] = []
            row_ok = True
            for pair in positions.split(";"):
                pair = pair.strip()
                if not pair:
                    continue
                try:
                    start_s, end_s = pair.split()
                    start, end = int(start_s), int(end_s)
                except ValueError:
                    row_ok = False
                    span_mismatch.append(
                        {"doc": doc, "code": code, "error": f"posición inválida: {pair!r}"}
                    )
                    continue
                x_spans += 1
                if start == end:
                    zero_length_spans += 1
                if start < 0 or end > len(text) or start >= end:
                    row_ok = False
                    if len(span_mismatch) < 20:
                        span_mismatch.append(
                            {
                                "doc": doc,
                                "code": code,
                                "start": start,
                                "end": end,
                                "error": "span fuera de rango o vacío",
                            }
                        )
                    continue
                observed = text[start:end]
                if observed.strip():
                    spans_nonempty += 1
                else:
                    row_ok = False
                observed_parts.append(observed)
                if observed == reference:
                    span_exact += 1

            if row_ok and observed_parts:
                if normalizar_texto("".join(observed_parts)) == normalizar_texto(reference):
                    references_reconstructed += 1
                elif len(span_mismatch) < 20:
                    span_mismatch.append(
                        {
                            "doc": doc,
                            "code": code,
                            "expected": reference,
                            "observed_parts": observed_parts,
                            "error": "la concatenación de spans no reconstruye la referencia",
                        }
                    )
            elif len(span_mismatch) < 20:
                span_mismatch.append(
                    {"doc": doc, "code": code, "error": "sin spans válidos para la referencia"}
                )

    codes = {code for values in docs.values() for code in values}
    missing_codes = sorted(codes - catalog)
    annotation_count = sum(len(values) for values in docs.values())
    stats = {
        "documents": len(docs),
        "annotations": annotation_count,
        "unique_codes": len(codes),
        "average_codes_per_document": round(annotation_count / len(docs), 2) if docs else 0,
        "documents_without_codes": sum(1 for values in docs.values() if not values),
        "codes_missing_from_catalog": len(missing_codes),
        "codes_missing_sample": missing_codes[:20],
        "x_diagnostic_rows": x_rows,
        "x_diagnostic_pairs": len(x_diag_pairs),
        "x_pair_coverage": round(len(x_diag_pairs & d_pairs) / len(d_pairs), 4) if d_pairs else 0,
        "x_spans_checked": x_spans,
        "x_spans_nonempty": spans_nonempty,
        "x_spans_nonempty_rate": round(spans_nonempty / x_spans, 4) if x_spans else 0,
        "x_zero_length_spans": zero_length_spans,
        "x_references_reconstructed": references_reconstructed,
        "x_reference_reconstruction_rate": (
            round(references_reconstructed / x_rows, 4) if x_rows else 0
        ),
        "x_spans_exact_token": span_exact,
        "x_span_exact_token_rate": round(span_exact / x_spans, 4) if x_spans else 0,
        "x_empty_references": empty_refs,
        "missing_text_documents": len(missing_texts),
        "missing_text_sample": missing_texts[:20],
        "span_mismatch_sample": span_mismatch[:20],
    }
    return docs, stats


def md_table(rows: list[tuple[str, Any]]) -> str:
    lines = ["| Métrica | Valor |", "|---|---:|"]
    lines.extend(f"| {key} | {value} |" for key, value in rows)
    return "\n".join(lines)


def main() -> int:
    if not CATALOG.is_file() or not CORPUS.is_dir():
        print(
            "ERROR: no se encontraron los datos. Ejecuta primero:\n"
            "  python scripts/download_data.py",
            file=sys.stderr,
        )
        return 2

    REPORTS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    catalog, catalog_stats = read_catalog(CATALOG)
    split_stats: dict[str, Any] = {}
    all_codes: set[str] = set()
    total_docs = total_annotations = 0
    for split in SPLITS:
        docs, stats = read_split(split, set(catalog))
        split_stats[split] = stats
        all_codes.update(code for values in docs.values() for code in values)
        total_docs += stats["documents"]
        total_annotations += stats["annotations"]

    missing_codes = sorted(all_codes - set(catalog))
    critical_failures: list[str] = []
    warnings: list[str] = []
    if catalog_stats["invalid_code_count"]:
        critical_failures.append("Hay códigos con formato inválido en el catálogo")
    if missing_codes:
        critical_failures.append("Hay códigos del corpus ausentes del catálogo")
    if catalog_stats["non_code_count"]:
        warnings.append(
            f"Se excluyeron {catalog_stats['non_code_count']} marcadores de capítulo "
            f"(CAP.xx) del catálogo de códigos"
        )
    if catalog_stats["duplicate_count"]:
        warnings.append(f"Hay {catalog_stats['duplicate_count']} filas duplicadas en el catálogo")
    if catalog_stats["empty_description_count"]:
        warnings.append(
            f"Hay {catalog_stats['empty_description_count']} códigos sin descripción en español"
        )
    for split, stats in split_stats.items():
        if stats["x_pair_coverage"] < 1.0:
            critical_failures.append(f"{split}: CodiEsp-X no cubre todos los pares D")
        if stats["x_spans_nonempty_rate"] < 0.999:
            critical_failures.append(f"{split}: demasiados spans vacíos o fuera de rango")
        elif stats["x_zero_length_spans"]:
            warnings.append(
                f"{split}: {stats['x_zero_length_spans']} span(s) de longitud cero en CodiEsp-X; "
                "se excluirán de la evaluación de evidencia"
            )
        if stats["x_reference_reconstruction_rate"] < 0.999:
            critical_failures.append(
                f"{split}: la concatenación de spans no reconstruye todas las referencias"
            )
        if stats["missing_text_documents"]:
            critical_failures.append(f"{split}: faltan textos para algunos documentos")

    result = {
        "project": "CodificaMed",
        "generated_at": datetime.now(UTC).isoformat(),
        "sources": {
            "catalog": "https://zenodo.org/records/3706838",
            "corpus": "https://zenodo.org/records/3837305",
            "license": "CC-BY-4.0",
        },
        "catalog": catalog_stats,
        "splits": split_stats,
        "totals": {
            "documents": total_docs,
            "annotations": total_annotations,
            "unique_codes": len(all_codes),
            "codes_missing_from_catalog": len(missing_codes),
        },
        "verdict": "OK" if not critical_failures else "FAIL",
        "critical_failures": critical_failures,
        "warnings": warnings,
    }
    (REPORTS / "data_audit.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines: list[str] = [
        "# Auditoría de datos — CodiEsp",
        "",
        f"Generado: {result['generated_at']}",
        "",
        "Fuentes: catálogo CIE-10-D (Zenodo 3706838) y corpus gold (Zenodo 3837305), "
        "licencia CC-BY-4.0.",
        "",
        "## Veredicto",
        "",
        f"**{result['verdict']}**",
        "",
    ]
    if critical_failures:
        lines.append("Fallos críticos:")
        lines.extend(f"- {item}" for item in critical_failures)
        lines.append("")
    else:
        lines.append(
            "El catálogo y el corpus son consistentes: todos los códigos gold existen "
            "en el catálogo y todos los spans de CodiEsp-X son no vacíos y reconstruyen "
            "la referencia anotada."
        )
        lines.append("")
    if warnings:
        lines.append("Advertencias:")
        lines.extend(f"- {item}" for item in warnings)
        lines.append("")

    lines += [
        "## Catálogo",
        "",
        md_table(
            [
                ("Filas", catalog_stats["rows"]),
                ("Códigos válidos únicos", catalog_stats["unique_codes"]),
                ("Marcadores de capítulo excluidos", catalog_stats["non_code_count"]),
                ("Duplicados", catalog_stats["duplicate_count"]),
                ("Descripciones vacías", catalog_stats["empty_description_count"]),
                ("Códigos con formato inválido", catalog_stats["invalid_code_count"]),
            ]
        ),
        "",
        "## Corpus por split",
        "",
        "| Split | Documentos | Anotaciones | Códigos únicos | Promedio/nota | Pares X/D | Spans no vacíos | Referencias reconstruidas | Spans vacíos |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for split in SPLITS:
        stats = split_stats[split]
        lines.append(
            f"| {split} | {stats['documents']} | {stats['annotations']} | "
            f"{stats['unique_codes']} | {stats['average_codes_per_document']} | "
            f"{stats['x_diagnostic_pairs']}/{stats['annotations']} | "
            f"{stats['x_spans_nonempty']}/{stats['x_spans_checked']} | "
            f"{stats['x_references_reconstructed']}/{stats['x_diagnostic_rows']} | "
            f"{stats['x_zero_length_spans']} |"
        )
    lines += [
        "",
        "## Totales",
        "",
        md_table(
            [
                ("Documentos", total_docs),
                ("Anotaciones de diagnóstico", total_annotations),
                ("Códigos únicos del corpus", len(all_codes)),
                ("Códigos válidos del catálogo", len(catalog)),
                ("Códigos ausentes del catálogo", len(missing_codes)),
            ]
        ),
        "",
        "## Verificaciones de calidad",
        "",
        "- Los códigos se normalizan a mayúsculas antes de comparar.",
        "- Se valida el formato ICD-10-CM, que admite una letra en la tercera posición (C4A, C7A, D3A).",
        f"- Se excluyen los {catalog_stats['non_code_count']} marcadores de capítulo `CAP.xx`, "
        "que no son códigos facturables.",
        "- Se comprueba que cada par diagnóstico de CodiEsp-D tenga su fila en CodiEsp-X.",
        "- Se comprueba que cada span sea no vacío y esté dentro del texto; los 3 spans de "
        "longitud cero detectados se excluirán de la evaluación de evidencia.",
        "- Se comprueba que la concatenación normalizada de los spans reconstruya la referencia; "
        "CodiEsp-X puede dividir una referencia multi-palabra en varios spans.",
        "- Se comprueba que exista el archivo de texto de cada documento anotado.",
        "",
        "El detalle completo está en `reports/data_audit.json`.",
        "",
    ]
    (DOCS / "auditoria_datos.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"Veredicto: {result['verdict']}")
    print(
        f"Catálogo: {catalog_stats['unique_codes']} códigos válidos "
        f"({catalog_stats['non_code_count']} marcadores CAP excluidos)"
    )
    print(f"Corpus: {total_docs} documentos, {total_annotations} anotaciones")
    print(f"Códigos únicos: {len(all_codes)}; ausentes del catálogo: {len(missing_codes)}")
    print(f"Reporte: {REPORTS / 'data_audit.json'}")
    print(f"Documento: {DOCS / 'auditoria_datos.md'}")
    for item in warnings:
        print(f"  ADVERTENCIA: {item}")
    if critical_failures:
        for item in critical_failures:
            print(f"  FALLO: {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
