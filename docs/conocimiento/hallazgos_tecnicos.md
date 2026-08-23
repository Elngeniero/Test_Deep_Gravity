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

---

## 5. Estado del Análisis XAI (Agosto 2026)

### Hallazgo: XAI no está implementado en el código base

Verificado el 23 de agosto de 2026. **No existe ningún código de análisis XAI** (SHAP, Integrated Gradients, ni ninguna otra técnica de atribución) en el repositorio. La búsqueda en todos los archivos `.py` no encontró referencias a `shap`, `captum`, `integrated_gradients`, `xai`, ni `explainab`.

> **Nota:** `shapely` aparece importado en `deepgravity.py` — es la biblioteca geoespacial de Python, sin ninguna relación con la biblioteca SHAP de explicabilidad.

### Compatibilidad: la arquitectura YA es apta para XAI sin modificaciones

| Aspecto | Situación |
|---|---|
| `NN_MultinomialRegression` es `nn.Module` puro | ✅ SHAP (`GradientExplainer`) y Captum (`IntegratedGradients`) operan directamente sobre él |
| `forward(vX)` → escalar | ✅ Interfaz exacta que esperan ambas bibliotecas |
| Checkpoint `.pt` guardado post-entrenamiento | ✅ El análisis XAI puede correr sin reentrenar el modelo |
| `model.eval()` ya existe en `evaluate()` | ✅ Desactiva el dropout antes de correr atribuciones |

### ⚠️ Precaución: Dropout activo en `forward()`

El modelo tiene **Dropout(p=0.35) en las 15 capas**. Si se corre SHAP o Integrated Gradients con `model.train()` activo, el dropout aleatoriza las atribuciones en cada llamada, produciendo resultados inestables. **Siempre llamar `model.eval()` antes de cualquier análisis XAI.**

### Lo que hay que construir para Fase 5

Se requiere un script nuevo (sugerido: `deepgravity/xai_analysis.py`) con la siguiente lógica:

```
1. Cargar modelo entrenado:
       model.load_state_dict(checkpoint['model_state_dict'])
       model.eval()

2. SHAP Global (importancia por categoría OSM):
       explainer = shap.GradientExplainer(model, background_tensor)
       shap_values = explainer.shap_values(input_tensor)
       → agregar por las 39 features → importancia por categoría

3. Integrated Gradients Local (atribución por par OD específico):
       ig = captum.attr.IntegratedGradients(model.forward)
       attributions = ig.attribute(input_od, baseline_od, n_steps=200)
       → análisis de pares de interés (ej. periferia → centro)

4. Visualización:
       → heatmap de importancia por categoría OSM (global)
       → mapa coroplético de Santiago por importancia SHAP por zona
```

### Dependencias de Fase 5

El análisis XAI requiere que primero se complete:
- **Fase 3:** Pipeline de datos Santiago (DTPM → grilla → OD) 
- **Fase 4:** Entrenamiento del modelo Deep Gravity sobre Santiago → checkpoint `.pt`

Solo entonces es posible correr el análisis XAI con datos reales de Santiago.

### Librerías a instalar para XAI

```bash
pip install shap          # SHAP (GradientExplainer para PyTorch)
pip install captum        # Integrated Gradients (Facebook/Meta, nativo PyTorch)
pip install matplotlib seaborn geopandas  # visualización
```

