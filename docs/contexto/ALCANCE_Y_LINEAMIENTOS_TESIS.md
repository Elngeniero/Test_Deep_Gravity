# Definicion del Problema y Objetivos de la Memoria

> **Titulo de la memoria**: *Generacion de flujos de movilidad en Santiago de Chile mediante Deep Gravity: evaluacion del impacto de las amenities de OpenStreetMap y analisis mediante XAI*.
>
> Este documento perfila la definicion del problema que motivate la memoria, los actores involucrados, las consecuencias de no resolverlo, la competencia existente y los objetivos y alcances. Se enfoca en **definir el problema**, no en describir la solucion.

## 1. Contexto

- **Donde**: Santiago de Chile, capital de la Region Metropolitana, ciudad de aproximadamente 7 millones de habitantes y con uno de los sistemas de transporte urbano mas complejos de America Latina (Transantiago / RED, Metro, Buses, tren Rancagua, taxis colectivos).
- **Linea de trabajo**: Movilidad urbana y ciencia de datos espaciales, en la interseccion entre el transporte, el aprendizaje profundo y los sistemas de informacion geografica voluntaria (VGI, por OpenStreetMap).
- **Momento**: Periodo post-pandemia (datos de noviembre 2024), en el cual los patrones de movilidad han cambiado respecto a los modelos pre-2020 (teletrabajo, redistribucion de viajes, caida de viajes al centro).
- **Marco academico**: La memoria se inscribe en la linea de Inteligencia Artificial aplicada a la ciudad, y se apoya en el modelo *Deep Gravity* propuesto por Simini et al. (Nature Communications, 2021), que ha demostrado superar al *gravity model* clasico y al *radiation model* en Inglaterra, Italia y el estado de Nueva York, pero que **no ha sido validado en una metropolis latinoamericana** ni sobre datos pospandemicos.

## 2. Qué y cómo se realiza actualmente la situación

- **Actualmente la planificacion del transporte en Santiago se apoya en**:
    - La **Encuesta Origen-Destino (EOD)** de SECTRA, cuya ultima version publicada es la EOD 2012 (con actualizaciones 2017), realizada por muestreo domiciliario, con una periodicidad de 7 a 10 anos y un costo elevado.
    - Datos anonimizados de **tarjeta bip!** (DTPM), que registran validaciones en Metro y buses, pero que no cubren etapas caminadas, viajes en taxi/colectivo pago en efectivo, ni modos no motorizados.
    - Modelos de **asignacion y distribucion de viajes** (ej. Strategic Transit Model de DTPM), basados en grillas de zonas de analisis (ZAT) y en modelos de gravedad calibrados.
- **En el ambito de generacion de flujos** (predecir flujos entre pares de zonas sinobservarlos directamente), Santiago no cuenta con un modelo que:
    - Explota las **amenities geograficas de OpenStreetMap** (POIs, uso de suelo, red vial, equipamiento) como variables explicativas.
    - Utiliza **redes neuronales profundas** para capturar relaciones no lineales entre el tejido urbano y los viajes.
    - Proporciona **explicabilidad** (XAI) que permita a planificadores entender que factores impulsan cada prediccion.
- **El Departamento de Transporte** cuenta con un dataset de **viajes y etapas de todo el mes de noviembre de 2024**, de mayor resolucion temporal y amplitud que la EOD, pero cuya explotacion para generacion de flujos con aprendizaje profundo no se ha realizado.

## 3. Actores y usuarios involucrados

- **Actores primarios** (quienes usarian el modelo y sus resultados):
    - **DTPM (Directorio de Transporte Publico Metropolitano)** y **SECTRA (Secretaria de Planificacion del Transporte)**: organismos publicos responsables de planificar y regular el transporte metropolitano.
    - **Ministerio de Transportes y Telecomunicaciones (MTT)**: nivel decisional nacional.
    - **Municipalidades y mancomunidades** (ej. Santiago Centro, Providencia, Las Condes): requiren estimaciones de flujo para infraestructura local, ciclovias, permisos de circulacion.
    - **Investigadores academico en movilidad urbana, ciencia urbana y transporte sostenible** en universidades chilenas (PUC, Universidad de Chile, Universidad Adolfo Ibanez).
