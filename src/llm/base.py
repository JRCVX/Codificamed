"""Contrato compartido para proveedores de modelos de lenguaje."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Interfaz única; los proveedores solo traducen el contrato al SDK/HTTP."""

    name: str
    model: str

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ) -> LLMResponse:
        """Genera una respuesta textual para una lista de mensajes role/content."""
