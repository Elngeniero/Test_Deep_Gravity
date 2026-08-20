# Arquitectura del Pipeline: Modelo Deep Gravity para Santiago

Este documento describe la arquitectura técnica, el flujo de datos y el pipeline de procesamiento específico para la tesis. Su objetivo es adaptar el modelo base de *Deep Gravity* para predecir y explicar los flujos origen-destino (OD) en el Gran Santiago.

> [!NOTE]
> Para revisar la auditoría técnica del repositorio base (código original + dataset de Nueva York), consultar [`architecture.md`](./architecture.md).

---

## 1. Visión General del Sistema

El pipeline se compone de tres fases fundamentales:

1. **Generación del *Ground Truth*:** Transformación de los datos transaccionales de transporte público en una matriz OD observada, agregada sobre una tessellation cuadrada del Gran Santiago.
2. **Ingesta de Features Espaciales:** Extracción de atributos semánticos del tejido urbano mediante OpenStreetMap, normalizados por área de cada celda.
3. **Entrenamiento y Explicabilidad:** Alimentación de los tensores espaciales a la red *Deep Gravity* y análisis de causalidad con *SHAP*.

---

## 2. Fuentes de Datos (*Ground Truth*)

A diferencia de los modelos clásicos (que dependen de la Encuesta Origen-Destino 2012/2017), este proyecto utiliza transacciones masivas de bip!/RED para capturar la movilidad real post-pandemia.

- **Proveedor:** Directorio de Transporte Público Metropolitano (DTPM).
- **Período de Análisis:** Todo el mes de Noviembre de 2024.
- **Archivos Base:**
  - `viajes.csv` (~3.6M de registros, ~1.5 GB): Contiene la agregación de las validaciones a nivel de viaje completo.
  - `etapas.csv` (~1.5M de registros, ~440 MB): Contiene el detalle de las transacciones unitarias en los modos del sistema (Buses, Metro, Metrotren).
- **Resolución Espacial:** Los viajes contienen coordenadas UTM de subida y bajada (`x_subida`, `y_subida`, `x_bajada`, `y_bajada`), que se usarán para asignar cada viaje a la celda de la grilla cuadrada correspondiente.

---

## 3. Unidad Espacial: Tessellation Cuadrada

La unidad espacial principal es una **grilla cuadrada** generada algorítmicamente sobre el Gran Santiago, coherente con el paper original de Deep Gravity y con los Objetivos Específicos 2 y 6 de la tesis.

- **Herramienta:** `skmob.tessellation.tilers.get("squared", ...)` — no requiere shapefiles externos.
- **Resoluciones a evaluar:** 500 m, 1 km, 2 km y 5 km.
- **Análisis de sensibilidad:** Se reportará el CPC y la importancia de features (SHAP) para cada resolución, constituyendo una contribución metodológica propia.
- **Referencia complementaria:** Los resultados también se agregarán a nivel de comunas para visualización e interpretación institucional, pero el análisis principal opera sobre la grilla.

---

## 4. Características Espaciales (*Urban Features*)

El modelo *Deep Gravity* no utiliza la distancia de manera desnuda; interpola la atractividad de una zona usando las características físicas del espacio. Para Santiago, utilizaremos la estructura de datos abierta de OpenStreetMap (OSM), normalizadas por área de cada celda (features por km²).

- **Herramienta de Ingesta:** `osmnx` y consultas a Overpass API (respaldado por `osm_query.yaml`).
- **Categorías (18 features del paper original), normalizadas por km²:**
  - *Uso de suelo:* Áreas verdes, polígonos residenciales, industriales.
  - *Red vial:* Longitud total de vías, intersecciones.
  - *Transporte:* Paraderos de bus, estaciones de metro.
  - *Alimentación:* Restaurantes, supermercados.
  - *Salud:* Hospitales, farmacias.
  - *Educación:* Escuelas, universidades.
  - *Comercio/Retail:* Tiendas, centros comerciales.
- **Features adicionales:** `log(población)` por celda y distancia geodésica entre centroides.
- **Extensión latinoamericana (fase 2):** Se evaluará incorporar categorías específicas del tejido urbano chileno (ferias libres, postas, etc.).

---

## 5. Pipeline de Preprocesamiento

Para adaptar los datos a la entrada estricta del modelo original de *Deep Gravity*:

1. **Filtro y Limpieza:** Depurar el dataset `viajes.csv` eliminando registros con coordenadas UTM nulas o `factor_expansion` inválido.
2. **Asignación a la Grilla:** Usar las coordenadas UTM (`x_subida`, `y_subida`, `x_bajada`, `y_bajada`) para asignar cada extremo del viaje a la celda de la tessellation cuadrada correspondiente.
3. **Agregación:** Consolidar los viajes entre la celda $i$ (origen) y la celda $j$ (destino), sumando el volumen (con `factor_expansion`) para construir el flujo observado $T_{ij}$.
4. **Generación de Archivos Core:**
   - `flows_oa.csv.zip`: Listado de flujos observados donde cada fila representa $(i, j, T_{ij})$.
   - `features.csv`: Matriz donde cada fila es una celda de la grilla y cada columna es una variable de OSM.
5. **Generación de Archivos de Soporte:** Ejecutar `_compute_support_files` (actualmente comentado en `utils.py`) para generar los `.pkl` de caché (`oa2features`, `od2flow`, `oa2centroid`).

---

## 6. Refactorización Técnica y Ejecución

Correcciones necesarias al repositorio original antes de procesar Santiago:

1. **Fix bug serialización:** Corregir `utils.py:106` — actualmente guarda `oa2centroid` en el archivo `od2flow.pkl`; debe guardar `od2flow`.
2. **Reactivar caché:** Descomentar `_compute_support_files` en `load_data()` para permitir la regeneración de los archivos `.pkl` intermedios.
3. **Corrección del test loop:** El `break` en `main.py:144` (test_loader) hace que solo se evalúe el primer batch. Debe eliminarse para obtener CPC válido durante el entrenamiento. El CPC oficial se calcula mediante `evaluate()`.

---

## 7. Módulo de Explicabilidad (XAI)

La etapa culminante de la arquitectura es la integración de algoritmos de explicabilidad:

- **SHAP (prioridad):** Se calcularán *SHAP values* sobre la red neuronal para cada par (origen, destino), determinando la importancia global y local de cada feature de OSM.
- **Integrated Gradients (complemento):** Para atribuciones por par (o, d) específicos.
- **Análisis de sensibilidad:** Comparación de importancias SHAP entre distintas resoluciones de grilla (500m, 1km, 2km, 5km) y entre temporalidades (punta / fuera de punta).
- **Comparación Santiago vs. Nueva York:** Análisis de diferencias en importancia de features para discutir especificidades del tejido urbano latinoamericano.
