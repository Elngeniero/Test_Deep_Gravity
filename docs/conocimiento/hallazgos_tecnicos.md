# Hallazgos Técnicos

Registro de hallazgos, bugs y notas técnicas acumuladas durante el desarrollo del proyecto.

---

## 1. Bugs Conocidos en el Código Base (DeepGravity)

Identificados durante la auditoría técnica. Ver detalles completos en [`architecture.md`](../architecture.md).

### Bug 1 — Serialización incorrecta (`utils.py:106`)
- **Descripción:** La función `_compute_support_files` guarda `oa2centroid` en el archivo `od2flow.pkl` en lugar de guardar `od2flow`.
- **Impacto:** El archivo `od2flow.pkl` queda corrupto; el pipeline falla al intentar cargar los flujos desde caché.
- **Fix requerido:** Cambiar `pickle.dump(oa2centroid, handle)` → `pickle.dump(od2flow, handle)` en la línea 106 de `utils.py`.

### Bug 2 — `_compute_support_files` comentada (`utils.py:136-137`)
- **Descripción:** La llamada a `_compute_support_files` está comentada en `load_data()`. Si la carpeta `processed/` no existe o está desactualizada, el pipeline falla con `FileNotFoundError`.
- **Impacto:** Para Santiago (sin `processed/` pre-generado), el pipeline no puede arrancar.
- **Fix requerido:** Descomentar y condicionar la llamada: ejecutar `_compute_support_files` si los archivos `.pkl` no existen.

### Bug 3 — `break` en el test loop (`main.py:144`)
- **Descripción:** El loop de evaluación durante el entrenamiento tiene un `break` que detiene la iteración tras el primer batch del `test_loader`.
- **Impacto:** El CPC reportado durante el entrenamiento es **no representativo** (solo evalúa una fracción del set de test). El CPC oficial y correcto se obtiene desde `evaluate()`, que no tiene este problema.
- **Fix requerido:** Eliminar el `break` en `main.py:144` para que el test loop evalúe todos los batches.

---

## 2. Notas sobre el Dataset DTPM (Noviembre 2024)

### Archivos disponibles

| Archivo | Registros | Tamaño | Descripción |
|---|---|---|---|
| `2024-11-27.viajes.csv` | ~3.6M | ~1.5 GB | Viajes completos |
| `2024-11-27.etapas.csv` | ~1.5M | ~440 MB | Etapas por validación |

### Campos clave para el pipeline

- **Coordenadas de origen:** `x_subida` (UTM Este), `y_subida` (UTM Norte) — para asignar el viaje a la celda de la grilla.
- **Coordenadas de destino:** `x_bajada` (UTM Este), `y_bajada` (UTM Norte).
- **Zonificación administrativa:** `comuna_inicio_viaje`, `comuna_fin_viaje` — para visualización complementaria.
- **Factor de expansión:** `factor_expansion` — debe aplicarse al agregar flujos para que representen la demanda real expandida.

### Distribución de modos
| Modo | Participación |
|---|---|
| Metro | ~48.2% |
| Buses | ~40.1% |
| Zona Paga | ~10.2% |
| Metrotren | ~1.5% |

### Limitación principal
Los viajes caminados, en taxi/colectivo de pago en efectivo y en modos no motorizados **no están registrados** en el dataset.

---

## 3. Estado de la Bibliografía (Agosto 2026)

### Fuentes disponibles (11 archivos markdown en `Fuentes/markdown/`)

| Paper | Año | Usado en |
|---|---|---|
| Zipf — P1P2/D Hypothesis | 1946 | Marco Conceptual, Trabajo Relacionado |
| Stouffer — Intervening Opportunities | 1940 | Marco Conceptual, Trabajo Relacionado |
| Simini et al. — Universal model (Radiación) | 2012 | Marco Conceptual, Trabajo Relacionado |
| González et al. — Individual mobility patterns | 2008 | Trabajo Relacionado |
| Simini et al. — Continuum approach | 2013 | Trabajo Relacionado |
| Simini et al. — Deep Gravity | 2021 | Marco Conceptual, Trabajo Relacionado |
| Rong, Ding & Li — Interdisciplinary Survey | 2024 | Marco Conceptual, Trabajo Relacionado |
| Rong et al. — GlODGen (Satellites) | 2024 | Trabajo Relacionado |
| Luca et al. — TS-Mob | 2024 | Marco Conceptual, Trabajo Relacionado |
| Memoria Angélica García | 2025 | Referencia de estilo y estructura |
| Memoria Gabriela Paz | 2025 | Referencia de estilo y estructura |

### Entradas en `bibliografia.bib` (14 entradas de la memoria)

`simini2021deep`, `simini2012universal`, `liu2024interdisciplinary`, `lundberg2017shap`, `zipf1946p`, `stouffer1940intervening`, `pappalardo2023scikitmobility`, `openstreetmap`, `dtpm_informe`, `BarringtonLeigh2017`, `haklay2008openstreetmap`, `sundararajan2017axiomatic`, `luca2024tsmob`, `gonzalez2008understanding`, `simini2013human`, `rong2024satellites`.

---

## 4. Resultado Experimental: Reproducción Nueva York

- **Modelo:** Deep Gravity (15 capas FF, PyTorch, RMSprop lr=5e-6)
- **Dataset:** New York (repositorio original)
- **CPC obtenido:** **0.5119**
- **CPC reportado en el paper:** 0.51
- **Estado:** ✅ Reproducción exitosa. Ver reporte completo en [`experimentos/REPORTE_REPRODUCCION_NEWYORK.md`](../experimentos/REPORTE_REPRODUCCION_NEWYORK.md).
