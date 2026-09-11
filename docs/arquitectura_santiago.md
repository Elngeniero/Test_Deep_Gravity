# Arquitectura propuesta para Santiago

**Estado:** especificación científica revisada en F1-B; implementación técnica actualizada al cierre de F2-G, 10 de septiembre de 2026.
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

La rama H3 transforma coordenadas válidas desde EPSG:32719 a WGS84 y asigna ambos extremos directamente en cada resolución. H3-r7 y H3-r8 pasan al piloto. F2-G corrigió el uso de padres de r8 en la implementación previa de r7: la tabla operativa directa tiene 223 unidades observadas, 220 orígenes activos y 37.196 pares OD. Las unidades y particiones actualizadas se guardan en `docs/verificacion/f2g/`.

## 4. Precisiones sobre H3

H3 es un sistema jerárquico de índices geoespaciales. Sus celdas no son planos idénticos: el área y las distancias varían geográficamente, existen pentágonos y la vecindad no puede describirse como seis vecinos para toda celda. Las áreas y longitudes de referencia se reportarán como promedios globales junto con estadísticas de las celdas presentes en el área elegida.

H3 no elimina el MAUP. La comparación Zona 777-H3 trata la unidad espacial como una fuente de sensibilidad que debe medirse.

## 5. Área, unidades y tiles

El área de estudio aprobada el 9 de septiembre de 2026 es el núcleo referencial de 34 comunas de F2-D. La regla exige ambos extremos UTM estrictamente contenidos en las geometrías comunales seleccionadas, proyectadas a EPSG:32719. Retiene 60.513.881 viajes (99,72 % de la cohorte primaria) y 99,69 % de la masa expandida. La geometría y los hashes se fijan en `docs/territorio/f2d/F2-D_AREA_APROBADA.geojson` y su manifiesto JSON. F2-E resolverá el tratamiento de celdas H3 que cruzan los bordes manteniendo este dominio de viajes.

Una celda o zona es una unidad origen-destino. Un tile es un bloque espacial mayor usado para particionar y evaluar. El diseño de tiles, los destinos cruzados y el universo de candidatos se resolverán en F2-F/F2-G; no se asume un único tile metropolitano.

## 6. Atributos y modelo

La fuente de población, la instantánea OSM, la ontología de categorías, la unidad de agregación y la normalización siguen pendientes de F2-I. La propuesta de 12 macro-categorías es un insumo de evaluación y no un conjunto ya adoptado. La dimensión del vector de entrada se definirá después de ese contrato.

F2-G corrigió el denominador de CPC, la serialización y regeneración de caché, la evaluación de todos los lotes y el soporte metropolitano de destinos. El refactor conserva cinco capas ocultas de 256 y diez de 128, sin BatchNorm y con dropout efectivo 0,0. Las 37 pruebas, la conservación mensual y el ensayo sintético están documentados en `docs/verificacion/f2g/F2-G_REPORTE_IMPLEMENTACION.md`; F2-H y el piloto de Santiago siguen pendientes.

## 7. Hipótesis y evidencia externa

Vicente Mackenzie se mantiene como antecedente interno que orienta preguntas y diagnósticos. Sus resultados no son un control experimental equivalente ni fijan el número de zonas, el CPC esperado o el patrón SHAP de este estudio.

La hipótesis empírica es bilateral: se medirá si la representación H3 modifica el desempeño y las atribuciones de origen y destino frente a Zona 777. Una ausencia de cambio o un resultado opuesto es informativo. SHAP u otra técnica XAI se ejecutará después de estabilizar datos, entrenamiento y evaluación; sus atribuciones no se interpretarán como causalidad.

## 8. Decisiones pendientes y puertas

| Decisión | Puerta prevista |
|---|---|
| Clave de unión, extremos, descartes, peso y cohorte | G2 cerrado |
| Área de estudio | F2-D completada y aprobada; ADR-005 |
| Resoluciones H3, bordes de celdas y tiles | G3 cerrada: Zona 777, H3-r7/r8 y 10 tiles determinísticos documentados en F2-E/F |
| Correcciones del código, soporte de destinos y CPC | F2-G completada y verificada; G4 sigue abierta hasta el piloto |
| Población, OSM y dimensión final de atributos | F2-I antes del piloto |
| XAI y redacción de resultados | después de G4 |
