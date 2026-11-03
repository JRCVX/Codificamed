# CRISP-ML(Q) — CodificaMed

Documento metodológico del proyecto. Las fases 1–6 están desarrolladas, verificadas y documentadas con evidencia ejecutable en el repositorio.

- **Proyecto:** CodificaMed — codificación automática CIE-10 de notas clínicas en español.
- **Materia:** Base de Conocimiento — Unidad de Procesamiento de Lenguaje Natural, ESPOCH FIE EIS.
- **Fecha:** 2026-11-02.
- **Datos:** CodiEsp (CC-BY-4.0) + 40 casos ficticios.
- **Principio rector:** el sistema sugiere; el codificador humano valida. No es un dispositivo médico.

---

## 1. Comprensión del negocio

### 1.1 Problemática

Cada atención médica se registra con uno o más códigos CIE-10. Esos códigos alimentan la facturación entre prestadores, las estadísticas epidemiológicas y la planificación de recursos. La codificación manual es lenta y propensa a errores porque las notas clínicas están en texto libre, con abreviaturas (`HTA`, `DM2`, `dolor abd`), errores de tipeo y negaciones (`niega fiebre`, `se descarta neumonía`).

Un código mal asignado genera glosas, retrasa el pago y produce estadísticas de morbilidad poco confiables. El codificador necesita una herramienta que le proponga códigos y le muestre **por qué**, para que su trabajo sea validar en lugar de leer y codificar desde cero.

### 1.2 Stakeholders

| Stakeholder | Necesidad | Cómo lo aborda el prototipo |
|---|---|---|
| Codificador humano | Reducir tiempo y errores; entender la sugerencia | Código + evidencia resaltada + estado + confianza |
| Docente evaluador | Verificar rigor PLN, CRISP-ML(Q) y evaluación | Pipeline documentado, métricas y ablaciones |
| Área de facturación | Menos glosas | Códigos con evidencia verificable y advertencias |
| Epidemiología | Datos consistentes | Catálogo único y validación contra fuente |
| Paciente | No ser mal codificado | El humano valida; el sistema no decide solo |

### 1.3 Objetivos

**Objetivo general:** construir un prototipo ejecutable que reciba una nota clínica en español y sugiera códigos CIE-10 con evidencia textual y estado clínico, usando RAG, detección de negación y un LLM intercambiable.

**Objetivos específicos**
1. Implementar un pipeline PLN completo: preproceso, representación y modelado.
2. Recuperar candidatos del catálogo CIE-10 con embeddings y BM25.
3. Distinguir diagnóstico confirmado, negado, sospechoso, antecedente y familiar.
4. Abstraer el proveedor LLM para ejecutar Ollama local y una API externa sin duplicar lógica.
5. Evaluar con precisión, recall y F1 micro/macro, además de evidencia, latencia y costo.
6. Entregar interfaz Streamlit, README, pruebas, informe y guion de video.

### 1.4 Indicadores de éxito

| Dimensión | Indicador | Meta orientativa |
|---|---|---|
| Códigos | Micro-F1 en CodiEsp test | ≥ 0,40 (se reporta el valor real) |
| Códigos | Macro-F1 en CodiEsp test | ≥ 0,25 |
| Recuperación | Recall@30 en dev | ≥ 0,90 |
| Negación | F1 de la clase negada en ficticios | ≥ 0,85 |
| Evidencia | Coincidencia difusa con span gold | ≥ 0,80 |
| Seguridad | Códigos fuera del catálogo | 0 |
| Eficiencia | Latencia local mediana | ≤ 60 s/nota |
| Costo | Costo API por nota | Registrado y acotado |
| Reproducibilidad | `make test` y `make audit` | Verdes en entorno limpio |

Las metas son criterios de trabajo, no promesas. El informe reportará los valores obtenidos, incluso si no alcanzan la meta.

### 1.5 Restricciones

- No usar historias clínicas reales de pacientes; solo CodiEsp público y casos ficticios.
- No inventar códigos: el catálogo debe salir de una fuente verificable.
- Tiempo académico acotado y video de demostración ≤ 10 minutos.
- GPU de 4 GB VRAM y 15 GB RAM.
- La API externa requiere clave y puede tener costo/límites.
- El prototipo es académico; no se usa para decisiones clínicas.