- **Actores secundarios** (beneficiados indirectos):
    - **Empresas de movilidad** (Moovit, Uber, Cabify, scooters) para benchmarking de demanda.
    - **Consultoras de transporte** (Movilidad sostenible, modelacion de impacto) que rinden cuentas a la DTPM.
    - **Ciudadania** en general, por mejores decisiones de inversion en infraestructura.

## 4. Dificultades actuales de esos actores

- **Volatilidad post-pandemia**: los modelos pre-pandemia son invalidos para la distribucion de viajes pospandemica; los datos EOD estan desactualizados frente a los cambios en el teletrabajo, la desconcentracion de empleos y la caida del uso de Metro (validaciones de 2024 aun por debajo de 2019).
- **Costo y periodicidad de la EOD**: una nueva EOD cuesta varios millones de dolares y solo se levanta cada 7-10 anos; los hacedores de politica publica necesitan estimaciones intermedias.
- **Cobertura de tarjetas bip!**: estan ausentes viajes no motorizados (caminata, bicicleta) y viajes en modo taxi/colectivo pago en efectivo, que son relevantes en sectores perifericos.
- **Modelos de gravedad clasicos** (los unicos implementados a escala metropolitana):
    - **Underfitting**: imponen una relacion parametrica monotona entre poblacion, distancia y flujo, incapaces de capturar efectos no lineales (ej. hubs de empleo secundarios, corredores de transporte masivo).
    - **Overdispersion**: la varianza empirica de los flujos supera la prevista por el modelo.
    - **Ignoran el tejido urbano**: no incorporan amenities, POIs, uso de suelo ni red vial, a pesar de ser variables determinantes.
- **Falta de explicabilidad**: los modelos actuales de distribucion de viajes son cajas negras dificiles de auditar; un planificador no puede responder a **por que** un par de zonas atrae mas viajes.
- **Escasez de modelos de generacion para America Latina**: apenas hay literatura que valide modelos neuronales de flujos sobre ciudades latinoamericanas con datos VGI, que ademas presentan **cobertura heterogenea de OSM** (densidad de POIs concentrada en barrios de ingresos medios-altos).
- **Cuantificacion del mercado**: en Chile existen al menos **3 organismos publicos** (DTPM, SECTRA, MTT), **52 municipalidades** de la Region Metropolitana, y **mas de 10 centros universitarios** con lineas de movilidad que podrian usar un modelo de generacion de flujos explicativo. A nivel regional, las capitales latinoamericanas con problemas similares (Lima, Bogota, Buenos Aires, Ciudad de Mexico, Sao Paulo) suman mas de **50 millones de habitantes**, lo que justifica la transferabilidad del trabajo.

## 5. Que pasaria si no se solucionan estas dificultades

- **Decisiones de inversion con datos caducados**: nuevas lineas de Metro, extensiones de BRT, redes de ciclovias y planes de densificacion se disenarian sobre la EOD 2012/2017, sin reflejar la redistribucion post-pandemica de la demanda (por ejemplo, debilitamiento del viaje al centro historico y fortalecimiento de subcentros como Providencia, Sanhattan, ENEA / Ciudad Empresarial).
- **Perdida de oportunidades de planificacion proactiva**: los modelos de gravedad clasicos no permiten anticipar el impacto de intervenciones urbanas (apertura de un mall, cierre de un eje, nueva estacion) sobre los flujos.
- **Opacidad en la decision publica**: sin un modelo explicativo, las autoridades y la ciudadania no pueden auditar la razon de una prediccion; esto baja la confianza en la planificacion.
- **Brecha metodologica**: la investigacion chilena en movilidad quedaria rezagada frente al state-of-the-art internacional (DeepGravity, modelos de flujos con GNNs, etc.), perdiendo la oportunidad de producir hallazgos sobre la especificidad latinoamericana (segregacion socioespacial, informalidad, polarizacion centro-periferia) que los modelos entrenados en el Norte Global no capturan.
- **Aprovechamiento deficiente de datos administrativos existentes**: el dataset del DTPM (noviembre 2024) permanece subutilizado para modelado de generacion, lo que representa una perdida de retorno a la inversion public en su levantamiento.

## 6. Competencia y soluciones existentes

