# F2-A — Preflight técnico y protección de datos

**Fecha:** 8 de septiembre de 2026  
**Estado:** completado; G0 cerrado con una alerta de trazabilidad para F2-B.

## Alcance y estado inicial

- Repositorio: rama master, último commit observado 29c4624 (1 de septiembre de 2026).
- El plan maestro ya estaba presente como archivo no versionado antes del preflight. No se eliminaron ni sobrescribieron cambios ajenos.
- Git requiere safe.directory por la diferencia entre el propietario del repositorio y el usuario del sandbox. Las inspecciones se hicieron con la excepción temporal por comando, sin alterar la configuración global.
- La ruta de datos queda configurada en config/dtpm.local.env, archivo local ignorado por Git. La plantilla versionada es config/dtpm.local.env.example.

La ruta local contiene DTPM_DATA_ROOT y el intérprete que debe usarse para los siguientes pasos:

~~~
C:\Users\pablo\anaconda3\envs\deepgravity\python.exe
~~~

El código heredado aún no consume esta configuración: esa adaptación pertenece al refactor acotado de F2-G. El generador del manifiesto sí la consume, por lo que evita una ruta personal dentro del código.

## Inventario de datos

El manifiesto reproducible es [MANIFIESTO_DTPM_NOV2024.csv](./MANIFIESTO_DTPM_NOV2024.csv). Se generó leyendo solamente las cabeceras de los 58 CSV; no contiene filas ni identificadores de personas, tarjetas, viajes o etapas.

| Componente | Archivos | Cobertura | Tamaño |
|---|---:|---|---:|
| etapas | 29 | 2024-11-01 a 2024-11-29 | 30,93 GiB |
| viajes | 29 | 2024-11-01 a 2024-11-29 | 33,01 GiB |
| Diccionario de campos | 1 XLSX | versión julio de 2024 | 19 KiB |
| Total CSV | 58 | 1–29 de noviembre | 63,94 GiB |

Las 29 cabeceras de cada tabla son idénticas entre sí. Ambas tablas usan | como separador. En viajes hay 100 campos de esquema más una columna terminal vacía; etapas tiene 35 campos de esquema y no presenta una columna terminal vacía. Las cabeceras y su orden coinciden con las hojas Tabla_viajes (100 campos) y Tabla_etapas (35 campos) del diccionario XLSX. Muestras técnicas de los días 1 y 29 confirmaron estos conteos y el delimitador sin exponer valores de filas.

El 30 de noviembre no está presente en ninguna de las dos carpetas. La entrega sí incluye otros sábados, por lo que el inventario local no permitía tratar su ausencia como esperada. La profesora guía confirmó posteriormente que los archivos de viajes y etapas de ese día venían con errores. Por tanto, la cohorte disponible queda limitada a 29 fechas, del 1 al 29 de noviembre; el 30 no se imputará ni se incorporará sin una entrega corregida.

Para regenerar el manifiesto:

~~~powershell
& 'C:\Users\pablo\anaconda3\envs\deepgravity\python.exe' tools\generate_dtpm_manifest.py --config config\dtpm.local.env --output docs\preflight\MANIFIESTO_DTPM_NOV2024.csv
~~~

## Entorno y capacidad

| Recurso | Evidencia observada | Implicación |
|---|---|---|
| CPU | 8 procesadores lógicos | Ejecución disponible solo en CPU. |
| GPU | No hay CUDA disponible para PyTorch; nvidia-smi no está disponible | No presupuestar aceleración GPU. |
| RAM | 23,89 GiB total; 7,65 GiB libres al medir | No cargar un CSV hábil completo, ni el par diario, con pandas. |
| Disco C: | 236,85 GiB libres al medir | Hay margen inicial, pero los intermedios deben controlarse. |
| Entorno de proyecto | Python 3.8.20, PyTorch 1.13.1+cpu, pandas 2.0.3, GeoPandas 0.9.0 | Usar el intérprete configurado, no el Python 3.10 del PATH. |
| Dependencias ausentes | h3, pyarrow, dask, polars, duckdb, osmnx | F2-D y la conversión incremental a Parquet requieren un entorno reproducible que incorpore las dependencias elegidas. |

Límites operativos adoptados para F2-B:

1. Procesar un único archivo por vez, con usecols, tipos explícitos y lectura por lotes de 50.000 filas iniciales. Solo se podrá aumentar a 100.000 tras medir memoria estable.
2. No iniciar procesamiento pesado con menos de 10 GiB libres de RAM; mantener el proceso bajo 6 GiB de RSS.
3. Reservar al menos 50 GiB libres en C: y limitar el crecimiento inicial de intermedios, cachés y checkpoints a 150 GiB hasta medir su tamaño real.
4. No cargar los 63,94 GiB mensuales ni el par diario completo mediante una sola llamada a pandas.read_csv().

## Protección y estado del código

Se amplió .gitignore para excluir la configuración local, los crudos DTPM, intermedios, cachés, checkpoints, resultados de Santiago y subproductos comunes. Los artefactos de Nueva York ya versionados no fueron modificados.

La auditoría confirma que el repositorio heredado no está listo para regenerar cachés ni entrenar Santiago antes de F2-G:

- no hay archivo de dependencias ni pruebas automatizadas;
- el procesamiento de caché está desactivado y contiene errores de serialización y de rutas;
- la implementación actual carga flujos completos en memoria;
- el CPC usa un denominador incorrecto;
- la evaluación se detiene tras el primer lote;
- los destinos se restringen al tile de origen y oa2pop proviene del flujo saliente observado.

Estas observaciones son un inventario de preflight. No se han modificado aún porque las correcciones y sus pruebas corresponden a F2-G.

## Cierre de G0

Se conocen el estado de los archivos, la ubicación de los datos, el entorno y los límites de ejecución. La próxima fase es F2-B: auditoría estructural y semántica, incluida la unión candidata viajes–etapas, sin producir todavía la cohorte final.
