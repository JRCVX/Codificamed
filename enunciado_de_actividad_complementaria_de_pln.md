# ESPOCH FIE EIS
## BASE DE CONOCIMIENTO

**Tarea:** CodificaMed - Codificación automática CIE-10 de historias clínicas con PLN  
**Materia:** Base de Conocimiento  
**Unidad:** Procesamiento de Lenguaje Natural  

*(Documento de referencia: "enunciado de actividad complementaria de PLN.pdf")*

---

## 1. Problemática
En la Red Pública Integral de Salud (MSP, IESS) y en las clínicas privadas, cada atención médica se registra con uno o más códigos CIE-10. Esos códigos sirven para la facturación entre prestadores, las estadísticas epidemiológicas y la planificación de recursos.

Hoy la codificación es manual: un codificador lee notas clínicas escritas en texto libre, con abreviaturas ("HTA", "DM2", "dolor abd"), errores de tipeo y negaciones ("niega fiebre", "se descarta neumonía"), y asigna los códigos uno por uno. El proceso es lento y propenso a errores. Un código mal asignado genera glosas (objeciones en el pago), retrasa la facturación y produce estadísticas de morbilidad poco confiables.

## 2. Lo que se busca resolver
Construir un prototipo de aplicación que reciba una nota clínica en texto libre y sugiera los códigos CIE-10 correspondientes, mostrando qué frase de la nota justifica cada código. Así, el codificador humano solo valida en lugar de leer y codificar desde cero. El sistema debe distinguir un diagnóstico confirmado de uno negado o descartado.

## 3. Requisitos
1. Desarrollar el proyecto siguiendo las 6 fases de CRISP-ML(Q) y documentar qué se hizo en cada una.
2. Construir el pipeline de PLN completo: preprocesamiento del texto clínico, representación y modelado.
3. Aplicar al menos una técnica o tecnología de PLN justificada, por ejemplo: RAG con embeddings sobre el catálogo CIE-10, reconocimiento de entidades clínicas (NER), detección de negación o un modelo de lenguaje biomédico en español.
4. La aplicación debe poder ejecutarse con un modelo local (por ejemplo, con Ollama) y con una API externa (Claude, OpenAI u otra), cambiando de uno a otro mediante configuración, y comparar los resultados de ambos.
5. Evaluar el sistema con métricas (precisión, recall, F1) sobre un conjunto de casos con códigos conocidos.
6. Contar con una interfaz donde se ingrese la nota clínica y se vean los códigos sugeridos con su evidencia.

## 4. Datos
Usar el corpus público CodiEsp (casos clínicos en español anotados con CIE-10, CLEF eHealth 2020) o casos clínicos ficticios.

> **⚠️ Importante:** Está prohibido usar historias clínicas reales de pacientes.

## 5. Entregables
1. **Código fuente** de todo el proyecto, en un repositorio o archivo comprimido, con:
   - Un archivo `README` con las instrucciones para instalarlo y ejecutarlo.
   - Un archivo de configuración de ejemplo (`.env.example` o similar), sin claves de API reales.
2. **Informe ejecutivo** de la tarea, que incluya:
   - La problemática y el objetivo.
   - Lo realizado en cada una de las 6 fases de CRISP-ML(Q).
   - La arquitectura de la solución.
   - Los resultados de la evaluación y la comparación entre el modelo local y la API externa.
   - Conclusiones y limitaciones.
3. **Verificación:** Crear un video grabando el escritorio demostrando el funcionamiento del sistema inteligente. 
   - El video no debe exceder los 10 minutos (si el procesamiento se demora demasiado tiempo, cortar parte del video y mostrar los resultados). 
   - En el video se debe observar su rostro en una esquina de la pantalla *(si no se observa su rostro, no se revisa la tarea)*.

Al final, subir el video, código fuente e informe ejecutivo en un repositorio y compartir el link en la tarea asignada en el aula virtual.

---
*Ing. Isaac Torres*