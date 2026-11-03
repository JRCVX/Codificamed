"""Orquestación del pipeline RAG con evidencia y validación determinista."""

from __future__ import annotations

import json
import re
import time
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.catalog.loader import Catalog
from src.catalog.models import ClinicalState, CodeSuggestion, Prediction, RetrievalHit
from src.llm.base import LLMProvider
from src.negation.detector import SentenceStatus, SpanishNegationDetector
from src.preprocess import ClinicalPreprocessor


class Retriever(Protocol):
    def retrieve(self, query: str, *, top_k: int = 30) -> list[RetrievalHit]: ...


class _LLMCode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    evidence: str
    state: ClinicalState = ClinicalState.CONFIRMED
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str | None = None


class _LLMOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    codes: list[_LLMCode] = Field(default_factory=list)


SYSTEM_PROMPT = """Eres un asistente de codificación CIE-10-CM en español. No diagnostiques ni inventes.
Selecciona solo códigos de los candidatos dados. Devuelve exclusivamente JSON con forma:
{"codes":[{"code":"...","evidence":"cita literal completa de la nota","state":"confirmed|negated|suspected|historical|family|uncertain","confidence":0.0,"rationale":"breve"}]}
Reglas estrictas:
- Si la nota menciona un diagnóstico, sospecha, antecedente o diagnóstico confirmado relevante, no devuelvas un arreglo vacío `[]`.
- Usa solo códigos presentes entre los candidatos del usuario.
- No escribas texto fuera del JSON. No escribas markdown ni explicaciones previas.
- La evidencia debe ser una subcadena literal y exacta de la nota.
- Incluye diagnósticos explícitos relevantes; no conviertas síntomas negados en diagnósticos confirmados.
- Si hay varias opciones, devuelve las más probables y útiles, no el array vacío."""


