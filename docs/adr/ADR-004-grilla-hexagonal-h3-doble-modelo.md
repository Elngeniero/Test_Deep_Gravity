# ADR-004: Grilla Hexagonal H3 (Uber) y Estrategia de Doble Modelo Comparativo

- **Fecha**: 2026-09-01
- **Estado**: Aceptado
- **Reemplaza**: [ADR-002](./ADR-002-grilla-cuadrada.md) (Tessellation Cuadrada)

## Contexto

Hasta la reunión del 31 de agosto de 2026, la unidad espacial del proyecto era una grilla cuadrada (ADR-002). La profesora guía, en base al análisis del trabajo previo de Vicente Mackenzie (2026), identificó dos problemas críticos que motivan un cambio de diseño:

**Problema 1 — Zonas irregulares producen relación OD degenerada:**
Vicente entrenó Deep Gravity sobre las 743 zonas operativas DTPM (Teselación 777), que son polígonos irregulares en tamaño y forma. El análisis SHAP de su modelo reveló que las 5 variables de mayor impacto pertenecen todas al **vector del origen** (Vías Principales_origen SHAP≈0.90, Vías Secundarias_origen SHAP≈0.52, Transporte Público_origen SHAP≈0.35, Ocio/Parques_origen, Comercio/Retail_origen). Las amenities del **destino** — que deberían ser los atractores decisivos de la elección de destino — tuvieron impacto marginal o nulo. El modelo aprendió un atajo estadístico basado en "de dónde sale el viaje" en lugar de aprender la interacción origen-destino real. CPC máximo reportado: 0.2566 (Periodo Valle).

**Problema 2 — La grilla cuadrada no aporta evidencia diferenciadora:**
No existe antecedente local (Santiago) que valide la grilla cuadrada frente a H3. La grilla hexagonal H3 del sistema Uber tiene propiedades geométricas superiores (vecindad isotrópica, sin efecto esquina) y es el estándar emergente para análisis de movilidad urbana.

**Oportunidad metodológica:**
La hipótesis de la profesora es que la unidad espacial irregular (zona 777) es la causa raíz del sesgo al origen en Vicente. Si con grilla regular H3 el SHAP del destino recupera importancia, esto es evidencia de que el problema era la geometría de la unidad, no las variables en sí.

## Decisión

### Unidad espacial principal: Grilla Hexagonal H3 (Uber H3)

Se adopta la **grilla hexagonal H3 de Uber** como unidad espacial del modelo propuesto. H3 es un sistema de indexación geoespacial jerárquico que divide la esfera terrestre en hexágonos regulares con 16 niveles de resolución (0=más grueso, 15=más fino).

**Resoluciones a explorar:** 3 a 8 del sistema H3 (a confirmar la gama definitiva con la profesora guía tras el piloto computacional).

**Razones:**
- **Regularidad geométrica**: todos los hexágonos H3 tienen igual área nominal dentro de una resolución dada, eliminando el sesgo de tamaño que afecta a las zonas 777 irregulares.
- **Vecindad isotrópica**: los hexágonos tienen 6 vecinos equidistantes, a diferencia de los cuadrados (4 cardinales + 4 diagonales con distancia diferente) y los polígonos irregulares.
- **Sistema de coordenadas nativo**: H3 opera sobre coordenadas geográficas (lat/lon). Los campos UTM del dataset DTPM (`x_subida`, `y_subida`, `x_bajada`, `y_bajada`) se reprojectan a WGS84 para asignar cada validación bip! a su hexágono H3 correspondiente mediante `h3.latlng_to_cell(lat, lon, resolution)` (librería `h3-py`).
- **Hipótesis experimental**: con unidad regular, se espera que el SHAP del destino recupere importancia, validando la hipótesis de que el sesgo al origen en Vicente se debía a la irregularidad de las zonas.

### Estrategia de doble modelo comparativo (+ baseline opcional)

Se implementan simultáneamente los siguientes modelos para comparar el efecto de la unidad espacial:

