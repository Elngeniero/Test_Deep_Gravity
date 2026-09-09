# Arquitectura propuesta para Santiago

**Estado:** especificación científica revisada en F1-B.
**Alcance:** decisiones vigentes y procedimientos pendientes; no reporta resultados del piloto.

## 1. Propósito

La memoria evaluará la sensibilidad de Deep Gravity a dos representaciones espaciales construidas desde una misma cohorte de viajes DTPM:

1. zonas DTPM o 777 irregulares;
2. celdas H3.

La comparación busca establecer cómo cambian el desempeño, la cobertura, la esparsidad, el costo computacional y, solo cuando el modelo sea estable, las explicaciones predictivas. No presupone que H3 mejore el CPC ni que las variables del destino aumenten su importancia.

## 2. Datos y reconstrucción de viajes

La entrega utilizable contiene 29 fechas, del 1 al 29 de noviembre de 2024. Los archivos del día 30 se recibieron con errores y quedan excluidos sin imputación.

| Tabla | Campos relevantes verificados | Estado de uso |
|---|---|---|
| viajes | identificadores de viaje, zonas y comunas consolidadas, secuencia de etapas y factor_expansion | fuente candidata para la unidad viaje y la rama zonal |
| etapas | identificadores de etapa y viaje, coordenadas x_subida, y_subida, x_bajada, y_bajada, zonas, comunas y dos factores de expansión | fuente candidata para reconstruir extremos y asignar H3 |

Las coordenadas no están en viajes. F2-B validó diariamente la unión viajes.(id_tarjeta,id_viaje) con etapas.(id_etapa,correlativo_viajes), y F2-C aprobó la reconstrucción desde la primera etapa para origen y la bajada válida de la etapa final para destino. La cohorte primaria exige secuencia coherente, zonas de origen y destino disponibles y factor_expansion no negativo; la secundaria se conserva separada y no participa en la comparación principal.

factor_expansion de viajes es la masa expandida principal aprobada; unexpanded_weight=1.0 se conserva para sensibilidad. Población censal, generación observada, flujo expandido y atributos OSM son magnitudes distintas y no se intercambiarán en el vector de entrada.

## 3. Núcleo común y adaptadores espaciales

La arquitectura prevista tiene un núcleo canónico de viajes y dos adaptadores, no dos pipelines independientes.

~~~text
viajes + etapas
       |
viajes canónicos, cohorte y área comunes
       |
  +----+----+
  |         |
Zona 777    H3
  |         |
  +----+----+
       |
contrato Deep Gravity común
       |
baselines, entrenamiento y evaluación
~~~

La rama zonal usará los campos auditados de los viajes canónicos y geometría oficial con CRS e identificadores verificados. No heredará automáticamente 743 zonas de un trabajo externo.

La rama H3 transformará coordenadas válidas desde EPSG:32719 a WGS84 y asignará ambos extremos después de cerrar la unión. Se evaluarán H3-r3 a H3-r8 en factibilidad; r6 a r8 son candidatas iniciales, no resoluciones seleccionadas.

## 4. Precisiones sobre H3

H3 es un sistema jerárquico de índices geoespaciales. Sus celdas no son planos idénticos: el área y las distancias varían geográficamente, existen pentágonos y la vecindad no puede describirse como seis vecinos para toda celda. Las áreas y longitudes de referencia se reportarán como promedios globales junto con estadísticas de las celdas presentes en el área elegida.

H3 no elimina el MAUP. La comparación Zona 777-H3 trata la unidad espacial como una fuente de sensibilidad que debe medirse.

## 5. Área, unidades y tiles

El área de estudio no está congelada. F2-D comparará alternativas territoriales con densidad, viajes retenidos, cobertura y esparsidad; después se versionarán el polígono, CRS, comunas y regla de frontera.

Una celda o zona es una unidad origen-destino. Un tile es un bloque espacial mayor usado para particionar y evaluar. El diseño de tiles, los destinos cruzados y el universo de candidatos se resolverán en F2-F/F2-G; no se asume un único tile metropolitano.

## 6. Atributos y modelo

La fuente de población, la instantánea OSM, la ontología de categorías, la unidad de agregación y la normalización siguen pendientes de F2-I. La propuesta de 12 macro-categorías es un insumo de evaluación y no un conjunto ya adoptado. La dimensión del vector de entrada se definirá después de ese contrato.

El código base requiere refactorización y pruebas antes de Santiago. Persisten, entre otros, el CPC con denominador incorrecto, la regeneración defectuosa de caché, la evaluación que se corta tras un lote y una semántica de destinos limitada al tile de origen. Las correcciones corresponden a F2-G.

## 7. Hipótesis y evidencia externa

Vicente Mackenzie se mantiene como antecedente interno que orienta preguntas y diagnósticos. Sus resultados no son un control experimental equivalente ni fijan el número de zonas, el CPC esperado o el patrón SHAP de este estudio.

La hipótesis empírica es bilateral: se medirá si la representación H3 modifica el desempeño y las atribuciones de origen y destino frente a Zona 777. Una ausencia de cambio o un resultado opuesto es informativo. SHAP u otra técnica XAI se ejecutará después de estabilizar datos, entrenamiento y evaluación; sus atribuciones no se interpretarán como causalidad.

## 8. Decisiones pendientes y puertas

| Decisión | Puerta prevista |
|---|---|
| Clave de unión, extremos, descartes, peso y cohorte | G2 |
| Área de estudio, resoluciones H3 y tiles | G3 |
| Correcciones del código, soporte de destinos y CPC | G4 |
| Población, OSM y dimensión final de atributos | F2-I antes del piloto |
| XAI y redacción de resultados | después de G4 |
