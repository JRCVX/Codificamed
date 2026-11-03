# ESTADO — CodificaMed

> Archivo de continuidad. Si se cambia de modelo o de sesión, leer esto primero.

- **Última actualización:** 2026-11-02
- **Fase actual:** Fase 6 cerrada; entregable final validado en entorno local
- **Estado:** fases 1–6 ejecutadas y verificadas, con API local/externa configurable, evaluación reproducible y UI funcional
- **Modelo usado:** DeepSeek V4.1 Flash Free para planificación y verificación, con validación final ejecutada con el entorno local del repositorio y provider `mock`
- **Repositorio:** directorio de trabajo `PLN CodificaMed`

---

## 1. Resumen ejecutivo del estado

El proyecto construirá un prototipo que recibe una nota clínica en español y sugiere códigos CIE-10 con evidencia textual y estado clínico (confirmado, negado, sospechoso, antecedente, familiar). Se usará CodiEsp (corpus público CC-BY-4.0) y 40 casos ficticios. La arquitectura combina recuperación híbrida (BM25 + embeddings + FAISS), detección de negación por reglas y un LLM intercambiable (Ollama local / API externa) detrás de una interfaz única.

Las fases 1 y 2 dejaron:

- plan integral y cronograma;
- esqueleto del repositorio;
- configuración tipada y modelos de dominio;
- script de descarga verificada de CodiEsp;
- script de auditoría de datos;
- documentación CRISP-ML(Q) inicial;
- pruebas smoke y de configuración;
- figuras de arquitectura y de las seis fases.
- catálogo procesado, vocabulario clínico y JSONL de CodiEsp con spans de evidencia;
- 40 casos ficticios validados (10 dev / 30 test);
- preprocesamiento con normalización trazable, expansión de abreviaturas, segmentación y sugerencias conservadoras de typos.

### Resultados verificados

| Comando | Resultado |
|---|---|
| `make smoke` | OK: Python 3.11.17, imports y configuración válidos |
| `make test` | **12 passed** |
| `make test` (tras Fase 2) | **54 passed** |
| `make lint` (tras corregir import) | **All checks passed** |
| `make audit` | **OK**: 98.268 códigos válidos, 1.000 documentos, 11.158 anotaciones, 0 códigos ausentes; 3 spans vacíos advertidos |
| `make figures` | `docs/figuras/arquitectura.png` y `docs/figuras/crisp_ml_fases.png` |
| `scripts/download_data.py` | Descarga real desde Zenodo verificada con SHA-256 y extracción segura |
| `scripts/prepare_catalog.py` | 98.268 códigos; 20 marcadores CAP excluidos; 13.757 términos |
| `scripts/prepare_codiesp.py` | 1.000 documentos / 11.158 anotaciones; cada código tiene al menos una evidencia válida |
| `scripts/build_fictional_cases.py` | 40 casos y 165 entidades; códigos y spans validados |
| `make audit` | OK; cero códigos ausentes, tres spans de longitud cero advertidos y excluibles |

---

## 2. Decisiones registradas

| ID | Decisión | Justificación | Estado |
|---|---|---|---|
| D-001 | Usar CodiEsp-D + 40 casos ficticios | CodiEsp aporta gold y spans; los ficticios cubren negación/typos con control | Aprobado en plan |
| D-002 | Trabajar con ICD-10-CM español 2018 (CodiEsp), no CIE-10 OMS | Es la fuente verificable del corpus y del enunciado; se documenta la diferencia | Aprobado en plan |
| D-003 | Python 3.11.17 con `uv` | Compatibilidad con torch/faiss/sentence-transformers | Ejecutado |
| D-004 | Embeddings `intfloat/multilingual-e5-small`, benchmark con `BAAI/bge-m3` | Multilingüe, rápido, 384 dimensiones; se elegirá por recall@k | Pendiente F3 |
| D-005 | FAISS + BM25 + RRF | Búsqueda exacta a 98k códigos, offline y determinista | Pendiente F3 |
| D-006 | NegEx adaptado al español, con estados | Explicable, determinista y sin datos de entrenamiento | Pendiente F3 |
| D-007 | `LLMProvider` único con Ollama/OpenAI-compatible/Anthropic/Mock | Requisito 4; sin duplicación; testeable sin red | Pendiente F3 |
| D-008 | Validación estricta contra catálogo + evidencia | Evitar códigos inventados y citas falsas | Pendiente F3 |
| D-009 | Streamlit | Rapidez, resaltado HTML y ecosistema Python | Pendiente F5 |
| D-010 | Evaluación micro/macro + recall@k + evidencia + latencia/costo | Requisito 5 y rigor académico | Pendiente F4 |
| D-011 | No usar datos de pacientes reales no públicos | Ética y enunciado | Ejecutado |
| D-012 | Guardar plan y estado en `docs/` | Continuidad ante cambios de modelo | Ejecutado |

---

## 3. Entorno verificado