| Modelo | Unidad espacial | Requiere redistribución | Rol en la tesis |
|---|---|---|---|
| **Modelo 0** *(opcional, si el tiempo alcanza)* | Comunas del Gran Santiago | No | Baseline simple, sin datos de alta resolución. Aprovecha `comuna_subida`/`comuna_bajada` directamente. |
| **Modelo 1** | Zonas DTPM/EOD (Teselación 777, polígonos irregulares) | No | Control/réplica del enfoque de Vicente. Base de comparación para cuantificar el efecto del cambio de unidad. |
| **Modelo 2** *(principal)* | Grilla hexagonal H3 | **Sí** (ver sección de redistribución) | Propuesta de la tesis. Si el SHAP del destino mejora frente al Modelo 1, valida la hipótesis de la unidad espacial. |

### Redistribución de viajes para el Modelo 2

El dataset DTPM tiene viajes pre-agregados por zona 777. Para construir la matriz OD por hexágono H3 hay dos estrategias:

**Estrategia A — Asignación punto-a-hexágono (preferida):**
Usar directamente los campos `x_subida`, `y_subida`, `x_bajada`, `y_bajada` del CSV de viajes (coordenadas UTM, EPSG:32719) para asignar cada validación individual a su hexágono H3 de origen y destino. No se necesita redistribución porque se opera a nivel de viaje individual, no a nivel de zona agregada. Esta estrategia es superior porque evita el error de redistribución.

**Estrategia B — Redistribución por proporción de superficie (fallback si A no es viable):**
Si los datos solo están disponibles a nivel de zona (flujos agregados zona→zona), redistribuir los viajes a hexágonos usando la proporción de superficie:
- **Método:** peso = área del hexágono ∩ zona / área total de la zona.
- **Justificación:** dado que los hexágonos H3 son regulares y cubren el territorio de forma homogénea, la proporción de superficie es una aproximación razonable. El método censal queda descartado como innecesario dado que la Estrategia A (punto-a-hexágono) es la vía preferida.

Se priorizará la Estrategia A dado que los CSV del DTPM contienen coordenadas individuales por validación.

### Análisis comparativo CPC + SHAP

- Calcular CPC para Modelo 0 (si aplica), Modelo 1 y Modelo 2, en los mismos periodos horarios (Punta Mañana, Valle, Punta Tarde) para días de semana y fin de semana.
- Calcular SHAP para Modelo 1 y Modelo 2. El aporte diferencial de la tesis es demostrar si las amenities del **destino** recuperan importancia al cambiar a grilla regular.
- Comparar el ranking SHAP entre modelos: si en Modelo 2 el vector del destino sube de posición, se valida la hipótesis.

## Consecuencias

- **Positivas:**
  - Aporte metodológico propio: la tesis no solo implementa Deep Gravity en Santiago (como Vicente), sino que **compara empíricamente** el efecto de la unidad espacial sobre la calidad de la estimación.
  - Hipótesis testable y falseable: "la grilla regular H3 mejora la relación OD aprendida por el modelo".
  - Permite citar el trabajo de Vicente como antecedente directo y mostrar mejora cuantificable.
- **Negativas/Riesgos:**
  - Mayor complejidad de implementación: dos pipelines paralelos (zona 777 y H3).
  - Las resoluciones H3 óptimas aún están por definir (piloto computacional requerido).
  - La asignación punto-a-hexágono requiere reprojectar coordenadas UTM → WGS84.
- **Dependencias:**
  - [ADR-001](./ADR-001-dataset-dtpm-nov2024.md): el dataset DTPM debe contener coordenadas individuales por validación (confirmado).
  - [ADR-005](./ADR-005-delimitacion-gran-santiago.md): la grilla H3 debe recortarse al área del Gran Santiago definida en ADR-005.
  - Librería `h3-py` debe agregarse a `requirements.txt` (o similar).
- **Pendientes:**
  - Confirmar con la profesora el rango definitivo de resoluciones H3 a explorar.
  - Definir si Modelo 0 (comunal) se implementa en la fase actual o se posterga.
