"""Valida y compila los 40 casos clínicos ficticios.

Entrada:
    data/fictional/cases_source.json

Salidas:
    data/fictional/cases.jsonl
    data/fictional/summary.json
    docs/casos_ficticios.md

El archivo fuente declara menciones por texto, no por offsets. Este script
resuelve los offsets, valida cada código contra el catálogo y comprueba que no
haya códigos contradictorios entre estados.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.catalog.loader import Catalog  # noqa: E402
from src.catalog.models import ClinicalState  # noqa: E402

DEFAULT_SOURCE = PROJECT_ROOT / "data" / "fictional" / "cases_source.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "fictional" / "cases.jsonl"
DEFAULT_SUMMARY = PROJECT_ROOT / "data" / "fictional" / "summary.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "docs" / "casos_ficticios.md"
DEFAULT_CATALOG = PROJECT_ROOT / "data" / "catalog" / "cie10_d_codes.tsv"
STATES = {state.value for state in ClinicalState}


class CaseValidationError(ValueError):
    """Error de validación de un caso ficticio."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--expected", type=int, default=40)
    return parser.parse_args()


def find_occurrence(haystack: str, needle: str, occurrence: int) -> tuple[int, int]:
    if not needle:
        raise CaseValidationError("La mención no puede estar vacía")
    start = 0
    found: list[int] = []
    while True:
        position = haystack.find(needle, start)
        if position < 0:
            break
        found.append(position)
        start = position + 1
    if occurrence < 0 or occurrence >= len(found):
        raise CaseValidationError(
            f"No se encontró la mención {needle!r} (ocurrencia {occurrence}); "
            f"ocurrencias disponibles: {len(found)}"
        )
    start = found[occurrence]
    return start, start + len(needle)


