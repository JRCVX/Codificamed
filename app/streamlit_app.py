"""Interfaz de sugerencia de códigos CIE-10 con evidencia y estado clínico."""

from __future__ import annotations

import json
import re
import sys
from html import escape
from pathlib import Path

import httpx
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.catalog.loader import Catalog
from src.catalog.models import RetrievalHit
from src.config import get_settings, reload_settings
from src.llm import create_provider
from src.pipeline.engine import ClinicalCodingPipeline
from src.preprocess import ClinicalPreprocessor
from src.retrieval.hybrid import E5Embedder, HybridRetriever

@st.cache_resource(show_spinner=False)
def load_catalog() -> Catalog:
    settings = get_settings()
    return Catalog.from_tsv(settings.catalog_path)


@st.cache_resource(show_spinner=False, hash_funcs={Catalog: lambda _: "catalog"})
def load_retriever(catalog: Catalog):
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
        except Exception as exc:  # pragma: no cover - se usa solo en runtime
            st.warning(f"No se pudo cargar el índice FAISS: {exc}. Se usa fallback léxico.")

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


def _provider_from_selection(provider_name: str):
    settings = reload_settings()
    settings.llm_provider = provider_name
    settings.llm_model = settings.llm_model

    if settings.llm_provider == "ollama":
        try:
            health = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=5.0)
            health.raise_for_status()
        except Exception:
            st.warning(
                f"Ollama no responde en {settings.ollama_base_url}. Se usa MockProvider para que la demo siga funcionando."
            )
            settings.llm_provider = "mock"
    elif settings.llm_provider in {"openrouter", "openai"}:
        api_key = settings.openrouter_key() if settings.llm_provider == "openrouter" else settings.openai_key()
        if not api_key:
            st.warning("No hay clave de API para el proveedor cloud. Se usa MockProvider determinista para la demo.")
            settings.llm_provider = "mock"

    try:
        return create_provider(settings)
    except ValueError as exc:
        st.warning(f"Proveedor no disponible: {exc}. Se usa MockProvider determinista para la demo.")

        def mock_response(messages: list[dict[str, str]]) -> str:
            payload = json.loads(messages[-1]["content"])
            note = payload["clinical_note"]
            note_tokens = {token for token in re.findall(r"[a-záéíóúüñ]+", note.lower()) if token}
            selected = []
            for candidate in payload.get("candidates", [])[:8]:
                desc = candidate.get("description", "").lower()
                desc_tokens = {token for token in re.findall(r"[a-záéíóúüñ]+", desc) if token}
                overlap = len(note_tokens & desc_tokens)
                if overlap > 0:
                    sentence = note.split(". ")[0].strip() if ". " in note else note.strip()
                    selected.append({
                        "code": candidate["code"],
                        "evidence": sentence[: min(180, len(sentence))] or note[: min(180, len(note))],
                        "state": "confirmed",
                        "confidence": min(0.95, 0.70 + 0.05 * overlap),
                        "rationale": "Mock determinista basado en sobreposición léxica con la nota.",
                    })
            return json.dumps({"codes": selected[:5]}, ensure_ascii=False)

        return create_provider(settings, mock_response=mock_response)


def _rag_summary() -> dict[str, object]:
    settings = get_settings()
    catalog = Catalog.from_tsv(settings.catalog_path)
    retriever_exists = settings.faiss_index_path.exists() and settings.faiss_codes_path.exists()
    return {
        "catalog_entries": len(catalog.codes()),
        "retriever_exists": retriever_exists,
        "faiss_path": settings.faiss_index_path,
        "codes_path": settings.faiss_codes_path,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "ollama_url": settings.ollama_base_url,
    }


def _highlight_evidence(note: str, codes: list) -> str:
    highlighted = note
    for suggestion in sorted(codes, key=lambda item: len(item.evidence or ""), reverse=True):
        evidence = suggestion.evidence or ""
        if not evidence:
            continue
        highlighted = highlighted.replace(evidence, f"<mark>{escape(evidence)}</mark>")
    return highlighted