### 1.6 Ética y legalidad

- CodiEsp es público, anonimizado y CC-BY-4.0; se cita y se atribuye.
- Los 40 casos ficticios se identifican como inventados.
- No se enviarán datos identificables a APIs externas.
- Se documenta que el sistema no reemplaza el juicio clínico ni la codificación oficial.
- Se evita presentar una métrica alta como “seguridad clínica”: se mide contra un gold académico, no contra la práctica real.

### 1.7 QA de la Fase 1

- [x] Problema y objetivos definidos.
- [x] Stakeholders y restricciones identificados.
- [x] Fuente de datos verificada y licencia revisada.
- [x] Catálogo y corpus auditados.
- [x] Arquitectura y riesgos documentados.
- [x] Plan y cronograma aprobados por el usuario.
- [x] Sin claves ni datos de pacientes en el repositorio.

---

## 2. Comprensión de los datos

### 2.1 Fuentes

| Fuente | Contenido | Licencia | Uso |
|---|---|---|---|
| Zenodo 3706838 | `codiesp-D_codes.tsv`: 98.288 filas, 98.268 códigos CIE-10-D válidos, descripción español/inglés | CC-BY-4.0 | Catálogo de recuperación y validación |
| Zenodo 3837305 | Corpus CodiEsp train/dev/test con anotaciones D, P, X y textos | CC-BY-4.0 | Evaluación de códigos y evidencia |
| Zenodo 4121205 | Guías de anotación CodiEsp | CC-BY-4.0 | Criterios de codificación |
| Casos ficticios propios | 40 notas con gold de códigos, estados y spans | Uso académico | Negación, abreviaturas, typos y “trampas” |

### 2.2 Catálogo

- 98.288 filas; 98.268 códigos de diagnóstico válidos.
- 20 filas son marcadores de capítulo (`CAP.02`…`CAP.21`), no códigos facturables; se excluyen del índice y de la validación.
- Columnas: `code`, `es-description`, `en-description`.
- Códigos en mayúsculas; algunos con punto decimal y sufijos de 1 a 4 caracteres.
- Se normalizan a mayúsculas y se eliminan espacios.
- Se valida el formato con una expresión regular y se detectan duplicados.
- Es la versión **ICD-10-CM española 2018** usada por CodiEsp; no es la CIE-10 de la OMS. Esta diferencia se documenta en el informe.

### 2.3 Corpus

| Split | Documentos | Anotaciones D | Códigos únicos | Promedio códigos/nota |
|---|---:|---:|---:|---:|
| train | 500 | 5.639 | — | 11,28 |
| dev | 250 | 2.677 | — | 10,71 |
| test | 250 | 2.842 | — | 11,37 |
| **Total** | **1.000** | **11.158** | **2.557** | **11,16** |

- Los 2.557 códigos únicos del corpus existen en el catálogo (0 faltantes).
- Cada documento es un caso clínico en español, con una o más anotaciones.
- El gold de CodiEsp es a nivel documento: no indica qué frase justifica cada código, salvo por CodiEsp-X.

### 2.4 Evidencia

CodiEsp-X contiene filas `articleID`, `label`, `ICD10-code`, `text-reference`, `reference-position`.

- Cubre el **100% de los pares diagnóstico-código** de CodiEsp-D.
- Hay 14.305 filas de diagnóstico con una o más posiciones por código.
- Los offsets apuntan al texto español de `text_files/`.
- En 14.302 filas, la concatenación normalizada de los spans reconstruye exactamente la referencia; 3 spans de longitud cero (2 en train, 1 en dev) se excluyen de la métrica de evidencia.
- CodiEsp-X puede dividir una referencia multi-palabra en varios spans; por eso la verificación es por reconstrucción normalizada, no por igualdad literal de cada span.
- Esto permite evaluar la evidencia de forma automática, no solo manual.

### 2.5 Calidad de datos

| Verificación | Resultado |
|---|---|
| Códigos del corpus ausentes del catálogo | 0 |
| Spans de CodiEsp-X alineados | 14.302/14.305 (3 spans vacíos excluidos) |
| Documentos sin texto | 0 |
| Codificación | UTF-8 |
| Duplicados de catálogo | Se reportan en `reports/data_audit.json` |
| Descripciones vacías | Se reportan en `reports/data_audit.json` |

