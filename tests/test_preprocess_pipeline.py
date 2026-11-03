"""Pruebas de la fachada de preproceso."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.preprocess.abbreviations import AbbreviationExpander
from src.preprocess.pipeline import ClinicalPreprocessor
from src.preprocess.segmenter import SentenceSegmenter
from src.preprocess.typos import TypoCorrector

YAML = """
abbreviations:
  - term: "HTA"
    expansion: "hipertensión arterial"
    case_sensitive: true
  - term: "DM2"
    expansion: "diabetes mellitus tipo 2"
    case_sensitive: true
  - term: "dolor abd"
    expansion: "dolor abdominal"
    case_sensitive: false
"""


@pytest.fixture()
def preprocessor(tmp_path: Path) -> ClinicalPreprocessor:
    abbreviations = tmp_path / "abbreviations.yaml"
    abbreviations.write_text(YAML, encoding="utf-8")
    vocabulary = tmp_path / "vocab.txt"
    vocabulary.write_text(
        "hipertensión\ndiabetes\nfiebre\npaciente\ncontrol\nniega\n",
        encoding="utf-8",
    )
    return ClinicalPreprocessor(
        expander=AbbreviationExpander.from_yaml(abbreviations),
        segmenter=SentenceSegmenter(backend="regex"),
        typo_corrector=TypoCorrector.from_file(vocabulary),
    )


def test_preprocess_returns_all_views(preprocessor: ClinicalPreprocessor) -> None:
    text = "Paciente con hipertensoin y HTA; niega fiebre. Control."
    result = preprocessor.preprocess(text)
    assert result.original == text
    assert result.normalized.text == text
    assert "hipertensión arterial" in result.expansion.expanded
    assert len(result.sentences) == 2
    assert any(correction.suggestion == "hipertensión" for correction in result.typos)
    assert "hipertensión arterial" in result.retrieval_text.casefold()
    assert "hipertensoin" not in result.retrieval_text


def test_preprocess_handles_empty_text(preprocessor: ClinicalPreprocessor) -> None:
    result = preprocessor.preprocess("")
    assert result.original == ""
    assert result.normalized.text == ""
    assert result.sentences == ()
    assert result.typos == ()
    assert result.retrieval_text == ""


def test_expand_matches(preprocessor: ClinicalPreprocessor) -> None:
    matches = preprocessor.expand_matches("HTA y DM2")
    assert [match.term for match in matches] == ["HTA", "DM2"]


def test_preprocessor_can_disable_typo_correction_for_retrieval_benchmarks() -> None:
    preprocessor = ClinicalPreprocessor(
        expander=AbbreviationExpander.from_yaml(),
        segmenter=SentenceSegmenter(backend="regex"),
        correct_typos=False,
    )
    result = preprocessor.preprocess("HTA y fiebre.")
    assert result.typos == ()
    assert "hipertensión arterial" in result.retrieval_text.casefold()
