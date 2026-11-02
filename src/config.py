"""Configuración central de CodificaMed.

Toda la aplicación lee la configuración desde variables de entorno o desde un
archivo ``.env``. No hay claves ni rutas absolutas hardcodeadas en el código.

Uso:
    from src.config import get_settings
    settings = get_settings()
    print(settings.llm_provider, settings.llm_model)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ProviderName = Literal["ollama", "openai", "anthropic", "mock"]
DeviceName = Literal["cpu", "cuda", "auto"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Configuración tipada y validada de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Proveedor LLM
    llm_provider: ProviderName = "ollama"
    llm_model: str = "qwen3:8b"
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1200, ge=64, le=8192)

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # API compatible con OpenAI (OpenAI, OpenRouter, Groq, vLLM...)
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Anthropic
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"

    # Embeddings y recuperación
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_device: DeviceName = "cpu"
    top_k: int = Field(default=30, ge=1, le=200)
    bm25_top_k: int = Field(default=50, ge=1, le=500)
    dense_top_k: int = Field(default=50, ge=1, le=500)

    # Rutas (relativas a la raíz del proyecto)
    catalog_path: Path = Path("data/catalog/cie10_d_codes.tsv")
    faiss_index_path: Path = Path("data/indexes/cie10_e5_small.faiss")
    cache_dir: Path = Path(".cache/llm")

    # Operación
    log_level: LogLevel = "INFO"

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _normalize_provider(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("llm_model", "openai_model", "anthropic_model")
    @classmethod
    def _strip_model(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El nombre del modelo no puede estar vacío")
        return value

    @field_validator("openai_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def _empty_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("catalog_path", "faiss_index_path", "cache_dir", mode="after")
    @classmethod
    def _resolve_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    def ensure_directories(self) -> None:
        """Crea los directorios de trabajo que deben existir en tiempo de ejecución."""
        for path in (
            self.cache_dir,
            self.faiss_index_path.parent,
            self.catalog_path.parent,
            PROJECT_ROOT / "data" / "processed",
            PROJECT_ROOT / "reports",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def openai_key(self) -> str | None:
        """Devuelve la clave de OpenAI sin exponerla en logs/repr."""
        return self.openai_api_key.get_secret_value() if self.openai_api_key else None

    def anthropic_key(self) -> str | None:
        """Devuelve la clave de Anthropic sin exponerla en logs/repr."""
        return self.anthropic_api_key.get_secret_value() if self.anthropic_api_key else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración cacheada (útil para Streamlit y scripts)."""
    return Settings()


def reload_settings() -> Settings:
    """Limpia la caché y vuelve a leer el entorno (tests y cambios en caliente)."""
    get_settings.cache_clear()
    return get_settings()