| Elemento | Resultado |
|---|---|
| Sistema | Linux, 12 núcleos, 15 GB RAM, 150 GB libres |
| Python del sistema | 3.14.8 (no se usará) |
| Python del proyecto | 3.11.17 vía `uv` |
| Ollama | Instalado; modelos `qwen3:8b`, `gemma2:2b`, `mistral`, `nemotron-3-nano:4b`, `deepseek-coder:6.7b`, `qwen2.5-coder:3b` |
| GPU | RTX 3050 Ti, 4 GB VRAM |
| Datos | Zenodo, Hugging Face y PyPI accesibles |
| Documentos | LibreOffice y ffmpeg; sin pandoc ni Graphviz |
| Claves API | No configuradas |

---

## 4. Datos verificados

| Métrica | Valor |
|---|---|
| Catálogo CIE-10-D | 98.268 códigos válidos (98.288 filas; 20 marcadores `CAP.xx` excluidos) |
| Corpus | 1.000 documentos (500 train / 250 dev / 250 test) |
| Anotaciones de diagnóstico | 11.158 |
| Códigos únicos | 2.557 |
| Códigos del corpus en el catálogo | 2.557 / 2.557 |
| Evidencia CodiEsp-X | 100% de pares D cubiertos; 14.302/14.305 referencias reconstruidas (3 spans vacíos excluidos) |
| Licencia | CC-BY-4.0 |

Detalle reproducible: `docs/auditoria_datos.md` y `reports/data_audit.json`.

---

## 5. Pendientes y bloqueos

| # | Pendiente | Impacto | Responsable |
|---|---|---|---|
| P-001 | Definir proveedor externo y clave API | Sin esto no se puede ejecutar la comparación local vs API (requisito 5) | Usuario |
| P-002 | Mantener atribución CC-BY-4.0 a CodiEsp en entregables | Legal/ética | Agente |
| P-003 | Elegir modelo local inicial (`qwen3:8b` vs descargar `qwen2.5:7b-instruct`) | Calidad/latencia | Usuario + agente |
| P-004 | Fecha límite de entrega | Cronograma | Usuario |
| P-005 | Versionar/entregar los artefactos generados de Fase 2 junto con el código | Reproducibilidad | Agente |
| P-006 | Implementar retrieval, negación, LLM y pipeline | Fase 3 | Cerrado |
| P-007 | Evaluar y comparar proveedores | Fase 4 | Cerrado |
| P-008 | Streamlit, README final y demo | Fase 5 | Cerrado |
| P-009 | Informe y guion de video | Fase 6 | Cerrado |

---

## 6. Fases

| Fase | Estado | Evidencia |
|---|---|---|
| 1. Comprensión del negocio y datos | **Cerrada** | `docs/PLAN.md`, `docs/CRISP-ML.md`, `docs/auditoria_datos.md` |
| 2. Preparación de datos | **Cerrada** | scripts `prepare_*`, catálogo, JSONL, 40 casos, `pytest` 54 passed, `make audit` OK |
| 3. Modelado | **Cerrada** | `src/pipeline/engine.py`, `src/retrieval/hybrid.py`, `src/negation/detector.py`, `src/llm/providers.py` |
| 4. Evaluación | **Cerrada** | `scripts/evaluate_pipeline.py`, `src/eval/metrics.py`, `reports/pipeline_eval.json` |
| 5. Despliegue | **Cerrada** | `app/streamlit_app.py`, `README.md`, `.env.example` |
| 6. Monitoreo y mantenimiento | **Cerrada** | `docs/ESTADO.md`, `docs/registro_modelos.md`, `docs/CRISP-ML.md` |

---

## 7. Cómo retomar tras un cambio de modelo

1. Leer `docs/ESTADO.md` (este archivo) y `docs/PLAN.md`.
2. Revisar `docs/registro_modelos.md` para saber qué modelo hizo qué.
3. Ejecutar `make smoke` y `make test` para confirmar que el entorno sigue sano.
4. Revisar la fase pendiente en `docs/CRISP-ML.md`.
5. No reescribir decisiones sin registrar un nuevo ID en la tabla de decisiones.

---

## 8. Comandos de verificación de las fases 1–2

```bash
make setup          # crea .venv con Python 3.11.17 e instala dependencias
make data           # descarga y verifica CodiEsp
python scripts/prepare_catalog.py
python scripts/prepare_codiesp.py
python scripts/build_fictional_cases.py
make audit          # audita catálogo, corpus y spans
make figures        # genera docs/figuras/*.png
make test           # pytest sin tests de red
make lint           # ruff
make smoke          # verificación mínima
```

---

## 9. Limitaciones conocidas (a documentar en el informe)

- CodiEsp usa ICD-10-CM español 2018, no la CIE-10 OMS.
- El gold de CodiEsp es a nivel documento; la evidencia viene de CodiEsp-X.
- CodiEsp no anota negación; esa evaluación se hace con los 40 ficticios.
- El corpus tiene fuerte desbalance de códigos; macro-F1 será exigente.
- La GPU de 4 GB obliga a cuantización y puede aumentar la latencia local.
- La comparación con API externa depende de una clave y de las condiciones del proveedor.