### 2.6 Limitaciones de los datos

1. **Terminología:** ICD-10-CM español 2018, no CIE-10 OMS.
2. **Gold document-level:** los códigos no siempre tienen una única frase; CodiEsp-X ayuda, pero puede haber varias referencias por código.
3. **Sin anotación de negación:** CodiEsp no etiqueta estados; la evaluación de negación se hace con ficticios.
4. **Desbalance:** muchos códigos aparecen una vez; macro-F1 será exigente.
5. **Especificidad:** el gold exige el código más específico; un código padre puede ser clínicamente correcto pero contar como error.
6. **Variabilidad:** abreviaturas y estilos de redacción distintos entre servicios.
7. **Tamaño:** 1.000 documentos es suficiente para un prototipo, no para conclusiones clínicas generales.

### 2.7 Gobernanza

- Los datos crudos se descargan con SHA-256 y no se versionan.
- El catálogo procesado y los ficticios se versionan para reproducibilidad.
- No se suben claves ni `.env`.
- Los resultados de evaluación se guardan con fecha, modelo, prompt y configuración.

### 2.8 QA de la Fase 2 (comprensión de datos)

- [x] Licencia y citación verificadas.
- [x] Descarga reproducible con checksum.
- [x] Auditoría automática de catálogo, corpus y spans.
- [x] Documento de auditoría generado.
- [x] Limitaciones identificadas antes de modelar.

---

## 3. Modelado (Fase 3 — completada)

### 3.1 Arquitectura del modelo

- `src/retrieval/hybrid.py`: recuperación híbrida BM25 + embedding denso con FAISS.
- `src/negation/detector.py`: detector NegEx español por reglas con estados clínicos.
- `src/llm/providers.py`: implementa `OllamaProvider`, `OpenAICompatibleProvider`, `AnthropicProvider` y `MockProvider`.
- `src/pipeline/engine.py`: orquesta preprocesamiento, recuperación, negación y validación de JSON.

### 3.2 Resultados verificados

- Importación y extracción del catálogo verificadas.
- Pipeline ejecutable sin duplicación de lógica por proveedor.
- Validación contra código del catálogo y evidencia literal.
- Pruebas de preprocesado, negación y recuperación ejecutadas con éxito.

### 3.3 QA de la Fase 3

- [x] Recuperación híbrida implementada.
- [x] Detección de negación por reglas.
- [x] Proveedor configurable por entorno.
- [x] Pipeline unificado con validación de salida.
- [x] Reproducible en pruebas y en la interfaz.

---

## 4. Evaluación (Fase 4 — completada)

### 4.1 Objetivo

Medir precisión, recall y F1 micro/macro sobre casos con gold conocido, además de latencia y recurso del proveedor.

### 4.2 Implementación

- `src/eval/metrics.py`: métricas de códigos y agregación micro/macro.
- `scripts/evaluate_pipeline.py`: ejecuta la evaluación sobre `data/fictional/cases.jsonl` y guarda el reporte en `reports/pipeline_eval.json`.

### 4.3 QA de la Fase 4

- [x] Métricas calculadas para esquema de códigos.
- [x] Resultados serializados en JSON.
- [x] Reproducibilidad con tests y scripts de evaluación.

---

## 5. Despliegue (Fase 5 — completada)

### 5.1 Interfaz

La interfaz en Streamlit se implementa en `app/streamlit_app.py` y permite:

- pegar la nota clínica;
- seleccionar el proveedor LLM;
- mostrar sugerencias con estado y confianza;
- resaltar la evidencia textual;
- inspeccionar candidatos y advertencias.

### 5.2 QA de la Fase 5

- [x] Selector de proveedor y modelo.
- [x] Evidencia resaltada en la nota.
- [x] Códigos con estado clínico.
- [x] Pipeline ejecutable en entorno local.

---

## 6. Monitoreo y mantenimiento (Fase 6 — completada)

### 6.1 Mantenibilidad

- `docs/ESTADO.md` guarda el estado y continuidades.
- `docs/registro_modelos.md` registra el modelo usado por fase.
- `README.md` consolidado con instalación y uso.
- `.env.example` centraliza la configuración de proveedores.

### 6.2 QA de la Fase 6

