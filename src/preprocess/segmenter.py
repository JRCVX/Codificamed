"""Segmentación de oraciones con offsets.

Se prefiere spaCy (``es_core_news_sm``) cuando está disponible. Si el modelo no
está instalado, se usa un segmentador regex determinista. En ambos casos los
spans apuntan al texto original.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

Backend = Literal["auto", "spacy", "regex"]

DEFAULT_SPACY_MODEL = "es_core_news_sm"

_ABBREVIATIONS_BEFORE_PERIOD = {
    "dr",
    "dra",
    "sr",
    "sra",
    "s",
    "p",
    "ej",
    "etc",
    "vs",
    "fig",
    "tab",
    "aprox",
    "mg",
    "ml",
    "kg",
    "cm",
    "mm",
    "h",
    "min",
    "seg",
}

_PRECEDING_WORD = re.compile(r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\.$")


@dataclass(frozen=True)
class Sentence:
    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("Span de oración inválido")
        if self.text != self.text.strip():
            raise ValueError("El texto de la oración no debe tener espacios externos")


@dataclass(frozen=True)
class _RawSpan:
    start: int
    end: int


def _trim_span(text: str, start: int, end: int) -> _RawSpan | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return _RawSpan(start, end) if end > start else None


def _is_decimal_point(text: str, index: int) -> bool:
    return (
        0 < index < len(text) - 1
        and text[index] == "."
        and text[index - 1].isdigit()
        and text[index + 1].isdigit()
    )


def _is_protected_abbreviation(text: str, segment_start: int, index: int) -> bool:
    if text[index] != ".":
        return False
    prefix = text[segment_start : index + 1]
    match = _PRECEDING_WORD.search(prefix)
    if match is None:
        return False
    return match.group(1).casefold() in _ABBREVIATIONS_BEFORE_PERIOD


def _regex_spans(text: str) -> list[_RawSpan]:
    spans: list[_RawSpan] = []
    start = 0
    index = 0
    length = len(text)

    while index < length:
        char = text[index]

        if char == "\n":
            trimmed = _trim_span(text, start, index)
            if trimmed:
                spans.append(trimmed)
            start = index + 1
            index += 1
            continue

        if char in ".!?":
            if char == "." and (
                _is_decimal_point(text, index)
                or _is_protected_abbreviation(text, start, index)
            ):
                index += 1
                continue

            next_index = index + 1
            while next_index < length and text[next_index] in " \t":
                next_index += 1
            if next_index >= length:
                trimmed = _trim_span(text, start, index + 1)
                if trimmed:
                    spans.append(trimmed)
                start = length
                break

            next_char = text[next_index]
            if next_char.isupper() or next_char in "¿¡\"'«»-":
                trimmed = _trim_span(text, start, index + 1)
                if trimmed:
                    spans.append(trimmed)
                start = next_index
                index = next_index
                continue

        index += 1

    trimmed = _trim_span(text, start, length)
    if trimmed:
        spans.append(trimmed)
    return spans


class RegexSentenceSegmenter:
    """Segmentador sin dependencias externas."""

    def segment(self, text: str) -> list[Sentence]:
        return [
            Sentence(text=text[span.start : span.end], start=span.start, end=span.end)
            for span in _regex_spans(text)
        ]


@lru_cache(maxsize=1)
def _load_spacy_model(model_name: str):
    import spacy

    return spacy.load(model_name)


class SpacySentenceSegmenter:
    """Segmentador basado en el modelo español de spaCy."""

    def __init__(self, model_name: str = DEFAULT_SPACY_MODEL) -> None:
        self.model_name = model_name
        self._nlp = _load_spacy_model(model_name)

    def segment(self, text: str) -> list[Sentence]:
        doc = self._nlp(text)
        spans: list[Sentence] = []
        for sent in doc.sents:
            trimmed = _trim_span(text, sent.start_char, sent.end_char)
            if trimmed:
                spans.append(
                    Sentence(
                        text=text[trimmed.start : trimmed.end],
                        start=trimmed.start,
                        end=trimmed.end,
                    )
                )
        return spans


class SentenceSegmenter:
    """Fachada que elige spaCy o regex y degrada con elegancia."""

    def __init__(self, backend: Backend = "auto", model_name: str = DEFAULT_SPACY_MODEL) -> None:
        if backend not in ("auto", "spacy", "regex"):
            raise ValueError(f"Backend desconocido: {backend}")
        self.backend = backend
        self.model_name = model_name
        self._delegate = self._build_delegate()

    def _build_delegate(self) -> RegexSentenceSegmenter | SpacySentenceSegmenter:
        if self.backend == "regex":
            return RegexSentenceSegmenter()
        try:
            return SpacySentenceSegmenter(self.model_name)
        except (ImportError, OSError):
            if self.backend == "spacy":
                raise
            return RegexSentenceSegmenter()

    def segment(self, text: str) -> list[Sentence]:
        return self._delegate.segment(text)


def segment_sentences(text: str, backend: Backend = "auto") -> list[Sentence]:
    """Atajo para segmentar una nota clínica."""
    return SentenceSegmenter(backend=backend).segment(text)
