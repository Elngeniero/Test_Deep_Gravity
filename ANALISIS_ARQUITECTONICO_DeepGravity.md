# Reporte de Analisis Arquitectonico - DeepGravity

> Auditoria tecnica del repositorio `DeepGravity` (implementacion oficial del paper *Simini et al., "A Deep Gravity model for mobility flows generation", Nature Communications 12, 6576, 2021*). El reporte cubre arquitectura, stack, flujo principal, configuracion y observaciones del revisor.

## 1. Resumen Ejecutivo

- **Que es**: Implementacion oficial (scikit-mobility) del paper *Simini et al., "A Deep Gravity model for mobility flows generation", Nature Communications 12, 6576 (2021)*. DOI: 10.1038/s41467-021-26752-4.
- **Problema que resuelve**: Generacion de **flujos de movilidad humana** entre ubicaciones geograficas cuando no hay datos reales. Mejora el clasico *gravity model* sustituyendo su formulacion lineal por una **red neuronal profunda** que captura relaciones no lineales entre features geograficas y flujos.
- **Usuario final / proposito**: Investigadores en movilidad urbana, epidemiologia, planificacion territorial y data science espacial. Es **software de investigacion** (licencia CC-BY-4.0), no una aplicacion de produccion.
- **Ventaja clave**: Hasta **+250% de performance** vs. gravity model clasico en zonas densamente pobladas, con capacidad de **generalizacion** a areas sin datos de entrenamiento y **explicabilidad** via XAI.

## 2. Stack Tecnologico y Dependencias

| Componente | Version / Detalle |
|---|---|
| **Lenguaje** | Python 3.8 (verificado: `.cpython-38.pyc`) |
| **Deep Learning** | PyTorch 1.7.1 |
| **Data core** | numpy 1.19.2, pandas 1.2.4 |
| **Geoespacial** | geopandas 0.9.0, shapely, `area` |
| **Movilidad** | scikit-mobility 1.1.0 (`skmob.tessellation.tilers`) |
| **Serializacion** | pickle, gzip, zipfile, JSON |
| **Optimizador** | RMSprop (momentum 0.9, lr 5e-6) - ver `main.py:245` |
| **Metrica** | Common Part of Commuters (CPC) - `od_models.py:18` |
| **Testing/Build** | **No hay**: sin `requirements.txt`, sin `setup.py`/`pyproject.toml`, sin framework de tests, sin CI |
| **Origen de datos** | OpenStreetMap (POIs via Overpass/HOTosm/PostgreSQL), censos UK/IT/US, GeoDS COVID19USFlows |

**No hay** `package.json`, `Cargo.toml`, `go.mod`, `docker-compose.yml`, ni `.env.example`. Las dependencias estan **solo documentadas en el README**.

## 3. Arquitectura y Estructura de Directorios

```
DeepGravity/
|- README.md, CITATION.cff, osm_query.yaml, plots.ipynb
|- .gitignore  (solo 2 lineas: *.agents, *.json)
|- imgs/  (architecture.png, plot.png)
|- deepgravity/                       <- paquete principal
    |- __init__.py  (vacio)
    |- main.py     (281 lineas)     <- entry point + CLI
    |- utils.py    (198 lineas)     <- carga datos, instanciacion modelo
    |- data_loader.py (130 lineas)  <- FlowDataset (torch Dataset)
    |- models/
    |   |- od_models.py     (179)   <- clase base GLM/NN + CPC
    |   |- deepgravity.py   (218)   <- NN_MultinomialRegression (15 capas)
    |- data/
        |- new_york/                 <- dataset de ejemplo
            |- features.csv          (807 KB)
            |- output_areas.{shp,shx,dbf,prj,cpg}
            |- tessellation.{shp,...}
            |- Untitled.ipynb
            |- processed/            <- cache generado en 1ra ejecucion
                |- train_tiles.csv / test_tiles.csv  (split 192 tiles)
                |- tileid2oa2handmade_features.json  (2.7 MB)
                |- flows_oa.csv.zip, oa_gdf.csv.gz
                |- *.pkl  (oa2features, oa2centroid, od2flow)
```

**Patron arquitectonico**:

- **No MVC / Clean Architecture**: es un **script monolitico de investigacion**. `main.py` contiene CLI + orquestacion + bucle de entrenamiento + evaluacion todo junto.
- **Herencia simple**: `NN_MultinomialRegression` (`deepgravity.py:79`) extiende `NN_OriginalGravity` (`od_models.py:132`), que extiende `GLM_MultinomialRegression` (`od_models.py:28`). Cadena: `Module -> GLM -> NN_Orig -> NN_Multinomial`.
- **Carga dinamica no idiomatica**: los modulos se importan via `SourceFileLoader` con rutas relativas hardcoded (`main.py:68-71`, `utils.py:19-20`, `data_loader.py:6-7`, `deepgravity.py:16-17`) en lugar de imports normales de paquete. **Deuda tecnica importante**: acopla el CWD y rompe la instalabilidad como paquete.

## 4. Puntos de Entrada y Flujo Principal