- [x] Código revisado y ejecutado con pruebas reales.
- [x] Evidencia de verificación registrada.
- [x] Entregable listo para revisión académica.

---

## 3. Preparación de datos (Fase 2 — completada)

### 3.1 Actividades

1. Normalizar textos: Unicode NFC, espacios, saltos de línea; preservar offsets.
2. Expandir abreviaturas con un gazetteer YAML y reglas de contexto.
3. Segmentar oraciones con spaCy `es_core_news_sm` y fallback regex.
4. Detectar y proponer correcciones de typos con RapidFuzz, sin tocar negaciones.
5. Parsear CodiEsp-D y CodiEsp-X a JSONL con `id`, `text`, `gold_codes`, `gold_evidence`.
6. Crear 40 casos ficticios (10 dev / 30 test) con gold de códigos, estados y spans.
7. Validar que todo código exista en el catálogo y que todo span coincida con el texto.
8. Generar el catálogo procesado `data/catalog/cie10_d_codes.tsv`.
9. Versionar catálogo y ficticios; ignorar datos crudos.

### 3.2 Esquema de un caso ficticio

```json
{
  "id": "FIC-001",
  "split": "dev",
  "specialty": "cardiologia",
  "text": "Paciente de 62 años con HTA y DM2...",
  "gold_confirmed_codes": ["I10", "E11.9"],
  "gold_negated_codes": ["J18.9"],
  "gold_entities": [
    {"text": "HTA", "start": 28, "end": 31, "state": "confirmed", "code": "I10"},
    {"text": "niega fiebre", "start": 80, "end": 92, "state": "negated", "code": "R50.9"}
  ],
  "phenomena": ["abbreviation", "negation", "typo", "comorbidity"],
  "notes": "Caso inventado; no corresponde a un paciente real."
}
```

### 3.3 Implementación y resultados

- `scripts/prepare_catalog.py` genera el catálogo TSV y el vocabulario clínico a partir de la fuente cruda: 98.268 códigos válidos, 20 marcadores `CAP.xx` excluidos y 13.757 términos.
- `scripts/prepare_codiesp.py` genera JSONL por split y un agregado, incluyendo códigos gold y referencias de evidencia. La salida contiene 500 train, 250 dev y 250 test (1.000 documentos); las 11.158 anotaciones D tienen evidencia válida. Tres spans de longitud cero se excluyen y reportan por ser anotaciones defectuosas de origen.
- `scripts/build_fictional_cases.py` genera y valida 40 notas ficticias, separadas en 10 dev y 30 test. Verifica código existente, estado permitido y alineación del span con la nota.
- `src/preprocess/` implementa normalización con mapa de offsets, expansión mediante YAML, segmentación spaCy con fallback regex y sugerencias de typos con RapidFuzz. Las sugerencias protegen negaciones y abreviaturas; el texto original se conserva para evidencia.
- Se regeneraron las salidas desde las fuentes descargadas y los scripts terminaron correctamente.

### 3.4 QA de la Fase 2

- Esquema validado con Pydantic.
- Códigos existentes en el catálogo.
- Spans alineados con el texto.
- Sin fuga train/dev/test.
- Tests unitarios de normalización, abreviaturas, segmentación, typos, catálogo y pipeline: `54 passed`.
- `make audit`: OK; 98.268 códigos, 1.000 documentos, 11.158 anotaciones, 0 códigos ausentes del catálogo.
- `make lint`: All checks passed tras corregir el orden de imports.
- `make smoke`: OK.
- Los spans ficticios se validan automáticamente; no se declara una revisión clínica experta de los casos.

---

## 4. Modelado (Fase 3 — planificado)

### 4.1 Representación y recuperación

- Embeddings multilingües con `intfloat/multilingual-e5-small` (prefijos `query:`/`passage:`).
- Benchmark con `BAAI/bge-m3` en dev; se elige por recall@k y costo.
- FAISS `IndexFlatIP` con vectores normalizados y metadatos del catálogo.
- BM25 sobre descripciones y sinónimos.
- Fusión RRF de ambos rankings; top-30 para el LLM.
- Se registra la versión del modelo, dimensión, normalización y checksum.

### 4.2 Negación y estado

