"""Convierte CodiEsp-D + CodiEsp-X a JSONL reproducible.

Entradas:
    data/raw/final_dataset_v4_to_publish/{split}/{split}D.tsv
    data/raw/final_dataset_v4_to_publish/{split}/{split}X.tsv
    data/raw/final_dataset_v4_to_publish/{split}/text_files/*.txt
    data/catalog/cie10_d_codes.tsv

Salidas:
    data/processed/codiesp_{split}.jsonl
    data/processed/codiesp_all.jsonl
    reports/codiesp_preparation.json

Se conservan los códigos D aunque una referencia X tenga un span vacío; el
span inválido se excluye y se reporta. Así el gold de códigos no se altera por
un problema de anotación de evidencia.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.catalog.loader import Catalog  # noqa: E402

RAW_CORPUS = PROJECT_ROOT / "data" / "raw" / "final_dataset_v4_to_publish"
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalog" / "cie10_d_codes.tsv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
SUMMARY_PATH = PROJECT_ROOT / "reports" / "codiesp_preparation.json"
SPLITS = ("train", "dev", "test")


@dataclass
class EvidenceReference:
    code: str
    reference: str
    spans: list[dict[str, Any]] = field(default_factory=list)
    valid: bool = True
    warnings: list[str] = field(default_factory=list)


def normalize_for_comparison(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", without_accents.lower())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_CORPUS)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--summary", type=Path, default=SUMMARY_PATH)
    parser.add_argument("--splits", nargs="+", default=list(SPLITS), choices=SPLITS)
    return parser.parse_args()


def read_d(path: Path) -> dict[str, set[str]]:
    documents: dict[str, set[str]] = defaultdict(set)
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle, delimiter="\t"), start=1):
            if len(row) < 2:
                raise ValueError(f"{path}:{line_number}: se esperaban 2 columnas")
            document = row[0].strip()
            code = row[1].strip().upper()
            if not document or not code:
                raise ValueError(f"{path}:{line_number}: documento/código vacío")
            documents[document].add(code)
    return dict(documents)


def parse_positions(raw: str, text_length: int) -> tuple[list[tuple[int, int]], list[str]]:
    spans: list[tuple[int, int]] = []
    warnings: list[str] = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            start_text, end_text = chunk.split()
            start, end = int(start_text), int(end_text)
        except ValueError:
            warnings.append(f"posición inválida: {chunk!r}")
            continue
        if start == end:
            warnings.append(f"span de longitud cero: {start}-{end}")
            continue
        if start < 0 or end > text_length or start > end:
            warnings.append(f"span fuera de rango: {start}-{end}")
            continue
        spans.append((start, end))
    return spans, warnings


def read_x(path: Path, text_dir: Path) -> tuple[dict[str, list[EvidenceReference]], dict[str, int]]:
    references: dict[str, list[EvidenceReference]] = defaultdict(list)
    stats = {
        "x_rows": 0,
        "x_non_diagnostic_rows": 0,
        "x_zero_length_spans": 0,
        "x_invalid_position_chunks": 0,
        "x_references_without_valid_span": 0,
        "x_reference_reconstruction_failures": 0,
        "x_missing_texts": 0,
    }
    text_cache: dict[str, str] = {}

    with path.open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.reader(handle, delimiter="\t"):
            if len(raw) < 5:
                continue
            document, label, code, reference, positions = (
                raw[0].strip(),
                raw[1].strip().upper(),
                raw[2].strip().upper(),
                raw[3],
                raw[4].strip(),
            )
            if label != "DIAGNOSTICO":
                stats["x_non_diagnostic_rows"] += 1
                continue
            stats["x_rows"] += 1

            text_path = text_dir / f"{document}.txt"
            if document not in text_cache:
                if not text_path.is_file():
                    stats["x_missing_texts"] += 1
                    text_cache[document] = ""
                else:
                    text_cache[document] = text_path.read_text(encoding="utf-8")
            text = text_cache[document]

            spans, warnings = parse_positions(positions, len(text))
            zero_count = sum(1 for warning in warnings if "longitud cero" in warning)
            invalid_count = len(warnings) - zero_count
            stats["x_zero_length_spans"] += zero_count
            stats["x_invalid_position_chunks"] += invalid_count

            evidence = EvidenceReference(
                code=code,
                reference=reference,
                spans=[
                    {"start": start, "end": end, "text": text[start:end]}
                    for start, end in spans
                ],
                valid=bool(spans),
                warnings=warnings,
            )
            if not spans:
                stats["x_references_without_valid_span"] += 1
            elif reference.strip():
                reconstructed = "".join(text[start:end] for start, end in spans)
                if normalize_for_comparison(reconstructed) != normalize_for_comparison(reference):
                    stats["x_reference_reconstruction_failures"] += 1
                    evidence.warnings.append("la concatenación de spans no reconstruye la referencia")
            references[document].append(evidence)

    return dict(references), stats


def build_document(
    document: str,
    split: str,
    text: str,
    codes: set[str],
    evidence: list[EvidenceReference],
    catalog: Catalog,
) -> dict[str, Any]:
    missing = sorted(code for code in codes if not catalog.contains(code))
    if missing:
        raise ValueError(f"{document}: códigos ausentes del catálogo: {missing}")

    evidence_payload = [
        {
            "code": item.code,
            "reference": item.reference,
            "spans": item.spans,
            "valid": item.valid,
            "warnings": item.warnings,
        }
        for item in evidence
        if item.code in codes
    ]
    evidence_codes = {item["code"] for item in evidence_payload if item["valid"]}
    return {
        "id": document,
        "split": split,
        "text": text,
        "gold_codes": sorted(codes),
        "gold_evidence": evidence_payload,
        "evidence_codes": sorted(evidence_codes),
        "num_gold_codes": len(codes),
        "num_evidence_references": len(evidence_payload),
        "has_evidence": bool(evidence_codes),
    }


def prepare_split(
    split: str,
    *,
    raw: Path,
    catalog: Catalog,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    split_dir = raw / split
    d_path = split_dir / f"{split}D.tsv"
    x_path = split_dir / f"{split}X.tsv"
    text_dir = split_dir / "text_files"
    for path in (d_path, x_path, text_dir):
        if not path.exists():
            raise FileNotFoundError(f"No existe {path}; ejecuta scripts/download_data.py")

    documents = read_d(d_path)
    evidence_by_doc, x_stats = read_x(x_path, text_dir)

    records: list[dict[str, Any]] = []
    missing_text: list[str] = []
    codes_without_evidence: set[str] = set()
    for document, codes in sorted(documents.items()):
        text_path = text_dir / f"{document}.txt"
        if not text_path.is_file():
            missing_text.append(document)
            continue
        text = text_path.read_text(encoding="utf-8")
        record = build_document(
            document=document,
            split=split,
            text=text,
            codes=codes,
            evidence=evidence_by_doc.get(document, []),
            catalog=catalog,
        )
        codes_without_evidence.update(set(codes) - set(record["evidence_codes"]))
        records.append(record)

    stats = {
        "documents": len(records),
        "gold_codes": sum(record["num_gold_codes"] for record in records),
        "unique_codes": len({code for record in records for code in record["gold_codes"]}),
        "documents_with_evidence": sum(record["has_evidence"] for record in records),
        "codes_without_evidence": len(codes_without_evidence),
        "missing_texts": missing_text,
        **x_stats,
    }
    return records, stats


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    if not args.catalog.is_file():
        raise SystemExit(
            f"No existe el catálogo procesado: {args.catalog}\n"
            "Ejecuta primero: python scripts/prepare_catalog.py"
        )
    catalog = Catalog.from_tsv(args.catalog)

    all_records: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"catalog": str(args.catalog), "splits": {}}
    for split in args.splits:
        records, stats = prepare_split(split, raw=args.raw, catalog=catalog)
        write_jsonl(args.output / f"codiesp_{split}.jsonl", records)
        summary["splits"][split] = stats
        all_records.extend(records)
        print(
            f"OK {split}: {stats['documents']} documentos, "
            f"{stats['gold_codes']} códigos, {stats['codes_without_evidence']} sin evidencia"
        )

    if len(args.splits) > 1:
        write_jsonl(args.output / "codiesp_all.jsonl", all_records)

    summary["totals"] = {
        "documents": sum(stats["documents"] for stats in summary["splits"].values()),
        "gold_codes": sum(stats["gold_codes"] for stats in summary["splits"].values()),
        "unique_codes": len(
            {code for record in all_records for code in record["gold_codes"]}
        ),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Resumen: {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
