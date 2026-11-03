"""Adaptadores HTTP de Ollama y APIs compatibles, más proveedor de pruebas."""

from __future__ import annotations

from typing import Any

import httpx

from src.config import Settings
from src.llm.base import LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 300.0) -> None:
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 1200) -> LLMResponse:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False,
                  "format": "json", "options": {"temperature": temperature, "num_predict": max_tokens}},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return LLMResponse(
            content=payload["message"]["content"], provider=self.name, model=self.model,
            usage={"prompt_tokens": payload.get("prompt_eval_count"), "completion_tokens": payload.get("eval_count")},
        )


class OpenRouterProvider(LLMProvider):
    """Proveedor cloud compatible con OpenRouter/OpenAI-style API."""

    name = "openrouter"

    def __init__(self, api_key: str | None, model: str, base_url: str = "https://openrouter.ai/api/v1", timeout: float = 300.0) -> None:
        if not api_key:
            raise ValueError("Falta la clave OPENROUTER_API_KEY o OPENAI_API_KEY para usar el proveedor cloud.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 1200) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://codificamed.local",
                "X-Title": "CodificaMed",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return LLMResponse(
            content=str(content),
            provider=self.name,
            model=self.model,
            usage={
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens"),
                "completion_tokens": data.get("usage", {}).get("completion_tokens"),
            },
        )


class OpenAIProvider(LLMProvider):
    """Proveedor cloud nativo de OpenAI."""

    name = "openai"

    def __init__(self, api_key: str | None, model: str, base_url: str = "https://api.openai.com/v1", timeout: float = 300.0) -> None:
        if not api_key:
            raise ValueError("Falta la clave OPENAI_API_KEY para usar OpenAI.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 1200) -> LLMResponse:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        return LLMResponse(
            content=str(choice["message"]["content"]),
            provider=self.name,
            model=self.model,
            usage={
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens"),
                "completion_tokens": data.get("usage", {}).get("completion_tokens"),
            },
        )


class GeminiProvider(LLMProvider):
    """Proveedor cloud para Google Gemini."""

    name = "gemini"
    fallback_models = (
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.8-flash",
    )

    def __init__(self, api_key: str | None, model: str, base_url: str = "https://generativelanguage.googleapis.com", timeout: float = 300.0) -> None:
        if not api_key:
            raise ValueError("Falta la clave GEMINI_API_KEY para usar Gemini.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _to_prompt(messages: list[dict[str, str]]) -> str:
        parts: list[str] = []
        for message in messages:
            role = message.get("role", "user")
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            if role == "assistant":
                parts.append(f"Assistant: {content}")
            elif role == "system":
                parts.append(f"System: {content}")
            else:
                parts.append(f"User: {content}")
        return "\n".join(parts) or "Contenido vacio"

    def _ordered_models(self) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for model_name in [self.model, *self.fallback_models]:
            if model_name and model_name not in seen:
                ordered.append(model_name)
                seen.add(model_name)
        return ordered

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 1200) -> LLMResponse:
        prompt = self._to_prompt(messages)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        last_error: Exception | None = None

        for model_name in self._ordered_models():
            try:
                response = httpx.post(
                    f"{self.base_url}/v1beta/models/{model_name}:generateContent?key={self.api_key}",
                    json=payload,
                    timeout=self.timeout,
                )
                if response.status_code in {404, 429, 500, 503}:
                    last_error = httpx.HTTPStatusError(
                        f"Gemini model '{model_name}' is unavailable or temporarily overloaded.",
                        request=response.request,
                        response=response,
                    )
                    continue
                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates", [])
                candidate = candidates[0] if candidates else {}
                content_block = candidate.get("content", {}) if isinstance(candidate, dict) else {}
                parts = content_block.get("parts", []) if isinstance(content_block, dict) else []
                if parts:
                    text = "".join(
                        str(part.get("text", ""))
                        for part in parts
                        if isinstance(part, dict)
                    )
                else:
                    text = ""
                self.model = model_name
                return LLMResponse(
                    content=str(text),
                    provider=self.name,
                    model=self.model,
                    usage={
                        "prompt_tokens": data.get("usageMetadata", {}).get("promptTokenCount"),
                        "completion_tokens": data.get("usageMetadata", {}).get("candidatesTokenCount"),
                    },
                )
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code in {404, 429, 500, 503}:
                    last_error = exc
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("No se pudo completar la llamada a Gemini con un modelo válido.")


class AnthropicProvider(LLMProvider):
    """Proveedor cloud para Anthropic Claude."""

    name = "anthropic"

    def __init__(self, api_key: str | None, model: str, base_url: str = "https://api.anthropic.com", timeout: float = 300.0) -> None:
        if not api_key:
            raise ValueError("Falta la clave ANTHROPIC_API_KEY para usar Anthropic.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 1200) -> LLMResponse:
        system_prompt = next((msg["content"] for msg in messages if msg.get("role") == "system"), "")
        user_messages = [msg for msg in messages if msg.get("role") != "system"]
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        response = httpx.post(
            f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        text = data["content"][0]["text"]
        return LLMResponse(
            content=str(text),
            provider=self.name,
            model=self.model,
            usage={
                "prompt_tokens": data.get("usage", {}).get("input_tokens"),
                "completion_tokens": data.get("usage", {}).get("output_tokens"),
            },
        )


class MockProvider(LLMProvider):
    """Proveedor sin red para pruebas y demos; acepta respuesta fija o callback."""

    name = "mock"

    def __init__(self, response: str | Any = '{"codes": []}', model: str = "mock-v1") -> None:
        self.response, self.model = response, model

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0, max_tokens: int = 1200) -> LLMResponse:
        content = self.response(messages) if callable(self.response) else self.response
        return LLMResponse(content=str(content), provider=self.name, model=self.model)


def create_provider(settings: Settings, *, mock_response: str | Any | None = None) -> LLMProvider:
    """Construye el proveedor activo del sistema: Ollama local, cloud o mock demo."""
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.ollama_base_url, settings.llm_model)
    if settings.llm_provider == "openrouter":
        return OpenRouterProvider(settings.openrouter_key(), settings.openrouter_model, settings.openrouter_base_url)
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.openai_key(), settings.openai_model, settings.openai_base_url)
    if settings.llm_provider == "gemini":
        return GeminiProvider(settings.gemini_key(), settings.gemini_model, settings.gemini_base_url)
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(settings.anthropic_key(), settings.anthropic_model, settings.anthropic_base_url)
    if settings.llm_provider == "mock":
        return MockProvider(mock_response or '{"codes": []}', settings.llm_model)
    raise ValueError(
        f"Proveedor no soportado: {settings.llm_provider}. Se admiten ollama, openrouter, openai, gemini, anthropic y mock."
    )