- **Gravity model clasico** (Zipf, 1946): modelo *de facto* en la planificacion del transporte. Sirve como **baseline** dentro de esta memoria, pero no captura no-linealidades ni usa VGI.
- **Radiation model** (Simini et al., 2012): modelo sin parametros que Arnold et al. y otros han probado en ciudades; **serviria como segundo baseline**. Supera al gravity en algunos casos, pero aporta explicabilidad limitada y tampoco usa amenities.
- **Deep Gravity** (Simini et al., 2021): estado del arte sobre UK/IT/NY, pero **validado solo en ciudades del Norte Global, con datos pre-pandemicos y sin extension a Santiago**. Su codigo (el repositorio base de esta memoria) es un artefacto de investigacion sin empaquetado, sin tests y sin XAI, lo que limita su adopcion fuera del equipo original.
- **Modelos con GNNs espaciales** (ej. GEML, Prophet en variantes): mas recientes, pero requieren grafos de movilidad con estructura administrativa y no se han aplicado a Santiago.
- **Modelos de distribucion de viajes propios de SECTRA/DTPM**: calibrados con correcciones localmente, pero lineales y opacos para fines explicativos.
- **Por que esta memoria aporta algo mejor**:
    - Primer aplicacion de DeepGravity sobre una metropolis latinoamericana con datos post-pandemicos.
    - Integracion de **baselines** (gravity + radiation) que aislan la contribucion del aprendizaje profundo.
    - **Capa de explicabilidad multiple** (SHAP + Integrated Gradients + analisis de sensibilidad) sobre el tejido urbano (amenities/POIs), que falta tanto en Deep Gravity original como en los modelos vigentes en Santiago.
    -     - Estudio de la **incidencia de la calidad/cobertura de OSM en Santiago**, un fenomeno latinoamericano poco documentado en la literatura.

## 7. Objetivos de la memoria

### 7.1 Objetivo general

- **Estudiar empiricamente** en que medida la incorporacion de amenities geograficas de OpenStreetMap, mediante el modelo Deep Gravity, mejora la prediccion de flujos de movilidad en Santiago de Chile respecto a modelos de gravedad y radiation, y **interpretar** la contribucion de cada tipologia de amenity al desempeno del modelo mediante tecnicas de explicabilidad.

### 7.2 Objetivos especificos

1. **Reproducir** el modelo Deep Gravity sobre el dataset de referencia New York del repositorio original, como linea base de validacion del pipeline y de las metricas (CPC) reportadas en el paper.
2. **Caracterizar** el dataset de viajes y etapas de noviembre 2024 del DTPM, construyendo una tessellation cuadrada para Santiago (sensibilidad de grilla: varios tamanos a probar, ej. 500 m, 1 km, 2 km, 5 km).
3. **Extraer** las amenities de OpenStreetMap para el area de estudio, primero con el set de **18 features del paper original** (uso de suelo, red vial, transporte, comida, salud, educacion, retail, poblacion, distancia) y luego evaluar la pertinencia de un set adaptado a contextos latinoamericanos.
4. **Entrenar y evaluar** Deep Gravity sobre Santiago, con dos **baselines**:
    - **Gravity model** (regresion lineal log-transformada sobre poblaciones y distancia).
    - **Radiation model** (Simini et al., 2012).
   Comparar cuantitativamente por CPC y por descomposicion por tile.
5. **Cuantificar el impacto** de las amenities mediante **XAI**:
    - **SHAP** (Kernel y Deep) para la importancia global y local de cada feature.
    - **Integrated Gradients** para la atribucion por par (o,d).
    - **Analisis de sensibilidad** por feature (perturbacion de amenity, efecto en CPC).
6. **Comparar** la importancia relativa de las amenities entre Santiago y New York, y discutir las diferencias a la luz del tejido urbano y la cobertura de OSM.
7. **Documentar** el proceso de adaptacion del repositorio DeepGravity, incluyendo el refactor necesario para importar correctamente como paquete y la generacion reproducible de `processed/`.

## 8. Alcances y limitaciones

### 8.1 Alcances

- **Area geografica**: Gran Santiago (comunas del area metropolitana del DTPM), eventualmente extension a Region Metropolitana completa.
- **Periodo**: Noviembre 2024 (post-pandemia).
- **Modos de transporte**: los presentes en el dataset del DTPM (todos los modos registrados a nivel de viaje/etapa).
- **Modelos cubiertos**: Deep Gravity (modelo principal), gravity model clasico y radiation model (baselines).
- **Features de entrada**: set del paper + extension a definir para Santiago.
- **Tecnicas XAI**: SHAP (Kernel + Deep), Integrated Gradients, analisis de sensibilidad.

