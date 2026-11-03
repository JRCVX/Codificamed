"""Pruebas del expansor de abreviaturas."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.preprocess.abbreviations import AbbreviationExpander

LEXICON = """
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
  - term: "abd"
    expansion: "abdominal"
    case_sensitive: false
  - term: "PA"
    expansion: "presión arterial"
    case_sensitive: true
"""


@pytest.fixture()
def expander(tmp_path: Path) -> AbbreviationExpander:
    path = tmp_path / "abbreviations.yaml"
    path.write_text(LEXICON, encoding="utf-8")
    return AbbreviationExpander.from_yaml(path)


def test_expands_known_abbreviations(expander: AbbreviationExpander) -> None:
    result = expander.expand("Paciente con HTA y DM2. Dolor abd.")
    assert "hipertensión arterial" in result.expanded
    assert "diabetes mellitus tipo 2" in result.expanded
    assert "dolor abdominal" in result.expanded.lower()
    assert len(result.matches) == 3


def test_longest_phrase_wins(expander: AbbreviationExpander) -> None:
    result = expander.expand("Dolor abd de 24 horas")
    assert result.expanded == "Dolor abdominal de 24 horas"
    assert result.matches[0].term == "dolor abd"


def test_case_sensitive_acronym_does_not_expand_common_word(expander: AbbreviationExpander) -> None:
    result = expander.expand("El paciente PA de 120/80; pa es una sílaba.")
    assert result.expanded.startswith("El paciente presión arterial de 120/80")
    assert result.expanded.endswith("pa es una sílaba.")


def test_word_boundaries(expander: AbbreviationExpander) -> None:
    result = expander.expand("HTAelevada no es HTA")
    assert result.expanded == "HTAelevada no es hipertensión arterial"


def test_original_span_maps_expansion(expander: AbbreviationExpander) -> None:
    result = expander.expand("HTA y DM2")
    first = result.matches[0]
    span = result.original_span(first.expanded_start, first.expanded_end)
    assert span == (0, 3)
    assert result.original[span[0] : span[1]] == "HTA"


def test_original_span_outside_expansion(expander: AbbreviationExpander) -> None:
    result = expander.expand("HTA y fiebre")
    start = result.expanded.index("fiebre")
    span = result.original_span(start, start + len("fiebre"))
    assert result.original[span[0] : span[1]] == "fiebre"
    assert span == (6, 12)


def test_empty_lexicon_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("abbreviations: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="vacío"):
        AbbreviationExpander.from_yaml(path)


def test_duplicate_term_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.yaml"
    path.write_text(
        "abbreviations:\n"
        "  - {term: HTA, expansion: hipertensión arterial}\n"
        "  - {term: HTA, expansion: otra cosa}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicada"):
        AbbreviationExpander.from_yaml(path)
