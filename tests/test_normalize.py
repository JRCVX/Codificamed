"""Pruebas de normalización y trazabilidad de offsets."""

from __future__ import annotations

import pytest

from src.preprocess.normalize import (
    NormalizedText,
    normalize_for_matching,
    normalize_text,
    strip_accents,
    tokens_for_matching,
)


def test_collapses_whitespace_and_preserves_original_span() -> None:
    original = "  HTA   y\nDM2. Paciente con fiebre.  "
    normalized = normalize_text(original)
    assert normalized.text == "HTA y DM2. Paciente con fiebre."
    start, end = normalized.original_span(
        normalized.text.index("DM2"), normalized.text.index("DM2") + 3
    )
    assert original[start:end] == "DM2"
    assert normalized.original_span(0, 3) == (2, 5)


def test_accents_are_preserved_for_evidence() -> None:
    normalized = normalize_text("Hipertensión arterial y neumonía")
    assert normalized.text == "Hipertensión arterial y neumonía"
    assert normalized.original_span(0, 12) == (0, 12)


def test_empty_text() -> None:
    normalized = normalize_text("   \n\t ")
    assert normalized.text == ""
    assert normalized.char_map == (len("   \n\t "),)
    assert normalized.original_span(0, 0) == (6, 6)


def test_invalid_span_raises() -> None:
    normalized = normalize_text("abc")
    with pytest.raises(ValueError):
        normalized.original_span(3, 1)
    with pytest.raises(ValueError):
        normalized.original_span(0, 4)


def test_normalize_for_matching_removes_accents_and_punctuation() -> None:
    assert normalize_for_matching("Hipertensión ARTERIAL, disnea.") == (
        "hipertension arterial disnea"
    )
    assert strip_accents("neumonía") == "neumonia"
    assert tokens_for_matching("Dolor abdominal (agudo)") == ["dolor", "abdominal", "agudo"]


def test_no_leading_or_trailing_space() -> None:
    normalized = normalize_text("\n  fiebre  \n")
    assert normalized.text == "fiebre"
    assert normalized.original_span(0, 6) == (3, 9)


def test_normalized_text_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        normalize_text(123)  # type: ignore[arg-type]


def test_normalized_text_is_immutable_dataclass() -> None:
    normalized = normalize_text("HTA")
    assert isinstance(normalized, NormalizedText)
    with pytest.raises(AttributeError):
        normalized.text = "otro"  # type: ignore[misc]
