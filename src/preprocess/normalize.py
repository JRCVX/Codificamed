"""Normalización de texto clínico conservando la trazabilidad de offsets.

La normalización no reemplaza el texto original: construye una versión con
espacios colapsados y un mapa ``carácter normalizado -> índice original``. Así
la evidencia que se muestre al usuario siempre apunta al texto original.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_HORIZONTAL_SPACE = re.compile(r"[ \t\f\v\u00a0\u2007\u202f]")
_NON_WORD = re.compile(r"[^a-z0-9áéíóúüñ]+")


@dataclass(frozen=True)
class NormalizedText:
    """Texto normalizado y mapa de offsets hacia el original."""

    original: str
    text: str
    char_map: tuple[int, ...]

    def original_span(self, start: int, end: int) -> tuple[int, int]:
        """Convierte un span del texto normalizado a índices del original.

        ``end`` es exclusivo, como en Python. Para spans vacíos se devuelve una
        posición puntual.
        """
        if not 0 <= start <= len(self.text):
            raise ValueError(f"start fuera de rango: {start}")
        if not 0 <= end <= len(self.text):
            raise ValueError(f"end fuera de rango: {end}")
        if end < start:
            raise ValueError("end no puede ser menor que start")
        if start == end:
            position = self.char_map[start]
            return position, position
        return self.char_map[start], self.char_map[end - 1] + 1


def normalize_text(text: str) -> NormalizedText:
    """Colapsa espacios y saltos de línea preservando un mapa al original.

    No aplica NFC/NFKD ni elimina acentos porque eso cambiaría la longitud y
    rompería los offsets de CodiEsp-X. Para comparaciones sin acentos existe
    :func:`normalize_for_matching`.
    """
    if not isinstance(text, str):
        raise TypeError("text debe ser str")

    chars: list[str] = []
    mapping: list[int] = []
    pending_space = False
    pending_space_index = 0
    index = 0

    while index < len(text):
        char = text[index]

        if char == "\r":
            # \r\n cuenta como un único separador; \r aislado también.
            pending_space = True
            pending_space_index = index
            if index + 1 < len(text) and text[index + 1] == "\n":
                index += 2
                continue
            index += 1
            continue

        if _HORIZONTAL_SPACE.match(char) or char == "\n":
            if not pending_space:
                pending_space_index = index
            pending_space = True
            index += 1
            continue

        if pending_space and chars and chars[-1] != " ":
            chars.append(" ")
            mapping.append(pending_space_index)
        pending_space = False

        chars.append(char)
        mapping.append(index)
        index += 1

    # Sin espacio final.
    if chars and chars[-1] == " ":
        chars.pop()
        mapping.pop()

    mapping.append(len(text))
    return NormalizedText(original=text, text="".join(chars), char_map=tuple(mapping))


def strip_accents(text: str) -> str:
    """Elimina diacríticos sin cambiar el resto del texto."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_for_matching(text: str) -> str:
    """Versión minúscula, sin acentos y sin puntuación para búsquedas."""
    lowered = strip_accents(text).lower()
    return " ".join(_NON_WORD.sub(" ", lowered).split())


def tokens_for_matching(text: str) -> list[str]:
    """Tokens normalizados; útil para BM25 y para el corrector de typos."""
    normalized = normalize_for_matching(text)
    return normalized.split() if normalized else []
