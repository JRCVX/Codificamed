"""Fachada de preproceso para una nota clínica."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.preprocess.abbreviations import (
    AbbreviationExpander,
    ExpansionMatch,
    ExpansionResult,
)
from src.preprocess.normalize import NormalizedText, normalize_text
from src.preprocess.segmenter import Sentence, SentenceSegmenter
from src.preprocess.typos import TypoCorrection, TypoCorrector


@dataclass(frozen=True)
class PreprocessedNote:
    original: str
    normalized: NormalizedText
    expansion: ExpansionResult
    sentences: tuple[Sentence, ...]
    typos: tuple[TypoCorrection, ...]
    retrieval_text: str


class ClinicalPreprocessor:
    """Orquesta normalización, abreviaturas, oraciones y typos."""

    def __init__(
        self,
        *,
        expander: AbbreviationExpander | None = None,
        segmenter: SentenceSegmenter | None = None,
        typo_corrector: TypoCorrector | None = None,
        correct_typos: bool = True,
    ) -> None:
        self.expander = expander or AbbreviationExpander.from_yaml()
        self.segmenter = segmenter or SentenceSegmenter(backend="auto")
        self.typo_corrector = (
            (typo_corrector or TypoCorrector.from_file()) if correct_typos else None
        )

    @classmethod
    def from_paths(
        cls,
        *,
        abbreviations_path: Path | str | None = None,
        vocabulary_path: Path | str | None = None,
        segmenter_backend: str = "auto",
        correct_typos: bool = True,
    ) -> ClinicalPreprocessor:
        expander = (
            AbbreviationExpander.from_yaml(abbreviations_path)
            if abbreviations_path
            else AbbreviationExpander.from_yaml()
        )
        corrector = None
        if correct_typos:
            corrector = (
                TypoCorrector.from_file(vocabulary_path)
                if vocabulary_path
                else TypoCorrector.from_file()
            )
        return cls(
            expander=expander,
            segmenter=SentenceSegmenter(backend=segmenter_backend),  # type: ignore[arg-type]
            typo_corrector=corrector,
            correct_typos=correct_typos,
        )

    def preprocess(self, text: str) -> PreprocessedNote:
        normalized = normalize_text(text)
        expansion = self.expander.expand(text)
        sentences = tuple(self.segmenter.segment(text))
        typos = tuple(self.typo_corrector.suggest(text)) if self.typo_corrector else ()
        corrected_original = (
            self.typo_corrector.apply(text, list(typos)) if self.typo_corrector else text
        )
        retrieval_text = self.expander.expand_text(corrected_original)
        return PreprocessedNote(
            original=text,
            normalized=normalized,
            expansion=expansion,
            sentences=sentences,
            typos=typos,
            retrieval_text=retrieval_text,
        )

    def expand_matches(self, text: str) -> tuple[ExpansionMatch, ...]:
        return self.expander.expand(text).matches