**Entry point unico**: `deepgravity/main.py` (via `python main.py ...`).

**Flujo critico de principio a fin**:

1. **CLI parsing** (`main.py:20-56`): argparse con ~15 flags (`--dataset`, `--mode`, `--epochs`, `--device`, columnas de datos, etc.).
2. **Setup semillas y dispositivo** (`main.py:63-80`): `torch.manual_seed` / `np.random.seed` / `random.seed` = 1234; `cpu` o `cuda`.
3. **Carga dinamica** de `data_loader.py` y `utils.py` via `SourceFileLoader` (`main.py:68-71`).
4. **Validacion dataset** (`main.py:83-86`): comprueba `./data/<dataset>/`.
5. **Tessellation** (`utils.py:129` -> `main.py:186`): usa `skmob.tessellation.tilers` con `get("squared", ...)` si no hay shapefile.
6. **`load_data`** (`utils.py:134-172` -> `main.py:188-195`): carga de `processed/`:
    - `tileid2oa2handmade_features.json` (mapeo tile -> OA -> features)
    - `oa_gdf.csv.gz`, `flows_oa.csv.zip`, `oa2features.pkl`, `od2flow.pkl`, `oa2centroid.pkl`
    - `oa2pop` se deriva de `flow_df.groupby('residence').sum()`
7. **Feature engineering inline** (`main.py:197`): `oa2features[oa] = [log(pop)] + feats`.
8. **Construccion de `o2d2flow`** anidado (`main.py:199-205`).
9. **Datasets/Loaders PyTorch** (`main.py:207-235`):
    - **Train**: `dim_dests=512` (negative sampling), `frac_true_dest=0.0`
    - **Test**: `dim_dests=int(1e9)` (todos los destinos), `frac_true_dest=0.0`
    - Las IDs train/test se leen de `processed/train_tiles.csv` y `test_tiles.csv` (split por tile, no por OA - esto evita leakage espacial).
10. **`dim_input`** se calcula dinamicamente con un sample (`main.py:237`).
11. **Branch `train`** (`main.py:239-269`):
    - Instancia `NN_MultinomialRegression(dim_input, 256, 'deepgravity', dropout_p=0)` via `utils.instantiate_model`
    - Optimizer `RMSprop(lr=5e-6, momentum=0.9)`
    - `test()` previo, luego bucle epochs (20 default paper, 15 default argparse). En cada epoch resetea seeds con `seed+epoch`.
    - `train()` (`main.py:89-118`): forward/loss por cada destino en el batch, acumula `loss`, `loss.backward()`, `optimizer.step()`.
    - `test()` (`main.py:121-147`): **NOTE el `break` en linea 144** - solo evalua el primer batch del loader. Comportamiento cuestionable.
    - Guarda `results/model_DG_<dataset>.pt` (state_dict + optimizer_state_dict)
    - `evaluate()` (`main.py:150-183`): calcula CPC numerator por OA, agrupa por tile, escribe `results/tile2cpc_DG_<dataset>.csv`
12. **Branch `test`** (`main.py:272-280`): carga checkpoint y llama a `evaluate()`.

**Red neuronal** (`deepgravity.py:79-215`):

- **Arquitectura**: 15 hidden layers.
    - Capas 1-5: `Linear(dim_input->256) -> LeakyReLU -> Dropout(0)`
    - Capa 6: `Linear(256->128)`
    - Capas 7-15: `Linear(128->128)`
    - Salida: `Linear(128->1)` -> score escalar por par (o,d)
- **Forward** procesa cada destino en paralelo (vectorizacion), salida -> softmax -> probabilidad por origen.
- **Loss**: cross-entropy multinomial (`od_models.py:39-41`, `LogSoftmax`), aplicado sobre `target = flujo normalizado por outflow`.

## 5. Configuracion y Entorno

**Variables de entorno**: **Ninguna**. No hay `.env`, no hay `os.environ.get(...)`. Toda config va por `argparse`.

**Setup local (paso a paso)**:

1. Crear entorno Python 3.8 (las versiones pinadas son antiguas - sugerir conda).
2. Instalar manualmente:
    ```bash
    pip install torch==1.7.1 numpy==1.19.2 pandas==1.2.4 geopandas==0.9.0 scikit-mobility==1.1.0 area
    ```
    (No hay `requirements.txt`; el README lista versiones solo en texto.)
3. Bajar `flows.csv` de New York desde el link Google Drive del README y colocarlo en `deepgravity/data/new_york/`.
4. Los shapefiles `output_areas.shp`, `tessellation.shp`, y `features.csv` ya estan en el repo (`deepgravity/data/new_york/`).
5. **Preprocesado**: el README dice que en la 1ra ejecucion se genera `processed/`, **PERO** `_compute_support_files` esta comentado en `utils.py:136-137`. Es decir, el codigo **no regenera** el cache si falta; hay que borrar y recrear a mano o descomentar esas lineas. En este repo, `processed/` ya viene commiteado para New York.
6. Entrenar:
    ```bash
    cd deepgravity
    python main.py --dataset new_york --oa-id-column GEOID \
      --flow-origin-column geoid_o --flow-destination-column geoid_d \
      --flow-flows-column pop_flows --epochs 20 --device cpu --mode train
    ```
