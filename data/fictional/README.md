# Casos ficticios

En la Fase 2 se crearán **40 casos clínicos ficticios** (10 dev / 30 test) para evaluar:

- negación y estados (`confirmed`, `negated`, `suspected`, `historical`, `family`);
- abreviaturas (`HTA`, `DM2`, `dolor abd`, `EPOC`...);
- errores de tipeo deliberados;
- comorbilidades y polifarmacia;
- evidencia textual con offsets.

Cada caso tendrá un gold con `gold_confirmed_codes`, `gold_negated_codes` y `gold_entities`. Todo código se validará contra el catálogo y todo span contra el texto.

**Ética:** estos casos son inventados. No corresponden a pacientes reales ni contienen datos identificables.
