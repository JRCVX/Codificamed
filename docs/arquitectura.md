# Arquitectura — CodificaMed

![Arquitectura del pipeline](figuras/arquitectura.png)

## 1. Vista general

CodificaMed es un pipeline de PLN con recuperación aumentada por generación (RAG) y guardrails deterministas. La nota clínica entra como texto libre; el sistema recupera candidatos del catálogo CIE-10, detecta negaciones y estados, pide al LLM que seleccione y justifique códigos, y valida la salida contra el catálogo y el texto original.

```text
Nota → preproceso → negación/estado → recuperación híbrida → prompt → LLM
     → validación → agregación → UI/CLI/evaluación
```

## 2. Componentes

| Componente | Responsabilidad | Archivos previstos |
|---|---|---|
| Configuración | Leer `.env`, validar tipos, resolver rutas | `src/config.py` |
| Modelos de dominio | Catálogo, candidatos, evidencia, predicción | `src/catalog/models.py` |
| Preproceso | Normalizar, expandir abreviaturas, segmentar, tolerar typos | `src/preprocess/` |
| Catálogo | Cargar y validar los 98.268 códigos válidos | `src/catalog/loader.py` |
| Recuperación | Embeddings, FAISS, BM25, fusión RRF | `src/retrieval/` |
| Negación | Disparadores, alcance y estados clínicos | `src/negation/` |
| NER | Entidades clínicas opcionales | `src/ner/` |
| LLM | Interfaz única y proveedores | `src/llm/` |
| Pipeline | Orquestación, evidencia, agregación | `src/pipeline/` |
| Evaluación | Métricas, datasets, reportes | `src/eval/` |
| Interfaz | Streamlit | `app/streamlit_app.py` |

## 3. Flujo de datos

1. **Entrada:** nota clínica, `note_id` y configuración del proveedor.
2. **Normalización:** se preserva el texto original y se construye un mapa de offsets.
3. **Abreviaturas:** se expanden términos como `HTA`, `DM2`, `dolor abd` sin perder la mención original.
4. **Segmentación:** oraciones con offsets para asociar evidencia y negación.
5. **Negación:** cada mención recibe un estado; las negaciones duras no se codifican.
6. **Recuperación:** BM25 y FAISS devuelven candidatos; RRF fusiona y corta a top-k.
7. **Prompt:** se envía la nota, los candidatos y las anotaciones de negación.
8. **LLM:** devuelve JSON con códigos, estado, evidencia, confianza y justificación.
9. **Validación:** se rechaza todo código que no esté en el catálogo o en los candidatos; se alinea la evidencia; se resuelven conflictos a favor de la regla de negación.
10. **Salida:** `Prediction` con códigos, candidatos, latencia, uso y warnings.

## 4. Interfaz `LLMProvider`

```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1200,
        response_format: str | None = "json",
    ) -> LLMResponse: ...
```

- `OllamaProvider`: HTTP a `/api/chat`.
- `OpenAICompatibleProvider`: SDK `openai` con `base_url` configurable.
- `AnthropicProvider`: SDK `anthropic`.
- `MockProvider`: respuestas deterministas para tests y demo sin red.
- `factory.py`: elige el proveedor por `LLM_PROVIDER`; valida la clave requerida.

Ningún proveedor construye prompts ni parsea la salida por su cuenta: eso vive en `prompts.py` y `schemas.py`.

## 5. Guardrails

| Riesgo | Guardrail |
|---|---|
| Código inventado | Whitelist estricta contra los 98.268 códigos válidos |
| Evidencia falsa | Búsqueda exacta y fuzzy en el texto original |
| Negación ignorada | La regla determinista tiene prioridad sobre el LLM |
| JSON inválido | Validación Pydantic + un reintento de reparación |
| Prompt injection | Instrucciones del sistema y candidatos acotados |
| Fuga de claves | `SecretStr`, logs sin secretos, `.env` ignorado |
| Costo excesivo | Límite de tokens, top-k y cache |

## 6. Despliegue

- **Local:** `uv` + Python 3.11, Streamlit, Ollama.
- **API:** cualquier endpoint compatible con OpenAI o Anthropic.
- **Datos:** CodiEsp descargado por script; índice FAISS construido localmente.
- **Reproducibilidad:** versiones fijadas, semillas, cache de respuestas y manifiesto de datos.

## 7. Decisiones de arquitectura

| ID | Decisión | Alternativa | Motivo |
|---|---|---|---|
| A-001 | RAG sobre catálogo | LLM zero-shot | Evita alucinación y fundamenta el código |
| A-002 | Híbrido BM25 + denso | Solo denso | BM25 captura abreviaturas y términos exactos |
| A-003 | Negación por reglas | Solo LLM | Explicable, determinista y auditable |
| A-004 | FAISS | ChromaDB | Exacto y rápido a 98k; menos dependencias |
| A-005 | `LLMProvider` | Código por proveedor | Requisito 4 y testeabilidad |
| A-006 | Streamlit | React/FastAPI | Rapidez y resaltado en Python |
| A-007 | Validación estricta | Confiar en el LLM | Seguridad y trazabilidad |

## 8. Diagrama de despliegue

```text
┌──────────────────────┐        ┌──────────────────────────┐
│ Navegador            │  HTTP  │ Streamlit (Python 3.11)   │
│ usuario/codificador  │◄──────►│ app/streamlit_app.py      │
└──────────────────────┘        └────────────┬─────────────┘
                                             │
                       ┌─────────────────────┼─────────────────────┐
                       ▼                     ▼                     ▼
             ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
             │ FAISS + catálogo │  │ Ollama local     │  │ API externa      │
             │ data/indexes/    │  │ /api/chat        │  │ OpenAI/Anthropic │
             └──────────────────┘  └──────────────────┘  └──────────────────┘
```
