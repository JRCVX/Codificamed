from __future__ import annotations

import os

from backend.main import FRONTEND_ROOT, get_port
from backend.services.coding_service import build_runtime_settings


def test_backend_uses_dedicated_frontend_dir() -> None:
    assert FRONTEND_ROOT.exists()
    assert (FRONTEND_ROOT / "index.html").exists()


def test_backend_port_is_configurable(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "8011")
    assert get_port() == 8011

    monkeypatch.setenv("PORT", "")
    assert get_port() == 8010


def test_runtime_settings_allow_local_and_cloud_provider_override() -> None:
    local_settings = build_runtime_settings(provider_mode="local")
    assert local_settings.llm_provider == "ollama"
    assert local_settings.ollama_base_url == "http://localhost:11434"
    assert local_settings.llm_model == "mistral"

    cloud_settings = build_runtime_settings(provider_mode="cloud", provider_name="openrouter", api_key="secret-key", llm_model="openai/gpt-4o-mini")
    assert cloud_settings.llm_provider == "openrouter"
    assert cloud_settings.llm_model == "openai/gpt-4o-mini"
    assert cloud_settings.openrouter_api_key is not None
    assert cloud_settings.openrouter_api_key.get_secret_value() == "secret-key"
    assert cloud_settings.ollama_base_url == "http://localhost:11434"

    remote_ollama_settings = build_runtime_settings(provider_mode="cloud", provider_name="ollama", ollama_base_url="http://ollama-server:11434")
    assert remote_ollama_settings.llm_provider == "ollama"
    assert remote_ollama_settings.ollama_base_url == "http://ollama-server:11434"
    assert remote_ollama_settings.llm_model == "glm-5.3-flash:cloud"
