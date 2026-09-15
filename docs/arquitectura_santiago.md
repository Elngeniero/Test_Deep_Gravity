# Arquitectura propuesta para Santiago

**Estado:** especificación científica revisada en F1-B; F2-G/F2-H verificadas y contrato F2-I aprobado el 14 de septiembre de 2026. F2-J aún no iniciada.
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

La rama H3 transforma coordenadas válidas desde EPSG:32719 a WGS84 y asigna ambos extremos directamente en cada resolución. H3-r7 y H3-r8 pasan al piloto. F2-G corrigió el uso de padres de r8 en la implementación previa de r7: su tabla histórica conserva 223 unidades, 220 orígenes activos y 37.196 pares OD. Tras la exclusión común aprobada en F2-I, r7 conserva 223 unidades, 218 orígenes activos y 37.089 pares OD. Las tablas para continuar se identifican por hash en `docs/territorio/f2i/F2-I_CONTRATO_APROBADO.json`; `docs/verificacion/f2g/` conserva la base histórica.

## 4. Precisiones sobre H3

H3 es un sistema jerárquico de índices geoespaciales. Sus celdas no son planos idénticos: el área y las distancias varían geográficamente, existen pentágonos y la vecindad no puede describirse como seis vecinos para toda celda. Las áreas y longitudes de referencia se reportarán como promedios globales junto con estadísticas de las celdas presentes en el área elegida.

H3 no elimina el MAUP. La comparación Zona 777-H3 trata la unidad espacial como una fuente de sensibilidad que debe medirse.

## 5. Área, unidades y tiles

El área de estudio aprobada el 9 de septiembre de 2026 es el núcleo referencial de 34 comunas de F2-D. La regla exige ambos extremos UTM estrictamente contenidos en las geometrías comunales seleccionadas, proyectadas a EPSG:32719. El filtro territorial retiene 60.513.881 viajes (99,72 % de la cohorte primaria) y 99,69 % de la masa expandida. La geometría y los hashes se fijan en `docs/territorio/f2d/F2-D_AREA_APROBADA.geojson` y su manifiesto JSON. F2-I añade la exclusión común aprobada de 1.904 viajes con algún extremo en las zonas sin polígono oficial 848, 849 o 852: quedan 60.511.977 viajes y masa 85.774.522,4070 en Zona777, H3-r7 y H3-r8. Se conservan las huellas completas de las celdas para atributos y el dominio territorial estricto para los viajes.

Una celda o zona es una unidad origen-destino. Un tile es un bloque espacial mayor usado para particionar y evaluar. F2-F/F2-G fijaron 10 tiles y soporte metropolitano global de destinos. F2-I mantiene las asignaciones de tiles y particiones; actualiza los totales por unidad tras la exclusión común.

## 6. Atributos y modelo

F2-I adoptó Censo 2024 de manzanas y entidades de la RM, asignado por interpolación areal, y OSM Chile del 1 de enero de 2024. El diccionario principal `paper19` contiene 19 variables por ubicación: población, cinco coberturas de suelo, tres densidades viales y cinco familias de servicios, cada una con densidad de puntos y cobertura de áreas. El par OD tiene **39 entradas**. Se unen polígonos y vías dentro de cada categoría antes de medir área o longitud, y se cuentan puntos con pertenencia estricta. Densidades y tasas usan `log1p`; todas las variables se estandarizan con parámetros ajustados únicamente sobre orígenes activos de entrenamiento. La alternativa `macro12_geometry20` tiene 20 variables y 41 entradas; queda disponible para diagnóstico. Véanse [ADR-006](adr/ADR-006-propuesta-cierre-f2i.md), [diccionario](territorio/f2i/F2-I_DICCIONARIO_PROPUESTA.json) y [contrato aprobado](territorio/f2i/F2-I_CONTRATO_APROBADO.json).

F2-G corrigió el denominador de CPC, la serialización y regeneración de caché, la evaluación de todos los lotes y el soporte metropolitano de destinos. El refactor conserva cinco capas ocultas de 256 y diez de 128, sin BatchNorm y con dropout efectivo 0,0. Las 37 pruebas, la conservación mensual y el ensayo sintético están documentados en `docs/verificacion/f2g/F2-G_REPORTE_IMPLEMENTACION.md`. F2-H completó una corrida de Nueva York de 20 épocas con CPC global 0,506684 y comprobación independiente; su reporte distingue la validez técnica de la equivalencia científica no acreditada con el artículo. La pérdida efectiva sigue ponderada por conteos y debe declararse en el protocolo del piloto. El piloto Santiago continúa pendiente y G4 permanece abierta.

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
| Población, OSM y dimensión final de atributos | F2-I cerrada y aprobada: Censo 2024, paper19 con 39 entradas y cohorte común de 60.511.977 viajes; ADR-006 |
| XAI y redacción de resultados | después de G4 |
