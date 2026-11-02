# Catálogo CIE-10

Este directorio contendrá el catálogo procesado que usa el pipeline.

- **Fuente:** `codiesp-D_codes.tsv` de CodiEsp (Zenodo 3706838, CC-BY-4.0).
- **Filas originales:** 98.288.
- **Códigos válidos:** 98.268; se excluyen 20 marcadores de capítulo `CAP.xx`, que no son códigos facturables.
- **Columnas:** `code`, `description_es`, `description_en`.
- **Generación:** `python scripts/prepare_catalog.py` (Fase 2).
- **Verificación:** `python scripts/audit_data.py` y `reports/data_audit.json`.

No se deben editar los códigos a mano. Cualquier transformación debe quedar en un script reproducible.
