from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.services.coding_service import get_rag_status, process_note

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 8010
FRONTEND_ROOT = PROJECT_ROOT / "frontend" if (PROJECT_ROOT / "frontend").exists() else PROJECT_ROOT / "web"


def get_port() -> int:
    raw_value = os.getenv("PORT", "").strip()
    if raw_value and raw_value.isdigit():
        return int(raw_value)
    return DEFAULT_PORT


app = FastAPI(
    title="CodificaMed API",
    description="Backend FastAPI para alta calidad de codificación clínica con RAG y Ollama.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Nota clínica a codificar")
    top_k: int = Field(default=10, ge=5, le=50)
    provider_mode: Literal["local", "cloud"] = Field(default="local", description="Elige entre Ollama local o un proveedor cloud externo")
    provider_name: Literal["ollama", "openrouter", "openai", "gemini", "anthropic"] | None = Field(default=None, description="Proveedor cloud a usar cuando el modo es cloud")
    api_key: str | None = Field(default=None, description="Se ignora en la interfaz, la clave debe estar en .env")
    ollama_base_url: str | None = Field(default=None, description="URL del servidor Ollama solo si se usa Ollama remoto")
    llm_model: str | None = Field(default=None, description="Modelo concreto a usar: local Mistral o cloud GPT/Gemini/OpenRouter/Claude")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "service": "codificamed-api"}


@app.get("/api/rag/status")
def rag_status() -> dict[str, object]:
    return get_rag_status()


@app.post("/api/code")
def code_note(payload: CodeRequest) -> dict[str, object]:
    try:
        return process_note(
            payload.text,
            top_k=payload.top_k,
            provider_mode=payload.provider_mode,
            ollama_base_url=payload.ollama_base_url,
            llm_model=payload.llm_model,
            provider_name=payload.provider_name,
            api_key=payload.api_key,
        )
    except Exception as exc:  # pragma: no cover - error de runtime
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_ROOT / "index.html")


app.mount("/static", StaticFiles(directory=str(FRONTEND_ROOT / "static")), name="static")
