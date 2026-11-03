from src.catalog.models import ClinicalState
from src.negation import SpanishNegationDetector


def test_negation_and_uncertainty_states():
    detector = SpanishNegationDetector()
    results = detector.detect("Niega fiebre. Posible neumonía. Antecedente de HTA.")
    assert [item.state for item in results] == [
        ClinicalState.NEGATED,
        ClinicalState.SUSPECTED,
        ClinicalState.HISTORICAL,
    ]


def test_pseudo_negation_does_not_mark_negative():
    result = SpanishNegationDetector().detect("No hay duda de infección.")[0]
    assert result.state == ClinicalState.CONFIRMED


def test_family_state():
    result = SpanishNegationDetector().detect("Madre con diabetes.")[0]
    assert result.state == ClinicalState.FAMILY


def test_adversative_clause_ends_negation_scope():
    detector = SpanishNegationDetector()
    results = detector.detect("Niega fiebre, pero presenta tos.")
    assert [item.state for item in results] == [ClinicalState.NEGATED, ClinicalState.CONFIRMED]
    assert results[0].sentence.text == "Niega fiebre"
    assert results[1].sentence.text == "presenta tos."
