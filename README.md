# CodificaMed

Proyecto académico para la codificación automática de notas clínicas en español con CIE-10, usando procesamiento de lenguaje natural, recuperación híbrida y detección de negación.

## Descripción general

CodificaMed recibe una nota clínica en texto libre y propone códigos CIE-10 con:

- evidencia textual que justifica cada código;
- estado clínico del diagnóstico (confirmado, negado, sospechoso, antecedente o familiar);
- candidatos recuperados desde el catálogo CIE-10;
- soporte para proveedores LLM locales o remotos, con configuración por entorno.

El sistema está pensado como ayuda de decisión para codificadores humanos, no como sustituto de su criterio clínico.

## Requisitos

- Linux o macOS
- Python 3.11
- `uv` instalado
- Ollama funcionando localmente o un servidor remoto con acceso al modelo elegido
- Conexión a internet para descargar datos y dependencias

## Estructura del proyecto

```text
app/                 Interfaz Streamlit
backend/             API FastAPI + servicios
frontend/            Frontend web estático
src/                 Código fuente principal
scripts/             Descargas, preparación de datos e índices
data/                Catálogo, corpus y archivos generados
reports/             Evaluaciones y métricas
tests/               Pruebas automatizadas
docs/                Documentación técnica y metodológica
```

## Instalación

1. Clona el repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
cd "PLN CodificaMed"
```

2. Crea el entorno virtual e instala dependencias:

```bash
make setup
```

Este comando crea `.venv` y ejecuta la instalación desde `requirements-dev.txt` usando Python 3.11.

3. Configura las variables de entorno:

```bash
cp .env.example .env
```

Edita el archivo `.env` y define al menos:

```env
LLM_PROVIDER=ollama
LLM_MODEL=mistral
OLLAMA_BASE_URL=http://localhost:11434
```

También puedes usar OpenAI, OpenRouter, Gemini o Anthropic, según tus credenciales.

4. Descarga y prepara los datos:

```bash
make data
make audit
```

5. Prepara el catálogo y los casos de prueba de ejemplo:

```bash
.venv/bin/python scripts/prepare_catalog.py
.venv/bin/python scripts/prepare_codiesp.py
.venv/bin/python scripts/build_fictional_cases.py
```

6. Genera el índice FAISS para la recuperación:

```bash
make index
```

7. Verifica que el proyecto arranca correctamente:

```bash
make smoke
make test
```

## Ejecutar la aplicación

Este proyecto se ejecuta en el modo API FastAPI + frontend web. La API sirve la interfaz desde la carpeta `frontend/` y queda disponible en:

```text
http://localhost:8010
```

Para arrancarlo:

```bash
make setup
cp .env.example .env
# edita .env con tus credenciales y proveedor LLM
make api
```

Si quieres revisar la API manualmente, usa la URL anterior en el navegador o prueba un endpoint con curl.

## Uso rápido

Puedes probar la lógica del preprocesado desde Python:

```python
from src.preprocess import ClinicalPreprocessor

note = ClinicalPreprocessor().preprocess("Paciente con HTA. Niega fiebre.")
print(note.retrieval_text)
print(note.sentences)
```

También puedes evaluar la recuperación del sistema:

```bash
make retrieval-eval
```

Esto genera resultados en `reports/retrieval_dev.json`.

## Variables de entorno importantes

El archivo `.env` puede incluir configuraciones como:

```env
LLM_PROVIDER=ollama
LLM_MODEL=mistral
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=1200
PORT=8010
HOST=0.0.0.0
OLLAMA_BASE_URL=http://localhost:11434
```

Si usas Ollama local, asegúrate de que el modelo exista. Por ejemplo:

```bash
ollama pull mistral
ollama serve
```

## Comandos útiles

```bash
make help
make setup
make data
make audit
make index
make test
make lint
make smoke
make api
make clean
```

## Verificación y pruebas

Se recomienda ejecutar:

```bash
make smoke
make test
make lint
```

## Documentación adicional

- `docs/CRISP-ML.md`
- `docs/ESTADO.md`
- `docs/arquitectura.md`
- `docs/auditoria_datos.md`
- `docs/registro_modelos.md`

## Licencia

- Código: MIT
- Datos de CodiEsp: CC-BY-4.0

## Nota importante

Este prototipo es académico y debe usarse solo para investigación y validación. No debe emplearse para facturación ni decisiones clínicas definitivas sin supervisión humana.

