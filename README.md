# CodificaMed

Prototipo académico de **codificación automática CIE-10 de notas clínicas en español** usando PLN, recuperación aumentada por generación (RAG) y detección de negación.

> **Estado:** Fase 1 de CRISP-ML(Q) — planificación, auditoría de datos y esqueleto reproducible. El pipeline funcional, la interfaz y la evaluación se construyen en las fases 2–6.

## Problema

En Ecuador y en muchos sistemas de salud, cada atención clínica se codifica manualmente con CIE-10 a partir de notas en texto libre. Las abreviaturas (`HTA`, `DM2`, `dolor abd`), los errores de tipeo y las negaciones (`niega fiebre`, `se descarta neumonía`) hacen que el proceso sea lento y propenso a errores. Un código mal asignado genera glosas, retrasa la facturación y distorsiona las estadísticas de morbilidad.

## Objetivo

Recibir una nota clínica y sugerir códigos CIE-10, mostrando:

- la **frase de evidencia** que justifica cada código;
- el **estado** del diagnóstico: confirmado, negado, sospechoso, antecedente o familiar;
- los **candidatos recuperados** del catálogo;
- el **proveedor LLM** utilizado (Ollama local o API externa), cambiable por configuración.

El codificador humano valida; el sistema no reemplaza su criterio clínico.

## Decisiones principales

| Componente | Elección |
|---|---|
| Datos | CodiEsp (CLEF eHealth 2020, CC-BY-4.0) + 40 casos ficticios |
| Terminología | ICD-10-CM español 2018 de CodiEsp (diagnósticos) |
| Preproceso | Normalización, abreviaturas, segmentación y tolerancia a typos |
| Representación | `intfloat/multilingual-e5-small` (benchmark con `BAAI/bge-m3`) |
| Recuperación | BM25 + FAISS, fusión RRF |
| Negación | NegEx adaptado al español, por reglas de alcance |
| LLM | Interfaz `LLMProvider`: Ollama, OpenAI-compatible, Anthropic y Mock |
| Interfaz | Streamlit |
| Pruebas | pytest; tests de red marcados y omitidos por defecto |

## Estructura

```text
app/                 Interfaz Streamlit
src/preprocess/      Normalización, abreviaturas, segmentación, typos
src/catalog/         Carga y validación del catálogo CIE-10
src/retrieval/       Embeddings, FAISS, BM25 y recuperación híbrida
src/negation/        Detección de negación y estados clínicos
src/ner/             NER clínico opcional
src/llm/             Interfaz y proveedores LLM
src/pipeline/        Orquestación, evidencia y agregación
src/eval/            Métricas, datasets y reportes
scripts/             Descarga, auditoría, índice, evaluación
tests/               Pruebas unitarias e integración
docs/                CRISP-ML(Q), estado, arquitectura, informe y guion
data/                Catálogo, casos ficticios, datos crudos e índices
```

## Requisitos

- Linux/macOS (probado en Linux)
- Python **3.11** (se instala con `uv`)
- `uv` >= 0.13
- Ollama (para el proveedor local)
- Opcional: clave de una API compatible con OpenAI o de Anthropic

## Instalación

```bash
git clone <URL_DEL_REPOSITORIO>
cd "PLN CodificaMed"

# 1. Crear entorno Python 3.11 e instalar dependencias fijadas
make setup

# 2. Configurar variables de entorno
cp .env.example .env
# editar .env: proveedor, modelo y claves (nunca subir .env)

# 3. Descargar y verificar CodiEsp
make data

# 4. Auditar los datos
make audit

# 5. Ejecutar pruebas
make test
```

> **Nota sobre PyTorch:** el proyecto usa la rueda CPU de PyTorch para evitar
> dependencias CUDA pesadas y problemas de driver. `make setup` ya incluye
> `--index-strategy unsafe-best-match`, necesario porque `requirements.txt`
> declara el índice oficial de PyTorch como índice adicional. Si instalas
> manualmente con `uv`, usa el mismo flag.

## Uso

La interfaz y el pipeline se habilitan en las fases 3–5:

```bash
# Fase 5
make app
```

Mientras tanto, la Fase 1 se verifica con:

```bash
make smoke
make test
make lint
```

## Cambio de proveedor LLM

Toda la lógica está detrás de `src/llm/base.py` (`LLMProvider`). El proveedor se elige **solo** con `.env`:

```bash
# Ollama local
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b

# API compatible con OpenAI (OpenAI, OpenRouter, Groq, vLLM...)
LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Anthropic
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-3-5-haiku-latest

# Sin red, para pruebas y demo determinista
LLM_PROVIDER=mock
```

No hay lógica duplicada por proveedor: todos usan el mismo prompt, el mismo esquema de salida y el mismo validador.

## Datos y ética

- **CodiEsp** es un corpus público, anonimizado y distribuido con licencia **CC-BY-4.0** por el Barcelona Supercomputing Center (BSC). Citación:

  > Miranda-Escalada, A., Gonzalez-Agirre, A., Armengol-Estapé, J., & Krallinger, M. (2020). *Overview of automatic clinical coding: annotations, guidelines, and solutions for non-English clinical cases at CodiEsp track of CLEF eHealth 2020*. CLEF eHealth 2020.

- El catálogo y el corpus se descargan de Zenodo con verificación SHA-256. Los datos crudos no se versionan.
- Los **40 casos ficticios** son inventados para la evaluación de negación, abreviaturas y typos; no corresponden a pacientes reales.
- Este prototipo es académico y **no** debe usarse para facturación, decisiones clínicas ni tratamiento de datos identificables.

## Documentación

- [`docs/CRISP-ML.md`](docs/CRISP-ML.md): las seis fases y su aseguramiento de calidad.
- [`docs/ESTADO.md`](docs/ESTADO.md): decisiones, pendientes y resultados.
- [`docs/registro_modelos.md`](docs/registro_modelos.md): modelo usado por fase y rendimiento.
- [`docs/arquitectura.md`](docs/arquitectura.md): arquitectura y diagrama.
- [`docs/auditoria_datos.md`](docs/auditoria_datos.md): auditoría reproducible de CodiEsp.
- [`docs/PLAN.md`](docs/PLAN.md): plan integral y cronograma.

## Licencia

Código del proyecto: MIT (ver `LICENSE`). Datos de CodiEsp: CC-BY-4.0 (ver `THIRD_PARTY_NOTICES.md`).
