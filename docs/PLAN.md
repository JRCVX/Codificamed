# Plan integral — CodificaMed

- **Versión:** 1.0
- **Fecha:** 2026-11-02
- **Estado:** aprobado para ejecutar la Fase 1 (respuesta del usuario: “continuar”)
- **Materia:** Base de Conocimiento — PLN, ESPOCH FIE EIS

## 1. Objetivo

Prototipo que recibe una nota clínica en español y sugiere códigos CIE-10, mostrando la frase de evidencia y distinguiendo diagnósticos confirmados de negados o descartados, con abreviaturas y errores de tipeo.

## 2. Alcance

**Incluye:** diagnósticos CIE-10-CM de CodiEsp, texto libre en español, abreviaturas, typos, negación, RAG, LLM local y API externa, evaluación micro/macro, Streamlit, informe y guion de video.

**Excluye:** procedimientos CodiEsp-P, facturación real, datos de pacientes no públicos, fine-tuning, CIE-10 OMS y uso clínico.

## 3. Datos

| Fuente | Contenido | Licencia |
|---|---|---|
| Zenodo 3706838 | 98.268 códigos CIE-10-D válidos (98.288 filas) | CC-BY-4.0 |
| Zenodo 3837305 | 1.000 casos (500/250/250), 11.158 anotaciones, 2.557 códigos | CC-BY-4.0 |
| Zenodo 4121205 | Guías de anotación | CC-BY-4.0 |
| Propios | 40 casos ficticios (10 dev / 30 test) | Académico |

## 4. Decisiones

| Área | Decisión |
|---|---|
| Terminología | ICD-10-CM español 2018 (CodiEsp), diagnósticos |
| Python | 3.11.17 con `uv` |
| Embeddings | `intfloat/multilingual-e5-small`; benchmark con `BAAI/bge-m3` |
| Índice | FAISS `IndexFlatIP` + BM25 + RRF |
| Negación | NegEx adaptado al español, por reglas |
| NER | Opcional; checkpoints clínicos en español o fallback léxico |
| LLM | `LLMProvider` con Ollama, OpenAI-compatible, Anthropic y Mock |
| Validación | Pydantic + whitelist + evidencia + conflicto de negación |
| UI | Streamlit |
| Evaluación | CodiEsp test + ficticios; micro/macro P/R/F1, recall@k, evidencia, negación, latencia/costo |

## 5. Fases y entregables

| Fase | Entregables | QA |
|---|---|---|
| 1. Comprensión del negocio y datos | Plan, `ESTADO.md`, `CRISP-ML.md` §1-2, auditoría, arquitectura, scaffold | Licencia, descarga reproducible, sin secretos |
| 2. Preparación de datos | Descarga, catálogo procesado, 40 ficticios, preproceso, tests | Códigos válidos, spans alineados, sin fuga |
| 3. Modelado | Embeddings, FAISS, BM25, negación, NER opcional, LLM, pipeline | Recall@30, contratos, JSON válido |
| 4. Evaluación | Métricas, ablaciones, comparación local/API, errores | Reproducible, IC, ambos proveedores |
| 5. Despliegue | Streamlit, README, `.env.example`, demo | Entorno limpio, selector, evidencia |
| 6. Monitoreo y mantenimiento | Logs, drift, informe, guion, checklist | PDF/DOCX, video ≤10 min, evidencia |

## 6. Cronograma

| Sesión | Fase | Horas | Entregable |
|---|---|---|---|
| 1 | F1 | 3 | Plan, scaffold, auditoría, CRISP-ML §1-2 |
| 2–3 | F2 | 8 | Datos, catálogo, ficticios, preproceso |
| 4–6 | F3 | 12 | Retrieval, negación, proveedores, pipeline |
| 7–8 | F4 | 8 | Evaluación y comparación |
| 9–10 | F5 | 8 | UI, README, demo |
| 11–12 | F6 | 7 | Informe, video, QA |

Total estimado: 46 horas. Ajustable a la fecha límite.

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| Sin clave API | Adaptador listo + `MockProvider`; pedir clave; OpenRouter gratuito |
| GPU 4 GB | Benchmark, Q4, cache, CPU, resultados precalculados |
| Python 3.14 | `uv` con 3.11.17 |
| Descarga lenta | Reanudación, checksum, espejo |
| Alucinación | Whitelist + evidencia + rechazo |
| Evidencia desalineada | Offsets + fuzzy + “no verificada” |
| Costo API | Muestra de 150, tokens limitados, cache |
| Scope creep | Diagnósticos y NER opcional |
| Reproducibilidad | Semillas, versiones, cache, manifiesto |
| Ética | CC-BY, ficticios etiquetados, sin PHI |

## 8. Checklist de requisitos

- [x] Plan y arquitectura.
- [x] Datos verificables y licencia.
- [ ] Pipeline PLN completo.
- [ ] RAG + negación + NER opcional.
- [ ] Proveedor local y API intercambiables.
- [ ] Evaluación micro/macro con ambos proveedores.
- [ ] Interfaz con evidencia y selector.
- [ ] README, `.env.example`, `.gitignore`, tests, scripts.
- [ ] Informe ejecutivo DOCX/PDF con diagrama.
- [ ] Guion de video ≤10 min con rostro en esquina.
- [ ] Registro de modelos y estado actualizados.

## 9. Protocolo de cambio de modelo

Antes de cada fase se escribe el bloque:

```text
### 🔁 SOLICITUD DE CAMBIO DE MODELO
- Fase/tarea siguiente: ...
- Modelo recomendado (de la lista): ...
- Motivo: ...
- Alternativa si falla: ...
- Contexto que debo pegar al nuevo modelo: ...
```

Al cerrar la fase se registra en `docs/registro_modelos.md` qué modelo se usó, para qué y cómo rindió.
