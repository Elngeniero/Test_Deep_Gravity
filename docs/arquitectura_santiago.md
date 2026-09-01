# Arquitectura del Pipeline: Modelo Deep Gravity para Santiago

Este documento describe la arquitectura técnica, el flujo de datos y el diseño del pipeline de procesamiento para la tesis de grado. Su objetivo es implementar, adaptar y evaluar el modelo *Deep Gravity* en el Gran Santiago mediante una estrategia metodológica de **doble modelo comparativo** (unidades zonales irregulares vs. grilla regular hexagonal H3).

> [!NOTE]
> Para consultar la auditoría técnica del repositorio base original (código de autores con dataset de Nueva York), revisar [`architecture.md`](./architecture.md).
> Las decisiones arquitectónicas formales que sustentan este diseño se encuentran registradas en [`docs/adr/`](./adr/) (ADR-001 a ADR-005).

---

## 1. Visión General del Sistema

El pipeline aborda la estimación de matrices Origen-Destino (OD) intra-urbanas y el análisis de interacción espacial mediante un diseño comparativo multiescalar:

```
+-----------------------------------------------------------------------------------+
|                           FUENTES DE ENTRADA METROPOLITANA                        |
|   1. Transacciones DTPM Nov 2024 (Viajes/Etapas bip! con UTM x_subida, y_subida)  |
|   2. OpenStreetMap (Geometrías VGI -> 12 Macro-categorías funcionales)           |
|   3. Datos Demográficos (Censo)                                                   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                 DELIMITACIÓN TERRITORIAL (ADR-005: Gran Santiago Urbano)          |
|                 Filtrado a ~33 comunas con cobertura densa de Red/Metro          |
+-----------------------------------------------------------------------------------+
                                         |
            +----------------------------+----------------------------+
            |                                                         |
            v                                                         v
+---------------------------------------+ +-----------------------------------------+
|     MODELO 1: ZONAL CONTROL (ADR-004) | |    MODELO 2: GRILLA HEXAGONAL H3 (PROP) |
| - Unidad: Teselación 777 DTPM (~743z) | | - Unidad: Grilla Uber H3 (res. 3 a 8)   |
| - Polígonos irregulares (control)     | | - Geometría regular e isotrópica        |
| - Asignación: zona_subida/bajada      | | - Asignación directa: UTM -> H3 cell    |
| - Réplica de Vicente Mackenzie (2026) | | - Fallback: proporción de superficie    |
+---------------------------------------+ +-----------------------------------------+
            |                                                         |
            v                                                         v
+---------------------------------------+ +-----------------------------------------+
|     EXTRACCIÓN FEATURES OSM (M1)      | |      EXTRACCIÓN FEATURES OSM (M2)       |
| 12 densidades funcionales por zona    | | 12 densidades funcionales por hexágono  |
+---------------------------------------+ +-----------------------------------------+
            |                                                         |
            +----------------------------+----------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|               ARQUITECTURA NEURONAL: DEEP GRAVITY (15 capas Feed-Forward)         |
|   - Vector entrada (27 dims): 12 POIs Orig + 12 POIs Dest + Pop_O + Pop_D + Dist  |
|   - Capas ocultas: 6 x 256 + 9 x 128 (LeakyReLU + BatchNorm + Dropout)           |
|   - Softmax Generalizado (Single Tile continuo sobre Gran Santiago)               |
|   - Negative Sampling (512 muestras negativas por flujo positivo)                 |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        EVALUACIÓN COMPARATIVA Y EXPLICABILIDAD                    |
|   1. Métrica CPC: Comparativa multitemporal (Punta Mañana, Valle, Tarde)          |
|   2. XAI con SHAP: Comparativa de atribución (¿H3 mitiga el sesgo de origen?)     |
+-----------------------------------------------------------------------------------+
```

---

## 2. Fuentes de Datos (*Ground Truth*)

A diferencia de los modelos analíticos basados en la histórica Encuesta Origen-Destino 2012, este trabajo explota registros de validación pasiva post-pandemia de alta resolución.

- **Proveedor Institucional:** Directorio de Transporte Público Metropolitano (DTPM).
- **Período de Ingesta:** Noviembre de 2024 (muestra consolidada de días laborales tipo y fines de semana).
- **Archivos Base:**
  - `viajes.csv` (~3.6M de registros): Viajes completos consolidados tras algoritmos de encadenamiento (*trip chaining*) y factores de expansión institucional.
  - `etapas.csv` (~1.5M de registros): Transacciones unitarias por etapa de viaje en buses Red, Metro y Tren Nos.
- **Campos Espaciales Clave:**
  - Coordenadas proyectadas UTM (`x_subida`, `y_subida`, `x_bajada`, `y_bajada` en EPSG:32719 / WGS84 UTM 19S).
  - Unidades zonales DTPM (`zona_subida`, `zona_bajada`, `comuna_subida`, `comuna_bajada`).
- **Antecedente Directo:** Vicente Mackenzie (2026) procesó jornadas de validación DTPM 2025 sobre 743 zonas 777, reportando un CPC máximo de 0.2566 en periodo valle y evidenciando una dependencia casi exclusiva del vector de origen en SHAP. Su resultado se toma formalmente como la línea base de control (Modelo 1).

