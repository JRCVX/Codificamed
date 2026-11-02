"""Pruebas de la configuración tipada y de los modelos de dominio."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.catalog.models import (
    CatalogEntry,
    ClinicalState,
    CodeSuggestion,
    EvidenceSpan,
    Prediction,
    RetrievalHit,
)
from src.config import PROJECT_ROOT, Settings, get_settings, reload_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_settings_are_valid() -> None:
    settings = Settings()
    assert settings.llm_provider == "ollama"
    assert settings.top_k == 30
    assert settings.catalog_path.is_absolute()
    assert settings.catalog_path.name == "cie10_d_codes.tsv"
    assert settings.faiss_index_path.parent.name == "indexes"


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("TOP_K", "7")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-no-real")
    settings = reload_settings()
    assert settings.llm_provider == "openai"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.top_k == 7
    assert settings.openai_key() == "sk-test-no-real"
    assert settings.openai_key() is not None
    assert "sk-test-no-real" not in repr(settings)


def test_empty_api_key_is_none() -> None:
    settings = Settings(openai_api_key="   ", anthropic_api_key="")
    assert settings.openai_key() is None
    assert settings.anthropic_key() is None


def test_invalid_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_provider="proveedor-inexistente")


def test_invalid_top_k_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(top_k=0)


def test_relative_paths_resolve_to_project_root() -> None:
    settings = Settings(catalog_path="data/catalog/otro.tsv")
    assert settings.catalog_path == PROJECT_ROOT / "data" / "catalog" / "otro.tsv"


def test_catalog_entry_normalizes_code() -> None:
    entry = CatalogEntry(code=" i10 ", description_es=" Hipertensión esencial ")
    assert entry.code == "I10"
    assert entry.description_es == "Hipertensión esencial"
    with pytest.raises(ValidationError):
        CatalogEntry(code="   ", description_es="x")


def test_evidence_span_validates_order() -> None:
    span = EvidenceSpan(text="fiebre", start=10, end=16, state=ClinicalState.NEGATED)
    assert span.end == 16
    with pytest.raises(ValidationError):
        EvidenceSpan(text="fiebre", start=10, end=5)


def test_code_suggestion_confidence_bounds() -> None:
    suggestion = CodeSuggestion(
        code="e11.9",
        description="Diabetes mellitus tipo 2",
        confidence=0.9,
        state=ClinicalState.CONFIRMED,
    )
    assert suggestion.code == "E11.9"
    with pytest.raises(ValidationError):
        CodeSuggestion(code="E11.9", description="x", confidence=1.5)


def test_prediction_serializes() -> None:
    prediction = Prediction(
        note_id="FIC-001",
        text="Paciente con HTA.",
        codes=[
            CodeSuggestion(
                code="I10",
                description="Hipertensión esencial",
                confidence=0.8,
            )
        ],
        candidates=[
            RetrievalHit(
                code="I10",
                description_es="Hipertensión esencial",
                score=0.9,
                rank=1,
            )
        ],
        provider="mock",
        model="mock",
        latency_ms=12.5,
    )
    payload = prediction.model_dump(mode="json")
    assert payload["codes"][0]["code"] == "I10"
    assert payload["candidates"][0]["rank"] == 1