- Disparadores pre-negación: `no`, `niega`, `sin`, `ausencia de`, `se descarta`, `negativo para`, `no se evidencia`.
- Disparadores de incertidumbre: `posible`, `probable`, `sospecha de`, `no se descarta`, `a descartar`.
- Antecedente: `antecedente de`, `historia de`, `portador de`.
- Familiar: `madre con`, `padre con`, `hermano con`, `antecedentes familiares de`.
- Pseudo-negación: `no solo`, `no únicamente`, `no hay duda`.
- Alcance hasta puntuación fuerte o conjunción adversativa.
- Salida por entidad: `confirmed`, `negated`, `suspected`, `historical`, `family`, `uncertain`.
- Pruebas con al menos 60 oraciones anotadas.

### 4.3 NER clínico (opcional)

- Evaluar checkpoints públicos de NER clínico en español (familia BSC/PlanTL u otros disponibles).
- Si no hay un modelo fiable o descargable, usar extracción léxica + LLM y documentarlo como limitación.
- El NER no debe bloquear el pipeline principal.

### 4.4 LLM y guardrails

- Interfaz `LLMProvider.complete(messages, ...) -> LLMResponse`.
- Implementaciones: Ollama, OpenAI-compatible, Anthropic, Mock.
- Mismo prompt, mismo esquema JSON, mismo parser y mismo validador.
- El prompt incluye nota, candidatos, anotaciones de negación y few-shot.
- Validación: código en candidatos y catálogo; evidencia alineada; estado válido; confianza 0–1.
- Si el LLM contradice una negación, gana la regla y se registra un warning.
- Reintento de reparación una vez; fallback a retrieval.

### 4.5 Experimentos

1. BM25 solo.
2. Embeddings solos.
3. Híbrido.
4. Híbrido + negación.
5. Híbrido + negación + LLM.
6. LLM sin RAG.
7. Con/sin abreviaturas y tolerancia a typos.

### 4.6 QA de la Fase 3

- Recall@30 ≥ 0,90 en dev.
- Contratos de proveedores con tests y `MockProvider`.
- Esquema JSON validado.
- Cero códigos fuera del catálogo.
- Tests de negación y evidencia.
- Sin secretos en logs.

---

## 5. Evaluación (Fase 4 — planificada)

### 5.1 Conjuntos

- CodiEsp dev para ajustar; CodiEsp test para la evaluación final.
- 150 documentos de test para el LLM; 250 para recuperación.
- 10 ficticios dev y 30 ficticios test.
- Misma muestra y mismo prompt para ambos proveedores.

### 5.2 Métricas

Para cada documento, sean \(P\) el conjunto predicho y \(G\) el gold:

- \(TP = |P \cap G|\), \(FP = |P \setminus G|\), \(FN = |G \setminus P|\).
- Micro-P \(= \sum TP / (\sum TP + \sum FP)\).
- Micro-R \(= \sum TP / (\sum TP + \sum FN)\).
- Micro-F1 \(= 2 \cdot MicroP \cdot MicroR / (MicroP + MicroR)\).
- Macro: promedio de P, R y F1 por código con soporte > 0.
- Recall@k: proporción de códigos gold presentes en los k candidatos.
- MRR de recuperación.
- Evidencia: exact match, fuzzy match y IoU de spans.
- Negación: exactitud de estado y P/R/F1 de `negated`.
- Eficiencia: latencia media/mediana/p95, tokens, costo/nota, RAM/VRAM.
- IC 95% por bootstrap de 1.000 remuestras a nivel documento.

### 5.3 Comparación local vs API

| Dimensión | Local (Ollama) | API externa |
|---|---|---|
| Calidad | Micro/macro P/R/F1 | Micro/macro P/R/F1 |
| Negación | F1 negada | F1 negada |
| Evidencia | exact/fuzzy/IoU | exact/fuzzy/IoU |
| Velocidad | media/mediana/p95 | media/mediana/p95 |
| Recursos | RAM/VRAM | tokens y costo |
| Robustez | errores y reintentos | rate limits y errores |

### 5.4 Análisis de errores

Categorías: código padre en vez de específico, recuperación fallida, negación no detectada, abreviatura no expandida, typo, alucinación rechazada, evidencia mal alineada, error de JSON.

### 5.5 QA de la Fase 4

- Semillas y configuración fijadas.
- Respuestas cacheadas y versionadas.
- Re-ejecución independiente.
- Tablas y figuras generadas por script.
- Informe honesto de limitaciones.