---

## 3. Delimitación del Área de Estudio (ADR-005)

Para evitar distorsiones matemáticas por **esparsidad extrema** en zonas rurales o periféricas sin cobertura formal de transporte público, el área de análisis se restringe al **Gran Santiago urbano**:

- **Criterio de Inclusión:** Comunas que forman parte del continuo urbano metropolitano con servicios activos de Red Movilidad / Metro y densidad transaccional estadísticamente significativa.
- **Comunas Nucleares (~33 comunas):** Santiago, Providencia, Las Condes, Ñuñoa, Vitacura, Lo Barnechea, La Reina, Peñalolén, Macul, San Joaquín, La Granja, La Florida, Puente Alto, San Bernardo, El Bosque, Pedro Aguirre Cerda, Lo Espejo, La Cisterna, San Miguel, Estación Central, Quinta Normal, Independencia, Recoleta, Conchalí, Huechuraba, Pudahuel, Lo Prado, Cerrillos, Maipú, Quilicura, Renca, Cerro Navia, La Pintana.
- **Implementación:** Las coordenadas y centroides se filtran espacialmente mediante un polígono de recorte (*bounding clip*) construido a partir de la cartografía oficial.

---

## 4. Unidades Espaciales y Estrategia Experimental

El núcleo de la contribución metodológica reside en contrastar el impacto de la partición espacial sobre el aprendizaje de la red:

### Modelo 1 (Control): Teselación 777 Zonal DTPM
- **Naturaleza:** Polígonos irregulares heterogéneos diseñados con criterios de zonificación operativa de transporte.
- **Cardinalidad:** ~743 zonas operativas urbanas.
- **Propósito:** Replicar de forma controlada el enfoque clásico y el trabajo previo de Vicente (2026) para medir el impacto intrínseco de la geometría irregular.

### Modelo 2 (Propuesto): Grilla Hexagonal Regular Uber H3
- **Naturaleza:** Sistema de teselación discreta global basado en hexágonos regulares jerárquicos (Uber H3).
- **Resoluciones en evaluación:** Niveles H3 **3 a 8** (con foco exploratorio en las resoluciones que equilibran granularidad urbana y esparsidad computacional, ej. H3 res. 7 ~1.2 km de radio, res. 8 ~460 m).
- **Ventajas teóricas:**
  1. *Isotropía de vecindad:* Cada celda posee exactamente 6 vecinos equidistantes con idéntica distancia inter-centroide, eliminando la asimetría diagonal de las grillas cuadradas.
  2. *Invarianza de escala y área:* Todas las celdas comparten idéntica superficie nominal en una resolución dada, anulando el sesgo de agregación espacial (MAUP).
  3. *Indexación eficiente:* Indexación geoespacial directa de 64 bits mediante la librería `h3-py`.

### Modelo 0 (Baseline opcional): Nivel Comunal
- Agregación macroscópica a nivel de comunas administrativas del Gran Santiago para visualización gerencial e interpretación institucional.

---

## 5. Características Espaciales (*Urban Features*)

Deep Gravity modula la interacción origen-destino incorporando la oferta de infraestructura y descriptores del entorno construido extraídos desde OpenStreetMap (OSM).

### Ontología Consolidada (12 Macro-Categorías Funcionales)
Para prevenir el problema de la matriz rala (*feature sparsity*) derivado de un exceso de etiquetas vacías en celdas periféricas, se adopta una consolidación en 12 dimensiones funcionales:

| ID | Macro-Categoría | Entidades OSM Representativas |
|---|---|---|
| 1 | `residential_bldg` | `building=residential, apartments, house` |
| 2 | `commercial_bldg` | `building=commercial, office` |
| 3 | `industrial_bldg` | `building=industrial, warehouse` |
| 4 | `leisure` | `leisure=park, sports_centre, pitch, garden` |
| 5 | `edu` | `amenity=school, university, college, kindergarten` |
| 6 | `food` | `amenity=restaurant, cafe, fast_food, bar` |
| 7 | `health` | `amenity=hospital, clinic, pharmacy, doctors` |
| 8 | `retail` | `shop=supermarket, mall, department_store, convenience; amenity=bank` |
| 9 | `transport` | `public_transport=platform, stop_position, station; highway=bus_stop` |
| 10 | `main_roads` | `highway=motorway, trunk, primary` (longitud en km) |
| 11 | `secondary_roads` | `highway=secondary, tertiary` (longitud en km) |
| 12 | `other` | Equipamientos institucionales y servicios menores |

### Normalización y Construcción de Tensores
- **Densificación Superficial:** Para cada celda $z$ (sea zona 777 o celda H3), los conteos brutos se transforman en densidades por kilómetro cuadrado:
  $$X_{k,z} = \frac{\sum_{i \in z} \mathbb{I}_k(\text{POI}_i)}{A_z}$$
  donde $A_z$ es el área métrica exacta calculada tras proyectar las geometrías a EPSG:32719.
