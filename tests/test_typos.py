"""Pruebas del corrector de typos."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.preprocess.typos import TypoCorrector

VOCAB = [
    "hipertensión",
    "diabetes",
    "neumonía",
    "gastritis",
    "apendicitis",
    "disnea",
    "dolor",
    "fiebre",
    "paciente",
    "control",
    "tratamiento",
]


@pytest.fixture()
def corrector() -> TypoCorrector:
    return TypoCorrector(VOCAB)


def test_corrects_common_typos(corrector: TypoCorrector) -> None:
    assert corrector.correct_token("hipertensoin") is not None
    assert corrector.correct_token("hipertensoin")[0] == "hipertensión"  # type: ignore[index]
    assert corrector.correct_token("diabete")[0] == "diabetes"  # type: ignore[index]
    assert corrector.correct_token("neumonia")[0] == "neumonía"  # type: ignore[index]
    assert corrector.correct_token("gastriti")[0] == "gastritis"  # type: ignore[index]


def test_does_not_correct_known_words(corrector: TypoCorrector) -> None:
    assert corrector.correct_token("paciente") is None
    assert corrector.correct_token("fiebre") is None
    assert corrector.correct_token("control") is None


def test_does_not_correct_negations_or_abbreviations(corrector: TypoCorrector) -> None:
    assert corrector.correct_token("niega") is None
    assert corrector.correct_token("HTA") is None
    assert corrector.correct_token("DM2") is None


def test_does_not_correct_short_tokens(corrector: TypoCorrector) -> None:
    assert corrector.correct_token("tos") is None
    assert corrector.correct_token("dolor") is None


def test_suggest_returns_offsets(corrector: TypoCorrector) -> None:
    text = "Paciente con hipertensoin y diabete."
    corrections = corrector.suggest(text)
    assert len(corrections) == 2
    assert text[corrections[0].start : corrections[0].end] == "hipertensoin"
    assert corrections[0].suggestion == "hipertensión"
    assert corrections[1].suggestion == "diabetes"


def test_apply_replaces_right_to_left(corrector: TypoCorrector) -> None:
    text = "Paciente con hipertensoin y diabete."
    corrected = corrector.apply(text)
    assert corrected == "Paciente con hipertensión y diabetes."


def test_from_file(tmp_path: Path) -> None:
    path = tmp_path / "vocab.txt"
    path.write_text("\n".join(VOCAB) + "\n", encoding="utf-8")
    corrector = TypoCorrector.from_file(path)
    assert corrector.correct_token("neumonia") is not None


def test_empty_vocabulary_is_rejected() -> None:
    with pytest.raises(ValueError, match="vacío"):
        TypoCorrector([])