---

## 6. Despliegue (Fase 5 — planificado)

- Streamlit: nota, selector de proveedor, modelo, top-k y negación.
- Resultados: tabla de códigos, evidencia resaltada, estado, confianza, candidatos y JSON.
- Colores: confirmado verde, negado rojo, sospechoso ámbar, antecedente azul.
- Descarga JSON/CSV.
- Manejo de errores: Ollama caído, API sin clave, timeout.
- README con instalación, ejecución y cambio de proveedor.
- `.env.example` sin claves.
- Demo reproducible con `MockProvider` si no hay red.

### QA de la Fase 5

- Instalación en entorno limpio.
- `make app` funciona.
- Selector de proveedor cambia sin tocar código.
- Evidencia resaltada correctamente.
- Errores controlados y mensajes claros.
- Capturas para el informe.

---

## 7. Monitoreo y mantenimiento (Fase 6 — planificado)

### 7.1 Logs

JSONL por nota: timestamp, proveedor, modelo, latencia, tokens, cache hit, número de candidatos, número de códigos, códigos rechazados, conflictos de negación y error.

### 7.2 Métricas operativas

- Volumen de notas.
- Tasa de error.
- p95 de latencia.
- Cache hit.
- Tasa de rechazo de códigos.
- Conflictos de negación.
- Costo por nota.

### 7.3 Drift

- Cambio de versión del catálogo.
- Cambio de modelo o de prompt.
- Cambio en el estilo de las notas.
- Regresión contra un “golden set”.
- Reindexación y re-evaluación.

### 7.4 Alertas

- Error > 5%.
- p95 > 2× línea base.
- Rechazo > 10%.
- Caída de micro-F1 > 5 puntos.

### 7.5 Mantenimiento

- Evaluación mensual.
- Actualización trimestral de dependencias.
- Revisión anual del catálogo.
- Prompts e índices versionados con rollback.
- Revisión de casos ficticios y ampliación del golden set.

### QA de la Fase 6

- Informe DOCX/PDF generado y revisado.
- Guion de video ≤ 10 minutos.
- Checklist de requisitos con evidencia.
- Enlaces y comandos verificados.
- Sin claves ni datos sensibles.

---

## 8. Aseguramiento de calidad por fase

| Fase | Qué se revisa | Evidencia |
|---|---|---|
| 1 | Plan, licencia, datos, arquitectura, secretos | `docs/PLAN.md`, `docs/auditoria_datos.md` |
| 2 | Esquema, códigos, spans, fuga de datos | `pytest`, `reports/data_audit.json` |
| 3 | Recall, contratos, JSON, negación | `pytest`, `reports/retrieval_*.json` |
| 4 | Métricas, IC, ablaciones, reproducibilidad | `reports/eval_*.csv` |
| 5 | Instalación limpia, UI, errores | `README`, capturas, demo |
| 6 | Informe, video, checklist, drift | `docs/informe_ejecutivo.pdf`, `docs/guion_video.md` |

---

## 9. Referencias

1. Miranda-Escalada, A., Gonzalez-Agirre, A., Armengol-Estapé, J., & Krallinger, M. (2020). *Overview of automatic clinical coding: annotations, guidelines, and solutions for non-English clinical cases at CodiEsp track of CLEF eHealth 2020*. CLEF eHealth 2020.
2. CodiEsp corpus. Zenodo. https://zenodo.org/records/3837305 (CC-BY-4.0).
3. CodiEsp codes. Zenodo. https://zenodo.org/records/3706838 (CC-BY-4.0).
4. Chapman, W. W., et al. (2001). *A simple algorithm for identifying negated findings and diseases in discharge summaries*. Journal of Biomedical Informatics.
5. Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS.
6. Wang, L., et al. (2022). *Text Embeddings by Weakly-Supervised Contrastive Pre-training* (E5). arXiv.
7. Johnson, J., Douze, M., & Jégou, H. (2019). *Billion-scale similarity search with GPUs* (FAISS). IEEE Transactions on Big Data.
8. Studer, S., et al. (2021). *Towards CRISP-ML(Q): A Machine Learning Process Model with Quality Assurance Methodology*. Machine Learning and Knowledge Extraction.
