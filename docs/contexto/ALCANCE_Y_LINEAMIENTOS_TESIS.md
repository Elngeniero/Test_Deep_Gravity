# Alcance y lineamientos de la tesis

**Estado:** revisado en F1-B el 8 de septiembre de 2026.
**Propósito:** definir el alcance científico vigente sin anticipar resultados del piloto de Santiago.

## 1. Problema

La tesis adapta Deep Gravity para estudiar flujos observados en el sistema de transporte público de Santiago mediante registros DTPM de noviembre de 2024. El estudio no representa todos los viajes urbanos: se limita a los modos y trayectos observables en la fuente DTPM.

La contribución propuesta no presupone una mejora de desempeño. Evalúa cómo la discretización espacial afecta la cobertura, esparsidad, desempeño y explicaciones predictivas de un modelo de flujos.

## 2. Objetivo general

Evaluar la sensibilidad de Deep Gravity y de sus baselines frente a dos representaciones espaciales, Zona 777 y H3, construidas desde una cohorte DTPM común y reproducible.

## 3. Objetivos específicos

1. Auditar la entrega DTPM, validar la unión entre viajes y etapas, y construir un contrato canónico de viajes.
2. Delimitar un área de estudio mediante evidencia territorial y documentar sus reglas de frontera.
3. Construir adaptadores comparables para Zona 777 y H3, y analizar H3-r3 a H3-r8 antes de seleccionar resoluciones.
4. Definir particiones espaciales, soporte de destinos, pesos, características y baselines desde un contrato común.
5. Adaptar y probar el código de Deep Gravity, incluida la métrica CPC, antes de interpretar reproducciones o resultados de Santiago.
6. Ejecutar un piloto reproducible de Santiago para elegir la configuración de los experimentos finales.
7. Aplicar XAI solo sobre el modelo final estabilizado, reportando estabilidad y sin interpretar atribuciones predictivas como causalidad.

## 4. Fuente, período y unidades

La entrega disponible contiene 29 fechas, del 1 al 29 de noviembre de 2024. Los archivos del 30 llegaron con errores y se excluyen sin imputación.

La cabecera de viajes contiene las unidades consolidadas, zonas, comunas y secuencias. Las coordenadas UTM de subida y bajada están en etapas. La reconstrucción de extremos para H3 depende de que F2-B y F2-C validen la unión, el orden de etapas y la calidad de bajada.

La comparación empleará una cohorte primaria común:

- rama zonal: zonas DTPM o 777 irregulares;
- rama H3: celdas H3 asignadas desde extremos válidos;
- tile: bloque espacial mayor para particionar o evaluar, distinto de la unidad origen-destino.

## 5. Decisiones metodológicas vigentes

| Tema | Decisión o estado |
|---|---|
| Área | pendiente de EDA territorial y G3 |
| Resolución H3 | pendiente de factibilidad, validación y costo computacional |
| Peso principal | pendiente de auditoría de los tres factores de expansión |
| Población y OSM | fuente, ontología, agregación y normalización pendientes de F2-I |
| Baselines | se definirán con el mismo contrato de cohorte y evaluación |
| CPC | métrica principal prevista, su implementación debe corregirse y probarse en F2-G |
| XAI | diferida hasta que datos, entrenamiento y evaluación sean estables |

H3 es un sistema jerárquico; sus celdas no son exactamente equiáreas, existen pentágonos y no elimina el MAUP. La comparación Zona 777-H3 trata estos efectos como sensibilidad empírica.

## 6. Referencias y limitaciones

Vicente Mackenzie se utiliza como antecedente interno y orientador, no como réplica ni control experimental equivalente. Sus resultados no fijan el CPC, la resolución, el número de zonas ni el resultado esperado de SHAP.

La EOD se mantiene como referencia histórica y no es el ground truth de esta implementación. También quedan fuera de alcance la predicción temporal, la evaluación causal de políticas públicas, los viajes no observados por DTPM y otros modelos neuronales espaciales.

## 7. Estado de ejecución

- F2-A: completado; G0 cerrado.
- F1-A: completado; la matriz de trazabilidad identifica contradicciones y acciones de corrección.
- F1-B: completado; alcance, ADR y arquitectura revisados.
- F2-B: en curso; su resultado será necesario para cerrar el contrato de datos G2.

El capítulo 4 se reescribirá en F1-C como una especificación verificable. Los capítulos de resultados, conclusiones y XAI final quedan fuera de esta fase.
