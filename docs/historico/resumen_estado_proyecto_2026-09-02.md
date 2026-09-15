# Resumen de Avances y Fases Restantes

Este documento detalla el trabajo consolidado en los primeros capítulos de la tesis y estructura las fases técnicas y de redacción pendientes para la finalización del proyecto.

## 1. Resumen de Tareas Completadas

Durante los últimos ciclos de trabajo, se completaron revisiones profundas y se formalizaron nuevas secciones, elevando el rigor académico de los primeros cinco capítulos (Introducción, Definición del Problema, Marco Conceptual, Trabajo Relacionado y Propuesta de Solución).

Los avances principales incluyen:

* **Formalización de la Propuesta de Solución (Capítulo 4):**
  Se redactó íntegramente la propuesta metodológica, detallando el flujo de doble modelo (Modelo 1: Zona 777 control vs. Modelo 2: Grilla Hexagonal H3). Se definió la extracción de características en 12 macro-categorías OSM, la arquitectura del vector de 27 dimensiones y se fundamentó formalmente la arquitectura en las teorías de Logit Multinomial, maximización de entropía y el Teorema de Aproximación Universal.

* **Fortalecimiento del caso de estudio (Contexto Latinoamericano):**
  Se amplió la justificación sobre la necesidad de evaluar el modelo en Santiago de Chile. Se integraron referencias empíricas recientes y de alto impacto para fundamentar la segregación socio-espacial (Vecchio et al., 2020; Marín-Flores et al., 2026), los sesgos en la completitud de datos geoespaciales (Herfort et al., 2023) y la falta de aplicaciones de aprendizaje profundo para flujos de movilidad en la región (Spadon et al., 2019).

* **Precisión teórica y técnica:**
  Se estableció una diferenciación explícita entre las variables empleadas por *TS-Mob* y *Deep Gravity*. Se clarificó la conceptualización de los modelos doblemente restringidos y se actualizó el Objetivo Específico 2 para reflejar la decisión arquitectónica (ADR-004) de emplear la grilla H3.

* **Estructuración de la Validación (Capítulo 5):**
  Se estableció el esqueleto y lineamientos del protocolo experimental directamente en el archivo `.tex` mediante comentarios, incluyendo las métricas a usar (CPC) sustentadas en bibliografía (Lenormand et al.) y el diseño del análisis SHAP comparativo, listos para recibir resultados.

* **Mejoras de formato LaTeX y estructuración:**
  Se implementó el paquete `booktabs` en tablas. Se corrigió el flujo solucionando saltos de página conflictivos y se unificó terminología en todo el texto.

* **Depuración y Ampliación de la bibliografía:**
  Se eliminó el contenido residual de la plantilla original y la bibliografía se amplió a 41 referencias fundamentales, incluyendo 10 entradas nuevas para sustentar la propuesta metodológica (ej. Munizaga & Palma, Espinoza et al., McFadden, Wilson, Brodsky).

---

## 2. Fases Restantes del Proyecto

Con el marco teórico, la definición del problema y la propuesta de solución consolidados (5/6 capítulos en estado maduro), el proyecto entra plenamente en la etapa experimental. Las siguientes fases detallan el trabajo técnico pendiente:

### Fase 3: Obtención y Procesamiento de Datos (Santiago)
Esta fase aborda la construcción del conjunto de datos de entrenamiento y evaluación.
* **Integración de datos DTPM:** Procesamiento de los registros masivos de etapas y viajes (noviembre 2024) para la construcción de la matriz Origen-Destino empírica.
* **Generación de la grilla espacial:** Construcción de la grilla H3 (resoluciones 3-8) y delimitación del Gran Santiago, junto con las zonas 777 de control.
* **Extracción de variables territoriales:** Descarga y procesamiento de los puntos de interés (*amenities*) desde OpenStreetMap en 12 macro-categorías funcionales.
* **Adaptación del pipeline:** Refactorización del módulo de carga de datos (`data_loader.py`) para procesar las dos unidades espaciales (H3 y Zonal).

### Fase 4: Adaptación y Entrenamiento del Modelo
Fase centrada en la ejecución computacional de la arquitectura neuronal.
* **Resolución de errores de código:** Corrección de problemas de serialización (`utils.py:106`) e importación (`main.py`) detectados durante la auditoría.
* **Entrenamiento local:** Ejecución del modelo *Deep Gravity* utilizando los datos procesados de Santiago y probando las resoluciones espaciales.

### Fase 5: Evaluación Comparativa y Explicabilidad (XAI)
Fase de análisis de resultados e interpretación.
* **Métricas de desempeño:** Comparación de la capacidad predictiva (evaluada mediante CPC) de *Deep Gravity* Modelo H3 frente al Modelo Zonal 777 y baselines.
* **Extracción de explicabilidad:** Aplicación de *SHAP* comparativo para determinar empíricamente si la regularidad topológica mitiga el sesgo hacia las variables de origen observado en estudios previos.

### Fase Final: Cierre de la Redacción de la Tesis
* **Capítulo 5 (Validación de la Solución):** Rellenar la estructura ya definida con la presentación gráfica y el análisis formal de los resultados experimentales.
* **Capítulo 6 (Conclusiones):** Síntesis de los hallazgos finales y formulación de trabajo futuro, cerrando la hipótesis central.
