# Auditoría de datos — CodiEsp

Generado: 2026-11-02T17:22:31.571277+00:00

Fuentes: catálogo CIE-10-D (Zenodo 3706838) y corpus gold (Zenodo 3837305), licencia CC-BY-4.0.

## Veredicto

**OK**

El catálogo y el corpus son consistentes: todos los códigos gold existen en el catálogo y todos los spans de CodiEsp-X son no vacíos y reconstruyen la referencia anotada.

Advertencias:
- Se excluyeron 20 marcadores de capítulo (CAP.xx) del catálogo de códigos
- train: 2 span(s) de longitud cero en CodiEsp-X; se excluirán de la evaluación de evidencia
- dev: 1 span(s) de longitud cero en CodiEsp-X; se excluirán de la evaluación de evidencia

## Catálogo

| Métrica | Valor |
|---|---:|
| Filas | 98288 |
| Códigos válidos únicos | 98268 |
| Marcadores de capítulo excluidos | 20 |
| Duplicados | 0 |
| Descripciones vacías | 0 |
| Códigos con formato inválido | 0 |

## Corpus por split

| Split | Documentos | Anotaciones | Códigos únicos | Promedio/nota | Pares X/D | Spans no vacíos | Referencias reconstruidas | Spans vacíos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 500 | 5639 | 1767 | 11.28 | 5639/5639 | 8305/8307 | 7207/7209 | 2 |
| dev | 250 | 2677 | 1158 | 10.71 | 2677/2677 | 3960/3961 | 3430/3431 | 1 |
| test | 250 | 2842 | 1143 | 11.37 | 2842/2842 | 4203/4203 | 3665/3665 | 0 |

## Totales

| Métrica | Valor |
|---|---:|
| Documentos | 1000 |
| Anotaciones de diagnóstico | 11158 |
| Códigos únicos del corpus | 2557 |
| Códigos válidos del catálogo | 98268 |
| Códigos ausentes del catálogo | 0 |

## Verificaciones de calidad

- Los códigos se normalizan a mayúsculas antes de comparar.
- Se valida el formato ICD-10-CM, que admite una letra en la tercera posición (C4A, C7A, D3A).
- Se excluyen los 20 marcadores de capítulo `CAP.xx`, que no son códigos facturables.
- Se comprueba que cada par diagnóstico de CodiEsp-D tenga su fila en CodiEsp-X.
- Se comprueba que cada span sea no vacío y esté dentro del texto; los 3 spans de longitud cero detectados se excluirán de la evaluación de evidencia.
- Se comprueba que la concatenación normalizada de los spans reconstruya la referencia; CodiEsp-X puede dividir una referencia multi-palabra en varios spans.
- Se comprueba que exista el archivo de texto de cada documento anotado.

El detalle completo está en `reports/data_audit.json`.