7. Salidas en `./results/`:
    - `model_DG_new_york.pt` (checkpoint)
    - `tile2cpc_DG_new_york.csv` (CPC por tile)
8. Visualizar resultados con `plots.ipynb` (Jupyter - el paper reproduce Fig 3 y Tabla 1).

**Nota**: El script asume `cwd = deepgravity/` porque los imports por `SourceFileLoader` y las rutas `./data_loader.py`, `./utils.py`, `./models/od_models.py` son relativas al CWD, no al archivo.

## 6. Observaciones del Arquitecto (Code Review)

### Areas de mejora / deuda tecnica

1. **Imports no idiomaticos via `SourceFileLoader`** (`main.py:68-71`, `utils.py:19-20`, `data_loader.py:6-7`, `deepgravity.py:16-17`):
    - Acopla el CWD; rompe la instalabilidad como paquete (`pip install -e .`).
    - No hay `setup.py` / `pyproject.toml`, `__init__.py` esta vacio.
    - **Recomendacion**: convertir a imports relativos normales, anyadir `pyproject.toml`, convertir `deepgravity` en paquete instalable.

2. **`_compute_support_files` esta comentado** (`utils.py:136-137`):
    - Si `processed/` se corrompe o se borra, `load_data` falla con `FileNotFoundError` en `open(...)`. El usuario no tiene forma limpia de regenerar.
    - Ademas, hay un **bug latente** en `utils.py:106`: `pickle.dump(oa2centroid, handle)` guarda `oa2centroid` en el archivo `od2flow.pkl` - deberia guardar `od2flow`. Bug silenciado porque el flujo esta comentado.

3. **`test()` rompe despues del primer batch** (`main.py:144`, literal `break`):
    - Solo evalua el primer batch del test_loader. Posiblemente sea un hack para debug, pero queda en produccion. CPC reportado durante el entrenamiento es **no representativo**. `evaluate()` posterior si recorre todo el loader - ese es el numero valido.

4. **Carga de datos en memoria**: `od2flow.pkl` pesa **19.6 MB** y `tileid2oa2handmade_features.json` **2.7 MB**; todo a RAM. Para datasets mas grandes (England/Italy completos) puede ser cuello de botella.

5. **Configuracion de dropout hardcodeada a 0** (`main.py:241`, `utils.py:188` - `dropout_p=0.0` por defecto), pero el constructor default de `NN_MultinomialRegression` usa `0.35` (`deepgravity.py:81`). Inconsistencia; el caller siempre pasa 0.

6. **Codigo repetido**: `earth_distance` definida tanto en `utils.py:193` como en `od_models.py:10`; `get_destinations`, `get_flow`, `get_features_ffnn` duplicados entre `data_loader.py`, `deepgravity.py` y `od_models.py`. Mantenibilidad baja.

### Tests

- **No existen tests automatizados**: sin carpeta `tests/`, sin `pytest`, sin `unittest`, sin `conftest.py`, sin fixtures, sin `tox.ini`.
- La "verificacion" funcional es el notebook `plots.ipynb` / `Untitled.ipynb` y el archivo `tile2cpc_*.csv` producido por `evaluate()`.
- **Cobertura: 0%** segun convenios estandar. El unico contrato de calidad reproducible seria comparar CPC contra los valores reportados en el paper.

### TODOs / FIXMEs

- Busqueda en `*.py` dentro de `deepgravity/`: **0 coincidencias** de `TODO|FIXME|XXX|HACK|BUG`. El codigo no usa marcadores de deuda explicitos; la deuda es **implicita** (codigo comentado, bugs latentes, duplicacion).

### Otros puntos menores

- `.gitignore` solo excluye `*.agents` y `*.json` - **insuficiente**: no ignora `__pycache__/`, `*.pyc` (que estan commiteados), `results/`, `.ipynb_checkpoints/`, ni los pickle/binarios grandes de `processed/`. El repo pesa probablemente >35 MB por shapefiles + pickles commiteados.
- El `argparse` mezcla `--batch_size` (guion bajo) y `--test-batch-size` (guiones) - inconsistencia de estilo.
- `__getitem_tile__` en `data_loader.py:111` esta definido pero no se usa en el flujo de `main.py` - metodo muerto.

## Resumen final

DeepGravity es un **artefacto de investigacion fiel al paper**, compacto (~800 LOC de Python), pero **no production-ready**: sin tests, sin empaquetado, con imports hackeados, varios bugs latentes (`utils.py:106`, `main.py:144`) y deuda tecnica evidente (codigo duplicado, `.gitignore` pobre, configuracion criticable). Su valor principal es **reproductibilidad cientifica**: reproduce con exito los resultados de Simini et al. 2021 sobre el dataset de New York incluido. Como base para extender a nuevos paises o a produccion, conviene refactorizar primero la cadena de imports, reactivar correctamente el preprocesado, escribir tests sobre CPC y discriminar `train()` / `test()` / `evaluate()` con un contrato claro.
