"""Expansión determinista de abreviaturas clínicas.

Las abreviaturas se expanden en una copia del texto que se usa para recuperar
candidatos. El texto original y sus offsets se conservan para mostrar evidencia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEXICON = PROJECT_ROOT / "data" / "lexicons" / "abbreviations.yaml"


@dataclass(frozen=True)
class AbbreviationEntry:
    term: str
    expansion: str
    case_sensitive: bool = True
    pattern: re.Pattern[str] | None = None


@dataclass(frozen=True)
class ExpansionMatch:
    start: int
    end: int
    term: str
    expansion: str
    expanded_start: int
    expanded_end: int


@dataclass(frozen=True)
class ExpansionResult:
    original: str
    expanded: str
    matches: tuple[ExpansionMatch, ...]

    def _map_position(self, position: int, *, is_end: bool) -> int:
        delta = 0
        for match in self.matches:
            if position < match.expanded_start:
                return position - delta
            if position <= match.expanded_end:
                return match.end if is_end else match.start
            delta += len(match.expansion) - (match.end - match.start)
        return position - delta

    def original_span(self, start: int, end: int) -> tuple[int, int]:
        """Mapea un span del texto expandido al texto original.

        Si el span cae dentro de una expansión, se devuelve el span completo de
        la abreviatura original. Es la unidad correcta para resaltar evidencia.
        """
        if not 0 <= start <= end <= len(self.expanded):
            raise ValueError("span fuera de rango")
        return self._map_position(start, is_end=False), self._map_position(end, is_end=True)


class AbbreviationExpander:
    """Carga un lexicón YAML y expande sus términos."""

    def __init__(self, entries: list[AbbreviationEntry]) -> None:
        if not entries:
            raise ValueError("El lexicón de abreviaturas no puede estar vacío")
        self.entries = tuple(entries)

    @classmethod
    def from_yaml(cls, path: Path | str = DEFAULT_LEXICON) -> AbbreviationExpander:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"No existe el lexicón: {path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw_entries = payload.get("abbreviations")
        if not isinstance(raw_entries, list):
            raise ValueError("El YAML debe contener la clave 'abbreviations' como lista")

        entries: list[AbbreviationEntry] = []
        seen: set[tuple[str, bool]] = set()
        for position, raw in enumerate(raw_entries, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Entrada {position}: se esperaba un objeto")
            term = str(raw.get("term", "")).strip()
            expansion = str(raw.get("expansion", "")).strip()
            case_sensitive = bool(raw.get("case_sensitive", True))
            if not term or not expansion:
                raise ValueError(f"Entrada {position}: term y expansion son obligatorios")
            key = (term.casefold(), case_sensitive)
            if key in seen:
                raise ValueError(f"Entrada {position}: abreviatura duplicada {term!r}")
            seen.add(key)
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", flags=flags)
            entries.append(
                AbbreviationEntry(
                    term=term,
                    expansion=expansion,
                    case_sensitive=case_sensitive,
                    pattern=pattern,
                )
            )

        # Primero los términos más largos: "dolor abd" antes que "abd".
        entries.sort(key=lambda entry: (-len(entry.term), entry.term.casefold()))
        return cls(entries)

    def expand(self, text: str) -> ExpansionResult:
        """Devuelve el texto expandido y los spans de cada reemplazo."""
        if not isinstance(text, str):
            raise TypeError("text debe ser str")

        candidates: list[tuple[int, int, str, str]] = []
        for entry in self.entries:
            assert entry.pattern is not None
            for match in entry.pattern.finditer(text):
                candidates.append((match.start(), match.end(), entry.term, entry.expansion))

        candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
        selected: list[tuple[int, int, str, str]] = []
        last_end = -1
        for candidate in candidates:
            if candidate[0] < last_end:
                continue
            selected.append(candidate)
            last_end = candidate[1]

        pieces: list[str] = []
        matches: list[ExpansionMatch] = []
        cursor = 0
        expanded_cursor = 0
        for start, end, term, expansion in selected:
            prefix = text[cursor:start]
            pieces.append(prefix)
            expanded_cursor += len(prefix)
            expanded_start = expanded_cursor
            replacement = expansion
            source = text[start:end]
            prefix_before = text[:start].rstrip()
            sentence_start = not prefix_before or prefix_before[-1] in ".!?\n"
            if (
                source[:1].isupper()
                and (not source.isupper() or sentence_start)
                and expansion[:1].islower()
            ):
                replacement = expansion[:1].upper() + expansion[1:]
            pieces.append(replacement)
            expanded_cursor += len(replacement)
            matches.append(
                ExpansionMatch(
                    start=start,
                    end=end,
                    term=term,
                    expansion=expansion,
                    expanded_start=expanded_start,
                    expanded_end=expanded_cursor,
                )
            )
            cursor = end
        pieces.append(text[cursor:])

        return ExpansionResult(original=text, expanded="".join(pieces), matches=tuple(matches))

    def expand_text(self, text: str) -> str:
        return self.expand(text).expanded
