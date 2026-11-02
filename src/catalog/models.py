"""Modelos de dominio compartidos: catálogo, recuperación y predicciones."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClinicalState(StrEnum):
    """Estado clínico de una mención o diagnóstico."""

    CONFIRMED = "confirmed"
    NEGATED = "negated"
    SUSPECTED = "suspected"
    HISTORICAL = "historical"
    FAMILY = "family"
    UNCERTAIN = "uncertain"


class CatalogEntry(BaseModel):
    """Un código del catálogo CIE-10 con sus descripciones."""

    model_config = ConfigDict(extra="forbid")

    code: str
    description_es: str
    description_en: str | None = None

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("El código no puede estar vacío")
        return value

    @field_validator("description_es", "description_en")
    @classmethod
    def _strip_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class RetrievalHit(BaseModel):
    """Candidato recuperado del catálogo."""

    model_config = ConfigDict(extra="forbid")

    code: str
    description_es: str
    score: float = Field(ge=0.0)
    rank: int = Field(ge=1)
    source: str = "hybrid"


class EvidenceSpan(BaseModel):
    """Fragmento textual que justifica una mención clínica."""

    model_config = ConfigDict(extra="forbid")

    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    sentence: str | None = None
    state: ClinicalState = ClinicalState.CONFIRMED

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, value: int, info: Any) -> int:
        start = info.data.get("start")
        if start is not None and value < start:
            raise ValueError("end debe ser mayor o igual que start")
        return value


class CodeSuggestion(BaseModel):
    """Código sugerido por el pipeline, con evidencia y estado."""

    model_config = ConfigDict(extra="forbid")

    code: str
    description: str
    state: ClinicalState = ClinicalState.CONFIRMED
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = None
    span: tuple[int, int] | None = None
    rationale: str | None = None
    provider: str | None = None
    model: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class Prediction(BaseModel):
    """Salida completa del pipeline para una nota."""

    model_config = ConfigDict(extra="forbid")

    note_id: str
    text: str
    codes: list[CodeSuggestion] = Field(default_factory=list)
    candidates: list[RetrievalHit] = Field(default_factory=list)
    provider: str
    model: str
    latency_ms: float | None = Field(default=None, ge=0.0)
    usage: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
