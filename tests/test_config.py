"""Pruebas de la configuración tipada y de los modelos de dominio."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from src.llm.providers import GeminiProvider

from src.catalog.models import (
    CatalogEntry,
    ClinicalState,
    CodeSuggestion,
    EvidenceSpan,
    Prediction,
    RetrievalHit,
)
from backend.services.coding_service import infer_provider_mode
from src.config import PROJECT_ROOT, Settings, get_settings, reload_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_settings_are_valid() -> None:
    settings = Settings(llm_provider="ollama")
    assert settings.llm_provider == "ollama"
    assert settings.top_k == 30
    assert settings.catalog_path.is_absolute()
    assert settings.catalog_path.name == "cie10_d_codes.tsv"
    assert settings.faiss_index_path.parent.name == "indexes"


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "llama3.1:8b")
    monkeypatch.setenv("TOP_K", "7")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama-cloud.internal:11434")
    settings = reload_settings()
    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "llama3.1:8b"
    assert settings.top_k == 7
    assert settings.ollama_base_url == "http://ollama-cloud.internal:11434"
    assert "ollama-cloud.internal" in settings.ollama_base_url


def test_empty_api_key_is_none() -> None:
    settings = Settings()
    assert settings.openai_key() is None
    assert settings.anthropic_key() is None


def test_invalid_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_provider="proveedor-inexistente")


def test_openrouter_provider_is_supported() -> None:
    settings = Settings(llm_provider="openrouter", openrouter_model="meta-llama/llama-3.1-8b-instruct:free")
    assert settings.llm_provider == "openrouter"
    assert settings.openrouter_model == "meta-llama/llama-3.1-8b-instruct:free"


def test_gemini_provider_is_supported() -> None:
    settings = Settings(llm_provider="gemini", gemini_model="gemini-3.5-flash", gemini_api_key="gemini-secret")
    assert settings.llm_provider == "gemini"
    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.gemini_key() == "gemini-secret"


def test_gemini_provider_falls_back_to_supported_models(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GeminiProvider("gemini-secret", "gemini-2.0-flash")

    calls: list[str] = []

    def fake_post(url: str, json: dict, timeout: float) -> httpx.Response:
        calls.append(url)
        if "gemini-2.0-flash" in url:
            return httpx.Response(404, request=httpx.Request("POST", url), json={"error": {"message": "not found"}})
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = provider.complete([{"role": "user", "content": "hola"}], temperature=0.1, max_tokens=32)

    assert response.content == "ok"
    assert any("gemini-2.0-flash" in call for call in calls)
    assert any("gemini-3.5-flash" in call for call in calls)


def test_gemini_provider_handles_empty_content_response(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GeminiProvider("gemini-secret", "gemini-3.5-flash")

    def fake_post(url: str, json: dict, timeout: float) -> httpx.Response:
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"candidates": [{"content": {}, "finishReason": "MAX_TOKENS"}], "usageMetadata": {"promptTokenCount": 5}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = provider.complete([{"role": "user", "content": "hola"}], max_tokens=1)

    assert response.content == ""
    assert response.provider == "gemini"


def test_infer_provider_mode_respects_selected_cloud_provider() -> None:
    assert infer_provider_mode("http://localhost:11434", selected_provider="gemini") == "cloud"
    assert infer_provider_mode("http://localhost:11434", selected_provider="ollama") == "local"


def test_gemini_provider_retries_when_model_is_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GeminiProvider("gemini-secret", "gemini-3.5-flash")
    calls: list[str] = []

    def fake_post(url: str, json: dict, timeout: float) -> httpx.Response:
        calls.append(url)
        if "gemini-3.5-flash" in url:
            return httpx.Response(503, request=httpx.Request("POST", url), json={"error": {"message": "busy"}})
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    response = provider.complete([{"role": "user", "content": "hola"}], max_tokens=8)

    assert response.content == "ok"
    assert any("gemini-3.5-flash" in call for call in calls)
    assert any("gemini-3.5-flash-lite" in call for call in calls)


def test_anthropic_provider_is_supported() -> None:
    settings = Settings(llm_provider="anthropic", anthropic_model="claude-3-5-sonnet-20241022", anthropic_api_key="anthropic-secret")
    assert settings.llm_provider == "anthropic"
    assert settings.anthropic_model == "claude-3-5-sonnet-20241022"
    assert settings.anthropic_key() == "anthropic-secret"


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
