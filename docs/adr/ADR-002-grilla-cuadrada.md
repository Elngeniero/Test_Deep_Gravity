# ADR-002: Tessellation Cuadrada como Unidad Espacial

- **Fecha**: 2026-08-20
- **Estado**: Aceptado

## Contexto

El modelo Deep Gravity requiere definir una **unidad espacial** (zona geográfica) para agregar los flujos OD y las features de OpenStreetMap. Se evaluaron tres alternativas:

1. **Comunas del Gran Santiago** (~52 unidades administrativas): unidad disponible directamente en el dataset DTPM (`comuna_inicio_viaje`, `comuna_fin_viaje`).
2. **Zonas 777 (ZAT de SECTRA)**: unidades de análisis de transporte utilizadas en la planificación oficial. Los shapefiles no están disponibles fácilmente.
3. **Tessellation cuadrada** (grilla regular): cuadros de lado fijo generados algorítmicamente sobre el área de estudio.

## Decisión

Se utiliza **tessellation cuadrada** como unidad espacial principal, con evaluación de múltiples resoluciones: **500 m, 1 km, 2 km y 5 km**.

**Razones:**

- **Coherencia con el paper original**: Deep Gravity (Simini et al., 2021) usa tessellation cuadrada sobre Nueva York, Italia e Inglaterra. Usar la misma unidad permite comparabilidad directa.
- **Objetivos de la tesis**: los Objetivos Específicos 2 y 6 de `definicion_del_problema.tex` establecen explícitamente la tessellation cuadrada y el análisis de sensibilidad por resolución como contribuciones metodológicas.
- **Generación algorítmica**: `skmob.tessellation.tilers.get("squared", ...)` genera la grilla sin necesidad de shapefiles externos, usando las coordenadas UTM del dataset DTPM.
- **Análisis de sensibilidad**: comparar CPC y valores SHAP a distintas resoluciones (500m–5km) es una contribución metodológica propia que no sería posible con comunas (escala única fija).
- **Compatibilidad con el dataset**: los campos UTM (`x_subida`, `y_subida`, `x_bajada`, `y_bajada`) permiten asignar cada viaje a la celda exacta de la grilla.

## Consecuencias

- **Positivas**: coherencia metodológica con el paper, análisis de sensibilidad posible, sin dependencia de shapefiles externos.
- **Comunas como capa complementaria**: los resultados se agregarán también a nivel comunal para visualización e interpretación institucional (planificadores urbanos), pero el análisis principal opera sobre la grilla.
- **Granularidad óptima por definir**: la resolución final se elegirá tras un piloto comparativo (CPC vs. costo computacional). Se anticipa que 1km o 2km será el punto de equilibrio para el Gran Santiago.
