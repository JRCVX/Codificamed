"""Detección basada en reglas de negación y estado en español clínico."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.catalog.models import ClinicalState
from src.preprocess.segmenter import Sentence, SentenceSegmenter


@dataclass(frozen=True)
class SentenceStatus:
    sentence: Sentence
    state: ClinicalState
    trigger: str | None = None


_FAMILY = re.compile(r"\b(?:madre|padre|hermano|hermana|hijo|hija|familiar(?:es)?)\s+(?:con|padece|tiene)\b|\bantecedentes? familiares de\b", re.I)
_HISTORICAL = re.compile(r"\b(?:antecedente(?:s)? de|historia de|portador(?:a)? de|diagnosticad[oa] previamente con)\b", re.I)
_UNCERTAIN = re.compile(r"\b(?:no se descarta|no se puede descartar|a descartar)\b", re.I)
_SUSPECTED = re.compile(r"\b(?:posible|probable|sospecha(?: de)?|compatible con)\b", re.I)
_NEGATION = re.compile(r"\b(?:niega|sin|ausencia de|se descarta|descartad[oa]|negativ[oa] para|no presenta|no refiere|no evidencia de|no se observa|no)\b", re.I)
_PSEUDO = re.compile(r"\b(?:no solo|no únicamente|no hay duda)\b", re.I)
_CLAUSE_BOUNDARY = re.compile(r"\s*(?:;|,?\s+pero\s+|\s+sin embargo\s+|\s+no obstante\s+)\s*", re.I)


class SpanishNegationDetector:
    """Clasifica menciones a nivel de oración con reglas auditables."""

    def __init__(self, segmenter: SentenceSegmenter | None = None) -> None:
        self.segmenter = segmenter or SentenceSegmenter(backend="auto")

    def classify_sentence(self, sentence: Sentence) -> SentenceStatus:
        text = sentence.text
        for pattern, state in (
            (_FAMILY, ClinicalState.FAMILY),
            (_HISTORICAL, ClinicalState.HISTORICAL),
            (_UNCERTAIN, ClinicalState.UNCERTAIN),
            (_SUSPECTED, ClinicalState.SUSPECTED),
        ):
            match = pattern.search(text)
            if match:
                return SentenceStatus(sentence, state, match.group(0))
        if not _PSEUDO.search(text):
            match = _NEGATION.search(text)
            if match:
                return SentenceStatus(sentence, ClinicalState.NEGATED, match.group(0))
        return SentenceStatus(sentence, ClinicalState.CONFIRMED)

    def detect(self, text: str) -> list[SentenceStatus]:
        statuses: list[SentenceStatus] = []
        for sentence in self.segmenter.segment(text):
            cursor = sentence.start
            for boundary in _CLAUSE_BOUNDARY.finditer(sentence.text):
                clause_end = sentence.start + boundary.start()
                if clause_end > cursor:
                    clause = Sentence(text[cursor:clause_end].strip(), cursor, clause_end)
                    statuses.append(self.classify_sentence(clause))
                cursor = sentence.start + boundary.end()
            if cursor < sentence.end:
                clause = Sentence(text[cursor:sentence.end].strip(), cursor, sentence.end)
                statuses.append(self.classify_sentence(clause))
        return statuses

    def state_for_span(self, span: tuple[int, int], statuses: list[SentenceStatus]) -> ClinicalState:
        start, end = span
        for status in statuses:
            sent = status.sentence
            if start < sent.end and end > sent.start:
                return status.state
        return ClinicalState.UNCERTAIN
