from __future__ import annotations

from urllib.parse import urlparse

from pydantic import SecretStr

from src.catalog.loader import Catalog
from src.catalog.models import RetrievalHit
from src.config import Settings, get_settings
from src.llm import create_provider
from src.pipeline.engine import ClinicalCodingPipeline
from src.preprocess import ClinicalPreprocessor
from src.retrieval.hybrid import E5Embedder, HybridRetriever


def infer_provider_mode(ollama_base_url: str | None = None, *, selected_provider: str | None = None) -> str:
    settings = get_settings()
    provider = (selected_provider or settings.llm_provider or "ollama").strip().lower()
    if provider in {"openrouter", "openai", "gemini", "anthropic"}:
        return "cloud"
    if provider == "ollama":
        base_url = (ollama_base_url or settings.ollama_base_url or "http://localhost:11434").strip()
        host = urlparse(base_url).hostname or ""
        return "cloud" if host and host not in {"localhost", "127.0.0.1", "0.0.0.0"} else "local"
    base_url = (ollama_base_url or settings.ollama_base_url or "http://localhost:11434").strip()
    host = urlparse(base_url).hostname or ""
    return "cloud" if host and host not in {"localhost", "127.0.0.1", "0.0.0.0"} else "local"


def build_runtime_settings(*, provider_mode: str | None = None, ollama_base_url: str | None = None, llm_model: str | None = None, provider_name: str | None = None, api_key: str | None = None) -> Settings:
    settings = get_settings()
    runtime = settings.model_copy(deep=True)

    mode = provider_mode or infer_provider_mode(settings.ollama_base_url, selected_provider=provider_name or settings.llm_provider)
    if mode == "cloud":
        selected_provider = (provider_name or "openrouter").strip().lower()
        if selected_provider == "ollama":
            remote_url = (ollama_base_url or settings.ollama_base_url or "").strip()
            if not remote_url or remote_url.startswith("http://localhost") or remote_url.startswith("http://127.0.0.1") or remote_url.startswith("http://0.0.0.0"):
                raise ValueError("Para el modo cloud con Ollama debes indicar una URL remota real; no vale localhost.")
            runtime.llm_provider = "ollama"
            runtime.ollama_base_url = remote_url
            runtime.llm_model = llm_model or "glm-5.3-flash:cloud"
            return runtime

        runtime.llm_provider = selected_provider if selected_provider in {"openrouter", "openai", "gemini", "anthropic"} else "openrouter"
        runtime.ollama_base_url = "http://localhost:11434"
        if runtime.llm_provider == "gemini":
            runtime.gemini_model = llm_model or runtime.gemini_model
            runtime.llm_model = runtime.gemini_model
            if api_key:
                runtime.gemini_api_key = SecretStr(api_key)
        elif runtime.llm_provider == "anthropic":
            runtime.anthropic_model = llm_model or runtime.anthropic_model
            runtime.llm_model = runtime.anthropic_model
            if api_key:
                runtime.anthropic_api_key = SecretStr(api_key)
        elif runtime.llm_provider == "openrouter":
            runtime.openrouter_model = llm_model or runtime.openrouter_model
            runtime.llm_model = runtime.openrouter_model
            if api_key:
                runtime.openrouter_api_key = SecretStr(api_key)
        else:
            runtime.openai_model = llm_model or runtime.openai_model
            runtime.llm_model = runtime.openai_model
            if api_key:
                runtime.openai_api_key = SecretStr(api_key)
        return runtime

    runtime.llm_provider = "ollama"
    runtime.ollama_base_url = "http://localhost:11434"
    runtime.llm_model = llm_model or "mistral"
    return runtime


def _fallback_retriever(catalog: Catalog):
    class FallbackRetriever:
        def retrieve(self, query: str, *, top_k: int = 30) -> list[RetrievalHit]:
            q_tokens = {token for token in query.lower().replace("-", " ").split() if token}
            scored = []
            for item in catalog.entries():
                text = f"{item.description_es} {item.description_en or ''}".lower()
                overlap = len({token for token in text.split()} & q_tokens)
                if not overlap:
                    continue
                score = (0.5 + overlap / max(len(q_tokens), 1)) * 100
                scored.append((item.code, item.description_es, score))
            ranked = sorted(scored, key=lambda row: row[2], reverse=True)[:top_k]
            return [
                RetrievalHit(code=code, description_es=description, score=score, rank=rank, source="fallback")
                for rank, (code, description, score) in enumerate(ranked, start=1)
            ]

    return FallbackRetriever()


def build_retriever(catalog: Catalog):
    settings = get_settings()
    index_path = settings.faiss_index_path
    codes_path = settings.faiss_codes_path
    if index_path.exists() and codes_path.exists():
        try:
            return HybridRetriever(
                catalog,
                E5Embedder(settings.embedding_model, settings.embedding_device),
                index_path,
                codes_path,
                bm25_top_k=settings.bm25_top_k,
                dense_top_k=settings.dense_top_k,
            )
        except Exception:
            return _fallback_retriever(catalog)
    return _fallback_retriever(catalog)


def _active_model_name(settings: Settings) -> str:
    provider = settings.llm_provider
    if provider == "gemini":
        return settings.gemini_model or settings.llm_model
    if provider == "openai":
        return settings.openai_model or settings.llm_model
    if provider == "anthropic":
        return settings.anthropic_model or settings.llm_model
    if provider == "openrouter":
        return settings.openrouter_model or settings.llm_model
    return settings.llm_model


def get_rag_status() -> dict[str, object]:
    settings = get_settings()
    catalog = Catalog.from_tsv(settings.catalog_path)
    provider_mode = infer_provider_mode(settings.ollama_base_url, selected_provider=settings.llm_provider)
    return {
        "catalog_entries": len(catalog.codes()),
        "faiss_index_exists": settings.faiss_index_path.exists(),
        "codes_index_exists": settings.faiss_codes_path.exists(),
        "provider": settings.llm_provider,
        "provider_mode": provider_mode,
        "model": _active_model_name(settings),
        "ollama_url": settings.ollama_base_url,
    }


def process_note(text: str, *, top_k: int = 10, provider_mode: str | None = None, ollama_base_url: str | None = None, llm_model: str | None = None, provider_name: str | None = None, api_key: str | None = None) -> dict[str, object]:
    settings = build_runtime_settings(
        provider_mode=provider_mode,
        ollama_base_url=ollama_base_url,
        llm_model=llm_model,
        provider_name=provider_name,
        api_key=api_key,
    )
    catalog = Catalog.from_tsv(settings.catalog_path)
    retriever = build_retriever(catalog)
    provider = create_provider(settings)
    pipeline = ClinicalCodingPipeline(
        catalog=catalog,
        retriever=retriever,
        provider=provider,
        preprocessor=ClinicalPreprocessor(),
        top_k=top_k,
    )
    prediction = pipeline.run(text)
    return prediction.model_dump(mode="json")
