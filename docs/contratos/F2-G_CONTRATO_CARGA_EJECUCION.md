# F2-G — Contrato de carga, entrenamiento y evaluación

**Fecha:** 10 de septiembre de 2026.  
**Ámbito:** implementación técnica de F2-G. Las características científicas de Santiago se fijan en F2-I y el piloto se ejecuta en F2-J.

## Interfaz de datos

`deepgravity.adapters.FlowBundle` entrega unidades, atributos, anclajes WGS84, flujos OD y particiones. Sus implementaciones son `legacy` y `santiago`; Santiago admite `zona777`, `h3_r7` y `h3_r8`. Los IDs se leen como texto.

Las tablas OD contienen exclusivamente `origin_unit_id`, `destination_unit_id`, `trip_count` y `expanded_mass`. No conservan identificadores de tarjeta o viaje. Los pares repetidos se agregan y los valores cero y fraccionarios se conservan. Las masas seleccionables son conteo o expansión.

En Santiago, la partición se aplica al origen. Todo destino del dominio de unidades observado sigue siendo candidato, aunque pertenezca a validación, prueba u otro tile. La asignación directa H3 se calcula para cada resolución desde los extremos aprobados. Las tablas operativas resultantes de F2-G se guardan junto a la OD y se exportan a `docs/verificacion/f2g/`; las tablas anteriores F2-E/F se conservan como evidencia de su ejecución.

## Masa y características

El flujo saliente observado es la masa usada para reconstruir predicciones condicionadas al total del origen. Ese total no se añade automáticamente al vector de entrada. La población censal y los atributos externos requieren una tabla y columnas explícitas, con procedencia y normalización fijadas en F2-I.

La opción `legacy_observed_outflow` conserva la posibilidad de estudiar la ejecución heredada de Nueva York, exclusivamente bajo `purpose: legacy_audit`. Su uso no acredita ausencia de fuga ni validación científica.

Una ejecución científica de Santiago exige `features_path` y `feature_columns` completos. El cargador tampoco acepta como geometría científica de Zona 777 los seis anclajes de extremos que F2-E autorizó solo para tiles. La geometría faltante debe resolverse antes del entrenamiento comparativo, conservando la cohorte.

## Distancias

La función de distancia recibe `[latitud, longitud]` en grados WGS84 y devuelve kilómetros sobre una esfera de radio 6371,01 km. La transformación UTM usa `always_xy=True`. El caché heredado de Nueva York almacena `[longitud, latitud]`; el adaptador invierte explícitamente ese orden.

El preprocesador de geometrías calcula centroides y áreas en una proyección métrica antes de convertir los centroides a WGS84. Los representantes espaciales de F2-E/F2-G se identifican como anclajes; no se presentan todos como centroides geométricos.

## Muestreo y pérdida

Durante entrenamiento se toman hasta `destinations_per_origin` candidatos por origen, sin reposición. `positive_destination_fraction` reserva una cuota de destinos con flujo positivo dentro del soporte permitido. El resto se extrae uniformemente de los candidatos todavía no seleccionados: puede contener otros positivos. El valor heredado de la cuota es cero; no equivale a excluir todos los destinos positivos.

El muestreo depende de semilla, época e índice del origen, con orden estable de candidatos. No depende de la iteración de un conjunto de Python. La evaluación usa siempre el soporte completo, sin muestreo.

La pérdida conserva la log-verosimilitud multinomial negativa ponderada por los conteos o la masa suministrada: `-sum(y * log_softmax(scores))`. En entrenamiento con destinos muestreados, el softmax se normaliza sobre ese subconjunto. No se presenta esa aproximación como una evaluación sobre todo el dominio. Las pérdidas se suman dentro del lote; el informe divide por el número de orígenes procesados.

## CPC y conservación

`CPC = 2 * sum(min(observado, predicho)) / (sum(observado) + sum(predicho))`.

Se guardan numerador y ambas masas por origen. El CPC global y el CPC por tile se calculan sumando esos componentes sobre el mismo soporte. La media de CPC por origen, la media por todos los tiles y la media condicionada a CPC positivo se reportan por separado. La convención para observado y predicho simultáneamente nulos es CPC = 0.

Para cada origen de evaluación, las probabilidades se multiplican por su masa observada dentro del soporte evaluado. La acumulación de métricas usa float64. El informe conserva además la masa del dominio fuente, para hacer visible la restricción por tile de una auditoría heredada. La evaluación recorre todos los lotes y procesa cada origen exactamente una vez.

## Arquitectura y particiones

La red mantiene 15 capas ocultas: cinco de ancho 256 y diez de ancho 128, activaciones LeakyReLU, sin BatchNorm y dropout efectivo 0,0 por defecto. Los nombres de las capas permanecen compatibles con checkpoints del modelo heredado. Los ensayos sintéticos pueden usar un ancho menor, registrado en su configuración, sin convertirlo en una decisión científica.

Durante entrenamiento se evalúa validación cuando existe. Se rechaza configurar prueba como evaluación del entrenamiento. La evaluación de prueba requiere una ejecución separada, modo `evaluate`, un checkpoint y `evaluation_split: test`. Nueva York no trae una partición de validación en los artefactos locales; F2-H debe dejar explícito su protocolo.

## Caché y ejecuciones

El preprocesamiento está separado de la carga del modelo. El caché se genera cuando falta un archivo, cambia una entrada, cambia la configuración de lectura o falla un hash. `od2flow.pkl` contiene pares OD y masas. Un caché completo y vigente se reutiliza. Los cachés heredados sin manifiesto se identifican como tales y se reconcilian con su tabla independiente de flujos.

Cada entrenamiento o evaluación crea un directorio exclusivo mediante fecha/UUID o un `run_id` explícito. Un nombre existente provoca error. Se guardan configuración efectiva, versiones, hashes de entradas y código, copia del código ejecutado, particiones, métricas, estado, duración y checkpoint. Las rutas relativas se resuelven desde el archivo de configuración.

La materialización de OD se realiza por fecha, con hashes de entradas y salidas que permiten reanudar fechas completas. Cada lote lee unas 51.200 filas; DuckDB limita su memoria a 1 GB y usa dos hilos. Los archivos OD y las ejecuciones permanecen ignorados por Git.

## Comandos

Desde la raíz de DeepGravity, con el entorno del proyecto activado:

~~~powershell
python -m unittest discover -s tests -v
python materialize_santiago.py --config config/f2g_materialize.example.json
python run_deepgravity.py --config config/f2g_santiago_h3_r7.example.json
~~~

La configuración de Santiago es una plantilla: la lista de características queda vacía hasta F2-I y debe completarse antes de ejecutar entrenamiento científico. Para Zona 777 o H3-r8 se cambian explícitamente representación, tabla OD, unidades y atributos correspondientes.

`config/f2g_new_york.example.json` prepara el protocolo heredado para F2-H; F2-G no ejecuta sus 20 épocas. También se pueden invocar los lanzadores mediante ruta absoluta desde otro directorio.