### 8.2 Fuera de alcance

- **Prediccion temporal** (forecasting): el modelo es de generacion espacial de flujos en un corte temporal, no de proyeccion futura.
- **Calibracion de politicas publicas**: se entregan insumos, no recomendaciones operativas.
- **Datos de telecom**: no se usaran trazas de operadores.
- **Modos no observados por el dataset**: no se cubren viajes no detectados por el DTPM.
- **Otros modelos neuronales**: no se implementaran GNNs ni transformers espaciales; el alcance se limita a Deep Gravity y sus baselines clasicos.

## 9. Decisiones metodologicas preeliminares

- **Tessellation**: grilla cuadrada, con tamanos a calibrar. Se testearan 500 m, 1 km, 2 km y 5 km; se reportara la sensibilidad.
- **Baselines**: gravity model (lineal log-log) y radiation model; ambos se implementaran o adaptaran en el mismo pipeline.
- **Features**: arranque con las **18 del paper** sobre Santiago; una segunda fase evaluara extension con amenities especificas de la realidad chilena (ferias libres, postas rurales, templos religiosos, juegos infantiles, sitios eriazos, etc.).
- **Fuente de POIs**: PostgreSQL/PostGIS con snapshot Geofabrik de Chile + queries derivados de `osm_query.yaml`; como respaldo, OSMnx y Overpass.
- **Evaluacion**: metrica principal **CPC** (Common Part of Commuters), siguiendo el paper; metricas auxiliares a definir (RMSE, Sorensen-Dice, MAE normalizado).
- **XAI**: prioridad SHAP por madurez y documentacion; Integrated Gradients como complemento para atribuciones por par; sensibilidad como prueba de robustez.
- **Reproducibilidad**: el repositorio DeepGravity base sera refactorizado (imports, preprocesado, tests) para garantizar trazabilidad del pipeline de Santiago.

## 10. Estado Actual y Siguientes Pasos

> Ultima actualizacion: Agosto 2026

### Estado actual

- **Fase 1 (Reproduccion NY):** Completada — CPC = 0.5119, coherente con el paper.
- **Redaccion de la tesis:** Capitulos completados: Introduccion, Definicion del Problema, Marco Conceptual (Cap. 2) y Trabajo Relacionado (Cap. 3). Pendientes: Propuesta de Solucion (Cap. 4), Validacion (Cap. 5) y Conclusiones.
- **Dataset DTPM:** Los CSV completos (viajes.csv y etapas.csv de noviembre 2024) estan disponibles en el equipo del investigador. Los resumenes y diccionario de datos estan en `Fuentes/dptm/`.
- **Unidad espacial:** Definida como **tessellation cuadrada** (500m, 1km, 2km, 5km), coherente con el paper original y con los Objetivos Especificos 2 y 6 de la tesis. La grilla se generara con `skmob.tessellation.tilers`.

### Proximos pasos

1. **Redactar Capitulo 4 (Propuesta de Solucion):** Describir el pipeline tecnico completo (datos DTPM → grilla cuadrada → features OSM → Deep Gravity → SHAP). Basarse en `arquitectura_santiago.md`.
2. **Corregir bugs del codigo base:** `utils.py:106` (serializacion incorrecta), `_compute_support_files` comentada, `break` en el test loop. Ver detalles en `docs/conocimiento/hallazgos_tecnicos.md`.
3. **Construir la matriz OD:** Usar coordenadas UTM del dataset DTPM para asignar viajes a celdas de la grilla y generar `flows_oa.csv`.
4. **Extraer features OSM:** Usar `osmnx`/Overpass con `osm_query.yaml` para el Gran Santiago, generando `features.csv` con las 18 variables del paper.
5. **Ejecutar pipeline completo:** Preprocesamiento, entrenamiento (20 epocas, RMSprop), evaluacion CPC por tile.
6. **Analisis XAI:** Calcular SHAP values y comparar importancias entre resoluciones de grilla y con los resultados de Nueva York.