class ClinicalCodingPipeline:
    def __init__(
        self,
        *,
        catalog: Catalog,
        retriever: Retriever,
        provider: LLMProvider,
        preprocessor: ClinicalPreprocessor | None = None,
        negation: SpanishNegationDetector | None = None,
        top_k: int = 30,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ) -> None:
        self.catalog, self.retriever, self.provider = catalog, retriever, provider
        self.preprocessor = preprocessor or ClinicalPreprocessor()
        self.negation = negation or SpanishNegationDetector()
        self.top_k, self.temperature, self.max_tokens = top_k, temperature, max_tokens

    def run(self, text: str, *, note_id: str = "note") -> Prediction:
        if not text.strip():
            raise ValueError("La nota clínica no puede estar vacía")
        started = time.perf_counter()
        preprocessed = self.preprocessor.preprocess(text)
        statuses = self.negation.detect(text)
        hits = self.retriever.retrieve(preprocessed.retrieval_text, top_k=self.top_k)
        messages = self._messages(text, hits, statuses)
        response = self.provider.complete(messages, temperature=self.temperature, max_tokens=self.max_tokens)
        warnings: list[str] = []
        try:
            raw = self._parse(response.content)
        except ValueError:
            repair_messages = [
                *messages,
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": "Repara la respuesta anterior. Devuelve solo JSON válido con el esquema solicitado."},
            ]
            try:
                response = self.provider.complete(
                    repair_messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                raw = self._parse(response.content)
                warnings.append("La salida JSON del proveedor requirió una reparación")
            except ValueError:
                raw = _LLMOutput()
                warnings.append("Salida JSON inválida tras un reintento; se devuelve sin códigos")

        if not raw.codes and hits and not any("Salida JSON inválida" in warning or "La salida JSON del proveedor requirió una reparación" in warning for warning in warnings):
            repair_messages = [
                *messages,
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": "La respuesta anterior está vacía. Esta nota contiene diagnósticos relevantes. Devuelve solo JSON con al menos un código válido de los candidatos propuestos; no devuelvas \"codes\": [] ni un arreglo vacío."},
            ]
            try:
                response = self.provider.complete(
                    repair_messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                raw = self._parse(response.content)
                if raw.codes:
                    warnings.append("El proveedor respondió vacío; se reintentó con instrucción estricta")
            except ValueError:
                raw = _LLMOutput()
                warnings.append("El proveedor respondió vacío y la corrección automática falló")

        if not raw.codes and hits and not any("El proveedor respondió vacío" in warning or "Salida JSON inválida" in warning for warning in warnings):
            raw = self._fallback_from_hits(text, hits)
            warnings.append("El proveedor devolvió una respuesta vacía; se reutilizaron los candidatos recuperados")

        suggestions: list[CodeSuggestion] = []
        candidate_codes = {hit.code for hit in hits}
        seen: set[tuple[str, int, int]] = set()
        for proposed in raw.codes:
            code = proposed.code.strip().upper()
            entry = self.catalog.get(code)
            if entry is None:
                warnings.append(f"Código fuera del catálogo rechazado: {code}")
                continue
            if code not in candidate_codes:
                warnings.append(f"Código no recuperado como candidato rechazado: {code}")
                continue
            start = text.find(proposed.evidence)
            if start < 0 or not proposed.evidence.strip():
                warnings.append(f"Evidencia no literal rechazada para {code}")
                continue
            end = start + len(proposed.evidence)
            key = (code, start, end)
            if key in seen:
                continue
            seen.add(key)
            rule_state = self.negation.state_for_span((start, end), statuses)
            state = rule_state if rule_state != ClinicalState.CONFIRMED else proposed.state
            if state != proposed.state:
                warnings.append(f"Estado {proposed.state.value} corregido a {state.value} por regla de contexto ({code})")
            suggestions.append(
                CodeSuggestion(
                    code=code,
                    description=entry.description_es,
                    state=state,
                    confidence=proposed.confidence,
                    evidence=proposed.evidence,
                    span=(start, end),
                    rationale=proposed.rationale,
                    provider=response.provider,
                    model=response.model,
                )
            )
        elapsed = (time.perf_counter() - started) * 1000
        return Prediction(
            note_id=note_id,
            text=text,
            codes=suggestions,
            candidates=hits,
            provider=response.provider,
            model=response.model,
            latency_ms=elapsed,
            usage=response.usage,
            warnings=warnings,
        )

    @staticmethod
    def _parse(content: str) -> _LLMOutput:
        candidate = content.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].lstrip()
        try:
            return _LLMOutput.model_validate_json(candidate)
        except ValidationError as original_error:
            left, right = candidate.find("{"), candidate.rfind("}")
            if left >= 0 and right > left:
                try:
                    return _LLMOutput.model_validate_json(candidate[left : right + 1])
                except ValidationError:
                    pass
            raise ValueError("El proveedor no devolvió JSON válido con el esquema esperado") from original_error

    @staticmethod
    def _fallback_from_hits(text: str, hits: list[RetrievalHit]) -> _LLMOutput:
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text.strip()) if segment.strip()]
        evidence = sentences[0] if sentences else text.strip()[:200]
        fallback_hits = hits[: min(3, len(hits))]
        return _LLMOutput(
            codes=[
                _LLMCode(
                    code=hit.code,
                    evidence=evidence,
                    state=ClinicalState.CONFIRMED,
                    confidence=max(0.4, min(0.9, hit.score / 10.0)),
                    rationale="Candidato recuperado porque el proveedor devolvió una respuesta vacía.",
                )
                for hit in fallback_hits
            ]
        )

    @staticmethod
    def _messages(text: str, hits: list[RetrievalHit], statuses: list[SentenceStatus]) -> list[dict[str, str]]:
        candidates = [
            {"code": hit.code, "description": hit.description_es, "rank": hit.rank}
            for hit in hits
        ]
        context = [
            {"text": status.sentence.text, "state": status.state.value, "trigger": status.trigger}
            for status in statuses
        ]
        user_payload = {
            "clinical_note": text,
            "candidates": candidates,
            "sentence_states": context,
        }
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
