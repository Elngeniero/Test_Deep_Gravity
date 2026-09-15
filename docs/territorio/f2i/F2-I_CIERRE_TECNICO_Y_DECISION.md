# F2-I — Cierre técnico y contrato aprobado

Actualizado: **14 de septiembre de 2026**. La generación de atributos y la integración terminaron el **13 de septiembre, 20:03 hora de Santiago**. El investigador aprobó el contrato el 14 de septiembre mediante «si apruebo». Estado: **F2-I y etapa 6 cerradas y aprobadas**. F2-J queda habilitada, aún no iniciada. La auditoría F2-H de Nueva York permanece cerrada con sus limitaciones; no se exige una reproducción integral adicional para continuar Santiago.

## Trabajo completado

| Ítem solicitado | Resultado comprobado | Evidencia |
|---|---|---|
| 1. Corregir y auditar los atributos | Áreas unidas antes de medir; vías por longitud; POI por densidad; población en ambos candidatos; coberturas entre 0 y 1 | [Verificación v2](F2-I_VERIFICACION_V2.json) |
| 2. Preparar la selección y resolver la alternativa geométrica | Comparación de dos diccionarios; paper19 y exclusión común adoptados para evitar los tres IDs sin polígono oficial | [Contrato aprobado](F2-I_CONTRATO_APROBADO.json), [impacto](F2-I_GEOMETRY_IMPACT.json), [ADR-006 aceptado](../../adr/ADR-006-propuesta-cierre-f2i.md) |
| 3. Integrar y verificar | Seis contratos cargados por el adaptador científico, normalización verificada y paso de inferencia sin entrenamiento | [Integración verificada](F2-I_INTEGRACION_VERIFICADA.json) |

La alternativa materializada fue adoptada como cohorte común para las siguientes fases. Los insumos originales de F2-C/F2-D/F2-G se conservan; ADR-006 registra la exclusión adicional. El [registro definitivo](F2-I_CONTRATO_APROBADO.json) fija los hashes de los productos ya verificados. Los manifiestos de propuesta conservan sus estados previos como historial y no representan una aprobación todavía pendiente.

## Fuentes y tratamiento