def validate_case(case: dict[str, Any], catalog: Catalog) -> dict[str, Any]:
    case_id = str(case.get("id", "")).strip()
    if not case_id:
        raise CaseValidationError("Caso sin id")
    split = str(case.get("split", "")).strip()
    if split not in {"dev", "test"}:
        raise CaseValidationError(f"{case_id}: split inválido {split!r}")
    specialty = str(case.get("specialty", "")).strip()
    if not specialty:
        raise CaseValidationError(f"{case_id}: falta specialty")
    text = case.get("text")
    if not isinstance(text, str) or not text.strip():
        raise CaseValidationError(f"{case_id}: text vacío")
    word_count = len(text.split())
    if word_count < 15:
        raise CaseValidationError(f"{case_id}: texto demasiado corto ({word_count} palabras)")
    phenomena = case.get("phenomena")
    if not isinstance(phenomena, list) or not phenomena:
        raise CaseValidationError(f"{case_id}: phenomena debe ser una lista no vacía")

    raw_mentions = case.get("mentions")
    if not isinstance(raw_mentions, list) or len(raw_mentions) < 2:
        raise CaseValidationError(f"{case_id}: se requieren al menos 2 menciones")

    entities: list[dict[str, Any]] = []
    for position, raw in enumerate(raw_mentions, start=1):
        if not isinstance(raw, dict):
            raise CaseValidationError(f"{case_id}: mención {position} no es un objeto")
        mention_text = str(raw.get("text", "")).strip()
        code = str(raw.get("code", "")).strip().upper()
        state = str(raw.get("state", "")).strip()
        if state not in STATES:
            raise CaseValidationError(f"{case_id}: estado inválido {state!r}")
        if not catalog.contains(code):
            raise CaseValidationError(f"{case_id}: código ausente del catálogo {code!r}")
        occurrence = int(raw.get("occurrence", 0))
        start, end = find_occurrence(text, mention_text, occurrence)
        entity = {
            "text": text[start:end],
            "start": start,
            "end": end,
            "code": code,
            "description": catalog.require(code).description_es,
            "state": state,
        }
        trigger = raw.get("trigger")
        if trigger:
            entity["trigger"] = str(trigger)
        entities.append(entity)

    # Deduplicar menciones idénticas (mismo span y código).
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str, str]] = set()
    for entity in entities:
        key = (entity["start"], entity["end"], entity["code"], entity["state"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entity)
    deduped.sort(key=lambda item: (item["start"], item["end"], item["code"]))
    entities = deduped

    by_state: dict[str, set[str]] = {state: set() for state in STATES}
    for entity in entities:
        by_state[entity["state"]].add(entity["code"])

    if not by_state[ClinicalState.CONFIRMED.value]:
        raise CaseValidationError(f"{case_id}: falta al menos un código confirmado")
    if not by_state[ClinicalState.NEGATED.value]:
        raise CaseValidationError(f"{case_id}: falta al menos un código negado")

    confirmed = by_state[ClinicalState.CONFIRMED.value]
    negated = by_state[ClinicalState.NEGATED.value]
    overlap = sorted(confirmed & negated)
    if overlap:
        raise CaseValidationError(f"{case_id}: código(s) confirmado(s) y negado(s): {overlap}")

    for state in (ClinicalState.SUSPECTED.value, ClinicalState.HISTORICAL.value, ClinicalState.FAMILY.value):
        conflict = sorted(confirmed & by_state[state])
        if conflict:
            raise CaseValidationError(
                f"{case_id}: código(s) confirmado(s) también en estado {state}: {conflict}"
            )

    return {
        "id": case_id,
        "split": split,
        "specialty": specialty,
        "phenomena": [str(item) for item in phenomena],
        "text": text,
        "word_count": word_count,
        "gold_codes": sorted(confirmed),
        "gold_confirmed_codes": sorted(confirmed),
        "gold_negated_codes": sorted(negated),
        "gold_suspected_codes": sorted(by_state[ClinicalState.SUSPECTED.value]),
        "gold_historical_codes": sorted(by_state[ClinicalState.HISTORICAL.value]),
        "gold_family_codes": sorted(by_state[ClinicalState.FAMILY.value]),
        "gold_entities": entities,
        "num_gold_codes": len(confirmed),
        "num_entities": len(entities),
        "source": "fictional",
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    specialties = Counter(record["specialty"] for record in records)
    phenomena = Counter(item for record in records for item in record["phenomena"])
    states = Counter(
        entity["state"] for record in records for entity in record["gold_entities"]
    )
    all_codes = {code for record in records for code in record["gold_codes"]}
    return {
        "total_cases": len(records),
        "splits": dict(Counter(record["split"] for record in records)),
        "specialties": dict(sorted(specialties.items())),
        "phenomena": dict(sorted(phenomena.items())),
        "entity_states": dict(sorted(states.items())),
        "unique_confirmed_codes": len(all_codes),
        "total_confirmed_codes": sum(record["num_gold_codes"] for record in records),
        "total_entities": sum(record["num_entities"] for record in records),
        "cases": [
            {
                "id": record["id"],
                "split": record["split"],
                "specialty": record["specialty"],
                "gold_codes": record["gold_codes"],
                "gold_negated_codes": record["gold_negated_codes"],
            }
            for record in records
        ],
    }


def build_markdown(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Casos clínicos ficticios",
        "",
        "Estos 40 casos son **inventados** para evaluación controlada. No corresponden a "
        "pacientes reales ni contienen datos identificables.",
        "",
        "## Resumen",
        "",
        f"- Casos: **{summary['total_cases']}**",
        f"- Reparto: **{summary['splits'].get('dev', 0)} dev / {summary['splits'].get('test', 0)} test**",
        f"- Códigos confirmados únicos: **{summary['unique_confirmed_codes']}**",
        f"- Entidades anotadas: **{summary['total_entities']}**",
        f"- Estados: {summary['entity_states']}",
        "",
        "## Distribución por especialidad",
        "",
        "| Especialidad | Casos |",
        "|---|---:|",
    ]
    for specialty, count in summary["specialties"].items():
        lines.append(f"| {specialty} | {count} |")
    lines.extend(
        [
            "",
            "## Casos",
            "",
            "| ID | Split | Especialidad | Confirmados | Negados | Otros estados |",
            "|---|---|---|---|---|---|",
        ]
    )
    for record in records:
        others = []
        if record["gold_suspected_codes"]:
            others.append(f"sospecha: {', '.join(record['gold_suspected_codes'])}")
        if record["gold_historical_codes"]:
            others.append(f"antecedente: {', '.join(record['gold_historical_codes'])}")
        if record["gold_family_codes"]:
            others.append(f"familiar: {', '.join(record['gold_family_codes'])}")
        lines.append(
            "| {id} | {split} | {specialty} | {confirmed} | {negated} | {others} |".format(
                id=record["id"],
                split=record["split"],
                specialty=record["specialty"],
                confirmed=", ".join(record["gold_confirmed_codes"]) or "—",
                negated=", ".join(record["gold_negated_codes"]) or "—",
                others="; ".join(others) or "—",
            )
        )
    lines.extend(
        [
            "",
            "## Criterios de validación",
            "",
            "- Cada mención se resolvió contra el texto original y tiene offsets verificados.",
            "- Cada código existe en el catálogo CIE-10-D de CodiEsp.",
            "- Cada caso tiene al menos un código confirmado y uno negado.",
            "- Un mismo código no puede estar confirmado y negado en el mismo caso.",
            "- Los casos con sospecha, antecedente o familiar se excluyen del gold confirmado.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if not args.catalog.is_file():
        raise SystemExit(
            f"No existe el catálogo: {args.catalog}\n"
            "Ejecuta primero: python scripts/prepare_catalog.py"
        )
    if not args.source.is_file():
        raise SystemExit(f"No existe el archivo fuente: {args.source}")

    payload = json.loads(args.source.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise SystemExit("El JSON debe contener la clave 'cases' como lista")

    catalog = Catalog.from_tsv(args.catalog)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw_case in raw_cases:
        try:
            records.append(validate_case(raw_case, catalog))
        except (CaseValidationError, ValueError, KeyError) as exc:
            errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(f"{len(errors)} caso(s) inválido(s)")

    if len(records) != args.expected:
        raise SystemExit(f"Se esperaban {args.expected} casos y se encontraron {len(records)}")
    ids = [record["id"] for record in records]
    if len(set(ids)) != len(ids):
        raise SystemExit("Hay IDs duplicados")
    splits = Counter(record["split"] for record in records)
    if splits != {"dev": 10, "test": 30}:
        raise SystemExit(f"Reparto inesperado: {dict(splits)}; se esperaba 10 dev / 30 test")

    write_jsonl(args.output, records)
    summary = build_summary(records)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(build_markdown(records, summary), encoding="utf-8")

    print(f"OK casos: {len(records)} -> {args.output}")
    print(f"OK resumen: {args.summary}")
    print(f"OK markdown: {args.markdown}")
    print(
        f"dev={splits['dev']} test={splits['test']} "
        f"entidades={summary['total_entities']} "
        f"códigos_confirmados={summary['total_confirmed_codes']} "
        f"únicos={summary['unique_confirmed_codes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