def main() -> None:
    st.set_page_config(page_title="CodificaMed", page_icon="🩺", layout="wide")
    st.title("CodificaMed — sugerencia CIE-10")
    st.caption("Pipeline PLN con recuperación híbrida, negación y proveedor LLM configurable.")

    rag_summary = _rag_summary()
    st.subheader("RAG cargado")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Códigos del catálogo", rag_summary["catalog_entries"])
    col_b.metric("Índice FAISS", "Sí" if rag_summary["retriever_exists"] else "No")
    col_c.metric("Proveedor activo", rag_summary["provider"].upper())
    with st.expander("Ver detalle del RAG", expanded=True):
        st.write(f"Modelo: {rag_summary['model']}")
        st.write(f"URL Ollama: {rag_summary['ollama_url']}")
        st.write(f"FAISS: {rag_summary['faiss_path']}")
        st.write(f"Códigos: {rag_summary['codes_path']}")

    col1, col2 = st.columns([3, 1])
    with col1:
        note = st.text_area(
            "Nota clínica",
            value=(
                "Paciente de 64 años con HTA y DM2. Niega fiebre. Se diagnostica insuficiencia cardiaca "
                "con fracción de eyección preservada."
            ),
            height=220,
        )
    with col2:
        deployment_options = [
            ("local", "Ollama — local (Mistral)"),
            ("cloud", "Cloud — OpenRouter / OpenAI-compatible"),
        ]
        deployment_mode = st.selectbox(
            "Tipo de IA",
            options=[item[0] for item in deployment_options],
            format_func=lambda choice: next(label for value, label in deployment_options if value == choice),
            index=0,
        )
        settings = reload_settings()
        if deployment_mode == "cloud":
            settings.llm_provider = "openrouter"
            settings.llm_model = st.text_input(
                "Modelo cloud",
                value=settings.openrouter_model,
                help="Ejemplo: openai/gpt-4o-mini o meta-llama/llama-3.1-8b-instruct:free",
            )
            settings.openrouter_model = settings.llm_model
            settings.ollama_base_url = "http://localhost:11434"
        else:
            settings.llm_provider = "ollama"
            settings.ollama_base_url = "http://localhost:11434"
            settings.llm_model = "mistral"
        top_k = st.slider("Top-k candidatos", min_value=5, max_value=50, value=10)

        status_placeholder = st.empty()
        is_processing = st.session_state.get("processing", False)
        if is_processing:
            status_placeholder.info("Procesando nota con Ollama local… puede tardar unos segundos.")

        with st.form("coding_form", clear_on_submit=False):
            submitted = st.form_submit_button(
                "Codificar nota",
                type="primary",
                use_container_width=True,
                disabled=is_processing,
            )

        if submitted:
            st.session_state.processing = True
            status_placeholder.info("Procesando nota con Ollama local… esto puede tardar unos segundos.")
            try:
                catalog = load_catalog()
                retriever = load_retriever(catalog)
                with st.spinner("Consultando Ollama y recuperando candidatos…"):
                    pipeline = ClinicalCodingPipeline(
                        catalog=catalog,
                        retriever=retriever,
                        provider=_provider_from_selection("ollama"),
                        preprocessor=ClinicalPreprocessor(),
                        top_k=top_k,
                    )
                    prediction = pipeline.run(note)
            except Exception as exc:  # pragma: no cover - runtime fallback simple
                st.session_state.processing = False
                status_placeholder.error(f"No pudo ejecutarse el pipeline: {exc}")
                st.error(f"No pudo ejecutarse el pipeline: {exc}")
                return
            finally:
                st.session_state.processing = False
                status_placeholder.success("Procesamiento completado.")

            st.subheader("Resultados")
            if not prediction.codes:
                st.info("El pipeline no devolvió códigos para esta nota.")
            else:
                cols = st.columns(4)
                with cols[0]:
                    st.metric("Códigos", len(prediction.codes))
                with cols[1]:
                    st.metric("Latencia", f"{prediction.latency_ms:.1f} ms" if prediction.latency_ms is not None else "n/a")
                with cols[2]:
                    st.metric("Proveedor", prediction.provider)
                with cols[3]:
                    st.metric("Modelo", prediction.model)

                for suggestion in prediction.codes:
                    with st.container():
                        st.markdown(
                            f"### {suggestion.code} — {suggestion.description}"
                            f"<br><small>Estado: {suggestion.state.value} · Confianza: {suggestion.confidence:.2f}</small>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**Evidencia:** {suggestion.evidence or '—'}")
                        if suggestion.rationale:
                            st.caption(suggestion.rationale)

                st.subheader("Evidencia resaltada")
                st.markdown(_highlight_evidence(note, prediction.codes), unsafe_allow_html=True)

                with st.expander("Candidatos recuperados"):
                    for hit in prediction.candidates[:10]:
                        st.write(f"{hit.rank}. {hit.code} — {hit.description_es} (score={hit.score:.3f})")

                with st.expander("Advertencias del pipeline"):
                    if prediction.warnings:
                        for warning in prediction.warnings:
                            st.warning(warning)
                    else:
                        st.success("Sin advertencias")


if __name__ == "__main__":
    main()