**Población adoptada:** INE, Censo 2024, manzanas y entidades de la Región Metropolitana, campo `n_per`, licencia declarada CC BY-SA 4.0. Se conservaron 68.945 geometrías de origen, con 7.291.744 personas y ningún registro inválido de población o geometría en la asignación. Se reparte población según la fracción de área intersectada con cada unidad, en EPSG:32719, y luego se divide por el área de la unidad. Esta interpolación supone población uniforme dentro de cada geometría censal; no proporciona población observada directamente en H3. [Servicio de origen](https://services5.arcgis.com/hUyD8u3TeZLKPe4T/arcgis/rest/services/Censo2024_v2/FeatureServer/5).

**OSM:** extracto histórico [Chile, Geofabrik](https://download.geofabrik.de/south-america/chile-240101.osm.pbf), ODbL 1.0. La cabecera real indica **2024-01-01T21:21:15Z**; corrige la hora inicialmente declarada en la configuración. La instantánea antecede aproximadamente diez meses a los viajes de noviembre de 2024. Ambos insumos tienen SHA-256 registrado en la verificación v2.

La extracción conserva 145.406 áreas, 157.222 vías seleccionadas y 36.118 puntos después de suprimir 102 duplicados nodo-área de igual nombre y categoría. El filtro nativo de Pyosmium conserva la construcción previa de geometrías y la ubicación de los nodos sin etiquetas, comportamiento comprobado con una prueba específica. [Documentación de filtros](https://docs.osmcode.org/pyosmium/latest/user_manual/04-Working-with-Filters/).

Dentro de cada categoría, los polígonos se recortan y unen antes de calcular cobertura; las líneas se recortan y unen antes de medir longitud. Se conservan agujeros de polígonos. Una línea coincidente con un límite compartido se asigna por orden determinista de `unit_id`. Los puntos requieren pertenencia estricta; los situados exactamente en el límite quedan sin asignar. Capas semánticas distintas pueden superponerse: sus coberturas no forman una partición exhaustiva del suelo ni deben sumarse. `other` tiene una lista cerrada de etiquetas.

La corrección eliminó aproximadamente 4,08 km² de área residencial contada más de una vez en Zona777 y H3-r7. Las coberturas residenciales máximas corregidas son 1,00, 0,999929 y 1,00 en Zona777, H3-r7 y H3-r8. Los CSV originales permanecen como evidencia histórica y están sustituidos por v2.

## Candidatos y selección aprobada

| Candidato | Variables por ubicación | Entradas del par OD | Situación |
|---|---:|---:|---|
| `paper19` adaptado | 19 | 39 = 19 + 19 + distancia | Adoptado como principal para el piloto Santiago |
| `macro12_geometry20` | 20 | 41 = 20 + 20 + distancia | Disponible para diagnóstico de sensibilidad; no es el contrato principal |

`paper19` contiene población, cinco coberturas de uso de suelo, tres densidades de longitud vial y cinco familias de servicios, cada una con densidad de puntos y cobertura de áreas. Su nombre identifica una adaptación temática; no acredita equivalencia con la construcción de atributos del artículo.

Las doce macro-categorías históricas requieren 20 variables al incorporar población y separar conteos, áreas y longitudes. No se conserva la afirmación anterior de 27 entradas: aquel CSV omitía población y mezclaba representaciones geométricas. El [diccionario de la propuesta](F2-I_DICCIONARIO_PROPUESTA.json) declara nombre, filtros exactos, precedencias, fuente, unidades, agregación, nulos y normalización.

Ambos candidatos tienen cobertura finita completa en la propuesta y ninguna columna constante entre orígenes de entrenamiento. La cobertura no nula más escasa corresponde al área de transporte: 68/793 zonas (8,58 %), 47/223 celdas r7 (21,08 %) y 82/1.210 celdas r8 (6,78 %). Una variable escasa no se elimina automáticamente: la cobertura finita y la presencia cartográfica son conceptos diferentes. Cero en OSM representa ausencia cartografiada, no prueba de ausencia real.

En H3-r7, las densidades de puntos de alimentación y comercio tienen correlación de Pearson de 0,964048 entre los orígenes de entrenamiento de la propuesta. Se conservan como fenómenos diferentes y se propone revisar su redundancia en el diagnóstico del piloto. No aparecen otras parejas con |r| ≥ 0,95 en estas tablas. Este valor es una alerta descriptiva, no un umbral de descarte ni una decisión basada en el conjunto de prueba.

Se adoptó `paper19` como principal porque conserva una estructura temática interpretable cercana a la referencia y utiliza una variable menos; la evidencia disponible no demuestra que las macro-categorías mejoren predicción o cobertura. La aprobación no presupone mejor desempeño de este diccionario: el piloto debe medirlo.

Para densidades y tasas se aplica `log1p`; para coberturas se conserva la escala física antes de estandarizar. Media y desviación se ajustan exclusivamente con los orígenes activos de entrenamiento de cada rama. Los mismos parámetros se aplican a todas las unidades, incluidas las de validación y prueba. No se utiliza flujo observado como población o predictor. La población total asignada puede diferir entre ramas porque las huellas completas de las celdas y zonas son distintas; la masa de viajes comparada sí es común.

## Exclusión común aprobada para los tres polígonos faltantes

El universo operativo F2-G tiene 796 IDs zonales, de los cuales **848, 849 y 852** carecen de polígono oficial. El shapefile alternativo EOD 2012 examinado contiene números iguales con otra codificación espacial; fue rechazado y no se usó para rellenar atributos. Su procedencia, hashes y comprobaciones están en [auditoría de la fuente alternativa](F2-I_GEOMETRY_SOURCE_AUDIT.json).

Se aprobó la exclusión de exactamente los mismos viajes canónicos cuando cualquiera de sus extremos pertenece a esos tres IDs. La regla se aplica antes de agregar OD, también en H3. No se fabrican polígonos ni se imputan atributos zonales.

| Magnitud | F2-G histórico, conservado | F2-I aprobado |
|---|---:|---:|
| Viajes | 60.513.881 | 60.511.977 |
| Masa expandida | 85.777.662,9386 | 85.774.522,4070 |
| Viajes retirados | — | 1.904 (0,003146 %) |
| Masa retirada | — | 3.140,5316 (0,003661 %) |

| Rama aprobada | Unidades con atributos | Orígenes activos | Entrenamiento / validación / prueba | Pares OD observados |
|---|---:|---:|---|---:|
| Zona777 | 793 | 793 | 507 / 185 / 101 | 426.948 |
| H3-r7 | 223 | 218 | 126 / 60 / 32 | 37.089 |
| H3-r8 | 1.210 | 1.189 | 701 / 299 / 189 | 616.749 |

Las celdas H3 sin origen activo se conservan como destinos. Se mantienen el dominio de 34 comunas, la asignación H3 directa, los tiles y sus etiquetas de partición. Solo se recalculan los totales por unidad y los orígenes que conservan viajes. Los hashes de los insumos originales coinciden después de generar la alternativa.

## Verificación y archivos terminados

La integración comprobó 69 referencias de archivos mediante hashes —incluye referencias repetidas entre manifiestos—, todas las filas de atributos, masas OD, totales por unidad y partición, parámetros de normalización y soporte completo de destinos. Los seis contratos pasaron un recorrido por el adaptador y la red sin entrenamiento, con un origen de entrenamiento por contrato. Error máximo de reconstrucción de atributos normalizados: inferior a 5 × 10⁻¹¹. El contrato zonal original con los tres nulos continúa rechazado por el adaptador.

Pasaron **11 pruebas F2-I** y **37 pruebas F2-G**. Las pruebas F2-G usan datos sintéticos; sus pequeñas corridas de prueba no son el piloto Santiago. No se produjeron checkpoints ni métricas científicas F2-J. Véase [registro de comprobaciones](F2-I_PRUEBAS.md).

Directorio base local:

```text
C:\Users\pablo\Documents\070.- MEMORIA DE PABLO CAMPOS\Modelo_Deep_Gravity\DeepGravity\deepgravity\data\santiago\processed\f2i\
```

| Carpeta | Archivos esperados y presentes | Finalidad |
|---|---:|---|
| `v2/` | 19: 13 CSV y 6 JSON | Atributos corregidos sobre el universo original; tres filas zonales incompletas explícitas |
| `proposal_common_exclusion/` | 33: 21 CSV, 3 Parquet y 9 JSON | Productos adoptados por hash; se conserva el nombre histórico de la carpeta |

Cada rama contiene diez archivos: `od.parquet`, `units.csv`, `partitions.csv`, `removed_od.csv` y tres archivos por candidato (`*_features.csv`, `*_model.csv`, `*_preprocessing.json`). La raíz contiene `scenario.json`, `feature_dictionary.json` y `feature_contracts.json`. Los seis contratos `config/f2i_contract_*.example.json` conservan la propuesta original. Las tres configuraciones principales adoptadas son `config/f2i_approved_{zona777,h3_r7,h3_r8}_paper19.example.json`; sus hashes y aprobación están en `docs/territorio/f2i/F2-I_CONTRATO_APROBADO.json`. Su modo `f2i_contract_check` declara un contrato de datos, no una orden de entrenamiento mensual.

El conteo por sí solo no acredita término: los manifiestos y `F2-I_INTEGRACION_VERIFICADA.json` registran verificaciones aprobadas y `training_started=false`. No es necesario volver a generar estos productos para comprobar su estado.

## Adopción y cierre de la etapa 6

Decisión aprobada el **14 de septiembre de 2026**: **Censo 2024 + `paper19` corregido como candidato principal + exclusión común de 1.904 viajes**. `macro12_geometry20` queda disponible para diagnóstico. La aprobación expresa del investigador satisface la intervención prevista en el [plan maestro, F2.6](../../PLAN_MAESTRO_FRENTES_1_Y_2.md#f26-decisiones-que-requieren-intervención-del-usuario), y ADR-006 queda aceptado.

El contrato está fijado por hashes y **F2-I queda cerrada**. Al registrar la adopción se verificó que los productos coinciden con la integración previa y se cargaron los tres contratos aprobados con el adaptador científico: dimensiones correctas y masa mensual conciliada en las tres ramas. Los datos originales F2-G no cambiaron. Esta operación no entrenó ningún modelo.

La siguiente fase es F2-J con los escalones del plan: muestra pequeña, día laboral y periodos horarios antes del piloto estable. Los productos actuales son mensuales y no sustituyen esos escalones; tampoco debe reutilizarse automáticamente su ajuste de normalización si cambia el conjunto de orígenes activos de entrenamiento del escalón. **F2-J aún no se ha iniciado; G4 permanece abierta hasta verificar el piloto y G5 espera la sincronización documental posterior.** La reproducción integral de Nueva York no es un pendiente de este cierre.

## Reconstrucción y trazabilidad

Con los insumos raw ya descargados, el orden es: `tools/f2i_osm_cache.py`, `tools/f2i_finalize.py`, `tools/audit_f2i_missing_zones.py`, `tools/prepare_f2i_common_cohort.py`, `tools/prepare_f2i_feature_contracts.py` y `tools/verify_f2i_integration.py`. Extracción, geometría y contratos usan Python 3.12 con `requirements-f2i.txt`; auditoría de viajes, cohorte e integración usan el entorno `deepgravity` Python 3.8. Cada comando se ejecuta desde la raíz del repositorio y rechaza reemplazar productos ya materializados cuando corresponde.

Se preservan los hashes del código usado en cada ejecución. Las aclaraciones posteriores del diccionario y del punto de entrada `build` no alteraron los CSV existentes. La publicación inicial requirió completar un movimiento de directorio en Windows después de terminar los cálculos; los archivos publicados y sus hashes fueron verificados posteriormente por la integración.
