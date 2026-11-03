"""Pruebas de segmentación de oraciones."""

from __future__ import annotations

import pytest

from src.preprocess.segmenter import RegexSentenceSegmenter, SentenceSegmenter, segment_sentences


def test_regex_segmenter_splits_sentences() -> None:
    text = "El paciente tiene HTA. Niega fiebre.\nSe indica control."
    sentences = RegexSentenceSegmenter().segment(text)
    assert [sentence.text for sentence in sentences] == [
        "El paciente tiene HTA.",
        "Niega fiebre.",
        "Se indica control.",
    ]
    for sentence in sentences:
        assert text[sentence.start : sentence.end] == sentence.text


def test_decimal_point_does_not_split() -> None:
    text = "Bilirrubina total 14.5 mg/dL. Se indica fototerapia."
    sentences = RegexSentenceSegmenter().segment(text)
    assert len(sentences) == 2
    assert sentences[0].text == "Bilirrubina total 14.5 mg/dL."


def test_protected_abbreviation_does_not_split() -> None:
    text = "Dr. Pérez evalúa al paciente. Niega dolor."
    sentences = RegexSentenceSegmenter().segment(text)
    assert len(sentences) == 2
    assert sentences[0].text.startswith("Dr. Pérez")


def test_exclamation_and_question_marks() -> None:
    text = "¿Tiene fiebre? No. ¡Entonces no hay infección!"
    sentences = RegexSentenceSegmenter().segment(text)
    assert [sentence.text for sentence in sentences] == [
        "¿Tiene fiebre?",
        "No.",
        "¡Entonces no hay infección!",
    ]


def test_empty_text_returns_empty_list() -> None:
    assert RegexSentenceSegmenter().segment("   \n  ") == []


def test_sentence_offsets_are_consistent() -> None:
    text = "Primera oración. Segunda oración."
    sentences = segment_sentences(text, backend="regex")
    assert text[sentences[0].start : sentences[0].end] == sentences[0].text
    assert text[sentences[1].start : sentences[1].end] == sentences[1].text
    assert sentences[1].start > sentences[0].end


def test_auto_backend_falls_back_or_loads_spacy() -> None:
    text = "El paciente tiene HTA. Niega fiebre."
    sentences = SentenceSegmenter(backend="auto").segment(text)
    assert len(sentences) == 2


def test_invalid_backend_is_rejected() -> None:
    with pytest.raises(ValueError):
        SentenceSegmenter(backend="otro")  # type: ignore[arg-type]
