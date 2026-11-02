# Registro de modelos

> Qué modelo de OpenCode se usó en cada fase, para qué, cómo rindió y por qué se cambió (o no).

- **Proyecto:** CodificaMed
- **Protocolo:** antes de cada fase se solicita/decide el modelo; al cerrar se registra el resultado.
- **Fecha de inicio:** 2026-11-02

## Registro

| Fecha | Fase | Modelo | Tarea | Resultado / rendimiento | Decisión |
|---|---|---|---|---|---|
| 2026-11-02 | 1 | DeepSeek V4.1 Flash Free | Plan integral, arquitectura, auditoría de CodiEsp, scaffold, configuración, scripts y documentación | Buen contexto y razonamiento; ejecutó la descarga, detectó 20 marcadores CAP y 3 spans vacíos, corrigió la auditoría y dejó 12 tests verdes + ruff limpio; sin repeticiones ni pérdida de contexto | Fase 1 cerrada; para F2 se recomienda un modelo fuerte en código |
| 2026-11-02 | 2 | *(pendiente)* | Preparación de datos y preproceso | — | — |
| — | 3 | *(pendiente)* | Retrieval, negación, proveedores y pipeline | — | — |
| — | 4 | *(pendiente)* | Evaluación y revisión crítica | — | — |
| — | 5 | *(pendiente)* | UI, README y demo | — | — |
| — | 6 | *(pendiente)* | Informe, video y QA | — | — |

## Asignación prevista

| Fase | Modelo recomendado | Alternativa | Motivo |
|---|---|---|---|
| 1 | DeepSeek V4.1 Flash Free | GLM-5.3-Flash Free | Planificación, arquitectura, contexto largo |
| 2 | GLM-5.3-Flash Free | MiMo-V2.6-Flash Free | Datos, parsing, módulos de preproceso, tests |
| 3 | GLM-5.3-Flash Free | MiMo-V2.6-Flash Free | Código de retrieval, negación, LLM y pipeline |
| 4 | Flint 40B Free | DeepSeek V4.1 Flash Free | Revisión crítica y métricas con un modelo distinto al autor |
| 5 | GLM-5.3-Flash Free | DeepSeek V4.1 Flash Free | UI y redacción en español |
| 6 | DeepSeek V4.1 / GLM-5.3 | Nemotron 3.5 Lightning Free | Informe y guion; tareas mecánicas con un modelo rápido |

## Criterios para pedir cambio

Se solicitará cambio de modelo si ocurre cualquiera de estos síntomas:

- repetición de texto o bucles;
- alucinación de códigos, archivos o resultados;
- errores de sintaxis repetidos o ruptura de archivos;
- pérdida de contexto entre fases;
- lentitud excesiva para la tarea;
- incapacidad de ejecutar y verificar comandos.

## Cómo se evalúa el rendimiento del modelo

- **Corrección:** ¿el código corre y los tests pasan?
- **Fidelidad:** ¿respeta las decisiones y el alcance?
- **Contexto:** ¿recuerda `ESTADO.md` y no reescribe lo aprobado?
- **Verificación:** ¿ejecuta comandos y reporta resultados reales?
- **Redacción:** ¿el español es claro y sin relleno?
- **Eficiencia:** tiempo hasta entregar la fase.

## Contexto mínimo para un nuevo modelo

1. Leer `docs/ESTADO.md`.
2. Leer `docs/PLAN.md`.
3. Leer la fase correspondiente en `docs/CRISP-ML.md`.
4. Ejecutar `make smoke` y `make test`.
5. No cambiar decisiones sin registrar un ID nuevo.
