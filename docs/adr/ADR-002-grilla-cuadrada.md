# ADR-002: Tessellation Cuadrada como Unidad Espacial

- **Fecha**: 2026-08-20
- **Estado**: ~~Aceptado~~ **Reemplazado por [ADR-004](./ADR-004-grilla-hexagonal-h3-doble-modelo.md)** (2026-09-01)

> [!NOTE]
> Esta decisión fue válida hasta la reunión del 31 de agosto de 2026 con la profesora guía. Se mantiene documentada como registro histórico. La unidad espacial activa del proyecto pasa a ser la grilla hexagonal H3 (con la grilla de zonas 777 como modelo de control). Ver ADR-004 para el razonamiento completo.

## Contexto

El modelo Deep Gravity requiere definir una **unidad espacial** (zona geográfica) para agregar los flujos OD y las features de OpenStreetMap. Se evaluaron tres alternativas:

1. **Comunas del Gran Santiago** (~52 unidades administrativas): unidad disponible directamente en el dataset DTPM (`comuna_inicio_viaje`, `comuna_fin_viaje`).
2. **Zonas 777 (ZAT de SECTRA)**: unidades de análisis de transporte utilizadas en la planificación oficial. Los shapefiles no están disponibles fácilmente.
3. **Tessellation cuadrada** (grilla regular): cuadros de lado fijo generados algorítmicamente sobre el área de estudio.

## Decisión (histórica)

Se utilizó **tessellation cuadrada** como unidad espacial principal, con evaluación de múltiples resoluciones: **500 m, 1 km, 2 km y 5 km**.

**Razones originales:**

- **Coherencia con el paper original**: Deep Gravity (Simini et al., 2021) usa tessellation cuadrada sobre Nueva York, Italia e Inglaterra. Usar la misma unidad permite comparabilidad directa.
- **Objetivos de la tesis**: los Objetivos Específicos 2 y 6 de `definicion_del_problema.tex` establecen explícitamente la tessellation cuadrada y el análisis de sensibilidad por resolución como contribuciones metodológicas.
- **Generación algorítmica**: `skmob.tessellation.tilers.get("squared", ...)` genera la grilla sin necesidad de shapefiles externos, usando las coordenadas UTM del dataset DTPM.
- **Análisis de sensibilidad**: comparar CPC y valores SHAP a distintas resoluciones (500m–5km) es una contribución metodológica propia que no sería posible con comunas (escala única fija).
- **Compatibilidad con el dataset**: los campos UTM (`x_subida`, `y_subida`, `x_bajada`, `y_bajada`) permiten asignar cada viaje a la celda exacta de la grilla.

## Por qué fue reemplazada

La reunión del 31/08/2026 con la profesora guía introdujo nueva evidencia: el trabajo de Vicente Mackenzie (2026) mostró que usar zonas irregulares (777) como unidad de entrenamiento produce una relación OD degenerada (el modelo aprende atributos del origen, no del destino). La profesora orientó hacia **grilla hexagonal H3** en lugar de cuadrada, y hacia una **estrategia comparativa doble** (zona irregular como control vs. grilla regular H3 como propuesta). La grilla cuadrada queda descartada también porque no fue testada en el antecedente local y no agrega evidencia diferenciadora frente a H3.

## Consecuencias

- **Positivas históricas**: coherencia metodológica con el paper, análisis de sensibilidad posible, sin dependencia de shapefiles externos.
- **Comunas como capa complementaria**: los resultados se seguirán agregando a nivel comunal para visualización institucional.
- **Granularidad**: la resolución de la grilla hexagonal H3 (resoluciones 3–8 del sistema Uber H3) reemplaza el análisis de sensibilidad 500m–5km. Ver ADR-004.