- **Vector de Entrada al MLP (27 dimensiones):**
  $$\mathbf{x}_{ij} = \big[ \text{Pop}_i,\, \text{Pop}_j,\, d_{ij},\, \mathbf{X}_i^{(1..12)},\, \mathbf{X}_j^{(1..12)} \big]$$
  donde $\text{Pop}_i, \text{Pop}_j$ corresponden a la masa censal (Censo INE), $d_{ij}$ es la distancia euclidiana/geodésica inter-centroides, y $\mathbf{X}_i, \mathbf{X}_j$ son las 12 densidades funcionales de origen y destino respectivamente.

---

## 6. Pipeline de Preprocesamiento de Datos

El flujo de ingeniería de datos se implementa en dos ramas concurrentes para garantizar coherencia en la evaluación comparativa:

```
[CSV viajes.csv / etapas.csv]
          |
          +---> FILTRO DE CALIDAD (Coordenadas no nulas, factor_expansion > 0)
          |
          +---> RECORTE GEOGRÁFICO: Clip Gran Santiago (ADR-005)
          |
          +---+---------------------------------------------------------+
              |                                                         |
    [Rama Modelo 2: H3]                                       [Rama Modelo 1: 777]
              |                                                         |
  Estrategia A (Principal):                                  Agregación por campos:
  Reproyección UTM -> WGS84                                  - zona_subida (origen i)
  Asignación: h3.latlng_to_cell(lat, lon, res)               - zona_bajada (destino j)
  Calculo directo de flujos T_ij (sin redistribución)                   |
  [Fallback B: Redistribución por proporción de superficie]             |
              |                                                         |
              +----------------------------+----------------------------+
                                           |
                                           v
                         GENERACIÓN DE ARTIFACTOS CORE
    1. flows_oa.csv.zip (i, j, T_ij expandido)
    2. features.csv (ID celda, Pop, 12 features OSM)
    3. Caché de soporte: oa2features.pkl, od2flow.pkl, oa2centroid.pkl
```

---

## 7. Refactorización Técnica y Corrección del Código Base

Antes de ejecutar el entrenamiento sobre los datasets de Santiago, se aplican las siguientes correcciones sobre el repositorio base:

1. **Fix bug serialización (`utils.py:106`):**
   - *Problema:* El código original almacena `oa2centroid` dentro del archivo `od2flow.pkl`.
   - *Solución:* Serializar la estructura correcta `od2flow` en su archivo respectivo.
2. **Reactivación del generador de soporte:**
   - Descomentar la llamada a `_compute_support_files` en `load_data()` para permitir la creación automática de los archivos `.pkl` indexados para Santiago.
3. **Corrección del loop de evaluación (`main.py:144`):**
   - Eliminar el `break` residual en la iteración sobre `test_loader` para permitir el cálculo del CPC acumulado completo sobre todas las particiones de prueba.
4. **Integración de dependencias geoespaciales:**
   - Incorporación de la librería `h3-py` (`h3`) y `geopandas` en el entorno de ejecución para el soporte nativo de la teselación hexagonal.

---

## 8. Módulo de Explicabilidad y Validación Experimental

La fase de validación científica contrasta ambos modelos en múltiples escenarios temporales:

### Protocolo de Evaluación Cuantitativa
- **Escenarios Horarios:**
  1. *Punta Mañana (07:00 - 09:00):* Flujos masivos y rígidos de trabajo/estudio hacia el cono oriente y centro.
  2. *Periodo Valle (10:00 - 16:00):* Movilidad dispersa y discrecional orientada a comercio, salud y trámites.
  3. *Punta Tarde (18:00 - 20:00):* Flujos de retorno con alta sensibilidad a la fricción de distancia.
- **Métrica Primaria:** Common Part of Commuters (CPC) contra matrices de viajes expandidos reales de la tarjeta bip!:
  $$\text{CPC}(\mathbf{y}^r, \hat{\mathbf{y}}) = \frac{2 \sum_{i,j} \min(y_{ij}^r, \hat{y}_{ij})}{\sum_{i,j} y_{ij}^r + \sum_{i,j} \hat{y}_{ij}}$$
- **Líneas Base de Comparación:** Modelo Gravitacional Clásico Exponencial (Singly-Constrained con calibración de $\beta$ por Grid Search) y Modelo de Radiación.

### Análisis XAI con SHAP (Testeo de Hipótesis)
- Se calculan los valores SHAP (*SHapley Additive exPlanations*) sobre el ensamble de predicciones para cada periodo horario.
- **Hipótesis Experimental Central:**
  - En el **Modelo 1 (Zona 777)** se espera replicar el sesgo de Vicente (2026), donde las variables de infraestructura del origen dominan el ranking de impacto y las del destino resultan marginales.
  - En el **Modelo 2 (Grilla Hexagonal H3)** se evaluará si la regularidad geométrica e isotrópica permite que los atractores de destino (comercio, salud, educación, retail) eleven su contribución relativa en SHAP, demostrando que la morfología urbana fina sí aporta señal predictiva real cuando se utiliza una discretización espacial homogénea.
