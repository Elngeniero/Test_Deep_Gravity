# F2-G — Refactor mínimo y verificación del modelo

**Estado:** completado el 10 de septiembre de 2026.  
**Alcance ejecutado:** F2-G; F2-H, F2-I y el piloto F2-J permanecen pendientes. G4 sigue abierta.

## Resultado

Se corrigieron CPC, serialización OD, regeneración condicional de caché, imports de paquete, muestreo y evaluación completa. El entrenamiento y la evaluación usan configuración declarativa y directorios exclusivos de ejecución. Se materializaron las 29 fechas canónicas en Zona 777, H3-r7 y H3-r8, con destinos metropolitanos globales y conservación del dominio F2-D.

La validación terminó con **37 pruebas aprobadas**, una verificación independiente de los agregados reales y un ensayo sintético de dos épocas con la arquitectura completa. No se entrenó un modelo de Santiago ni se evaluó el checkpoint de Nueva York.

## Evidencia frente a los criterios de F2-G

| Criterio | Implementación y comprobación |
|---|---|
| Serialización OD | `preprocessing.write_support_files` guarda pares OD y pesos; pruebas con duplicados, masas fraccionarias y cero. |
| Caché condicional | Se comprueban archivos, hashes de entradas/salidas y opciones de lectura. Se ensayaron reutilización, archivo ausente, corrupción y cambio de campo de peso. |
| CPC | Fórmula simétrica; casos idéntico, disjunto, nulo, parcial y masas distintas. El caso observado [8,0] y predicho [2,0] devuelve 0,4. |
| Conservación por origen | Softmax sobre soporte completo multiplicado por masa observada; verificación de cada origen y de las sumas por tile/global. |
| Destinos y muestreo | Candidatos globales en Santiago; cuota de positivos dentro del soporte, sin reposición, límites correctos y semillas estables. |
| Distancias | Contrato [latitud,longitud], kilómetros, centros proyectados y transformación con orden explícito. Se corrigió la lectura del orden heredado de NY. |
| Particiones | IDs textuales, origen único, tile único y misma agenda de F2-F. Se mantienen flujos entre particiones. |
| Evaluación completa | Recorre todos los lotes; invariancia frente a tamaños de lote y casos con masa nula. |
| Semillas y modos | Dos ejecuciones sintéticas reproducen parámetros y métricas; pruebas de train/eval y dropout. |
| Arquitectura | Cinco capas de 256 y diez de 128; LeakyReLU, sin BatchNorm, dropout 0,0. El checkpoint NY existente carga estrictamente con dimensión de entrada 39. |
| Ejecuciones | Configuración efectiva, versiones, hashes, copia del código, particiones, métricas y checkpoint; se rechazan nombres existentes. |
| Independencia del directorio | Imports sin ejecución al importar y prueba completa con lanzador absoluto desde otro directorio. |

Log íntegro: [F2-G_PRUEBAS.txt](F2-G_PRUEBAS.txt).  
Contrato y comandos: [F2-G_CONTRATO_CARGA_EJECUCION.md](../../contratos/F2-G_CONTRATO_CARGA_EJECUCION.md).

## Materialización y conservación mensual

Las tres ramas conservan **60.513.881 viajes** y **85.777.662,9386 de masa expandida**, con diferencias de suma de punto flotante por debajo de la tolerancia de 0,0001. Los conteos son exactos. La verificación se ejecutó mediante consultas independientes sobre las tablas OD, controles de cada origen, hashes y carga por el adaptador común.

| Rama | Unidades candidatas | Orígenes activos | Destinos activos | Pares OD | Viajes entre tiles |
|---|---:|---:|---:|---:|---:|
| Zona 777 | 796 | 795 | 796 | 427.170 | 34.643.357 (57,25 %) |
| H3-r7 directa | 223 | 220 | 222 | 37.196 | 35.048.185 (57,92 %) |
| H3-r8 | 1.210 | 1.194 | 1.181 | 617.070 | 34.435.766 (56,91 %) |

La masa expandida de los flujos entre tiles es 48.878.953,4721 en Zona 777, 49.438.725,3390 en H3-r7 y 48.586.694,1441 en H3-r8. Esos flujos permanecen en el entrenamiento o la evaluación según la partición del origen.

La OD mensual ocupa aproximadamente 6,2 MiB en total y se conserva en la ruta ignorada `deepgravity/data/santiago/interim/f2g_spatial/`. Las particiones diarias y sus manifiestos permiten reanudar la materialización sin repetir fechas completas. Durante la ejecución se observó un RSS de aproximadamente 265 MiB; no se presenta esa observación puntual como un máximo de memoria.

## Corrección de H3-r7 detectada en F2-G

La implementación anterior de F2-E obtenía las resoluciones menores desde `cell_to_parent(r8, resolución)`. Esa operación jerárquica no equivale a asignar directamente el punto con `latlng_to_cell` en cada resolución. El contrato aprobado especifica asignación desde los extremos.

F2-G aplicó esa regla directa y volvió a reconciliar las 29 fechas. En r7:

- se añade `87b2c551bffffff`;
- dejan de estar observadas `87b2c5564ffffff` y `87b2c5721ffffff`;
- el soporte pasa de 224 a 223 unidades;
- los orígenes activos pasan de 221 a 220 y los pares OD de 37.589 a 37.196;
- cambian los conteos de origen de 215 unidades de la unión de ambos soportes.

Zona 777 y H3-r8 mantienen sus unidades, pares OD y conteos por origen. El área aprobada, la cohorte, el peso principal, las resoluciones candidatas y los 10 tiles de 15 km se conservan. Las unidades corregidas se asignan a la agenda existente de F2-F; no se vuelve a optimizar ni a sortear la partición. H3-r7 conserva más de 100 orígenes y su matriz densa de scores ocupa menos de 1 MiB, por lo que esta corrección no altera su condición de candidata al piloto.

Las tablas históricas F2-E/F se preservan. Para las próximas fases, las unidades y particiones operativas son [F2-G_UNIDADES_H3_R7.csv](F2-G_UNIDADES_H3_R7.csv) y [F2-G_PARTICIONES_UNIDADES.csv](F2-G_PARTICIONES_UNIDADES.csv), junto con las tablas Zona 777/H3-r8 de esta carpeta. También se corrigió la asignación directa en el script de F2-E y su escritura Parquet mediante DuckDB. Las estadísticas históricas de r3–r6 no se recalcularon en esta fase y deberán regenerarse con el script corregido si se usan en la redacción final.

## Nueva York: comprobaciones técnicas y entrega a F2-H

El checkpoint local carga con los nombres originales de las capas. Se corrigió el orden longitud–latitud del caché al contrato latitud–longitud de distancia, sin modificar los artefactos NY existentes.

La carga estructural identifica 5.411 unidades con atributos, de las cuales 44 no tienen tile; 133.927 pares OD referencian unidades fuera de la cobertura de atributos y suman 8.567.506 de flujo. El adaptador registra esa exclusión de soporte en modo de auditoría y conserva el outflow fuente para comparar masas. Hay 2.531 orígenes de entrenamiento y 2.836 de prueba; no existe una partición de validación suministrada.

Estos controles no cierran F2-H. Esa fase debe auditar el soporte, la configuración, el predictor de generación observada y las métricas, y ejecutar o validar las 20 épocas. El ejemplo de configuración preserva las opciones heredadas de forma explícita para esa auditoría.

## Límites y siguientes pasos

La fuente de población, la ontología OSM, la normalización y las columnas del vector de Santiago siguen pendientes de F2-I. La tabla de features no se sustituye por outflow observado. Antes del entrenamiento científico zonal también debe resolverse la geometría de los seis IDs que F2-E solo pudo anclar para tiles.

La sincronización integral del capítulo 4 corresponde a F1-C/F1-E/F1-F y G5. La siguiente fase de ejecución es **F2-H**; G4 se cierra únicamente después del piloto reproducible de Santiago.

## Artefactos y reproducción

- [F2-G_VERIFICACION.json](F2-G_VERIFICACION.json): conservación, hashes, soporte corregido y resultados de carga real.
- [F2-G_CONSERVACION_DIARIA.csv](F2-G_CONSERVACION_DIARIA.csv): 29 fechas reconciliadas.
- [F2-G_VERIFICACION_RAMA.csv](F2-G_VERIFICACION_RAMA.csv): unidades, OD y particiones por rama.
- [F2-G_FLUJOS_CRUZADOS.csv](F2-G_FLUJOS_CRUZADOS.csv): conteos y masas entre bloques y particiones.
- [F2-G_COMPATIBILIDAD_CHECKPOINT_NY.json](F2-G_COMPATIBILIDAD_CHECKPOINT_NY.json): carga estructural.
- [F2-G_SMOKE_SINTETICO.json](F2-G_SMOKE_SINTETICO.json): ubicación de la ejecución técnica persistida bajo `runs/f2g/`.
- [F2-G_ENTORNO_Y_FUENTES.json](F2-G_ENTORNO_Y_FUENTES.json): versiones y hashes del código entregado.

Con el entorno del proyecto activado, desde la raíz de DeepGravity:

~~~powershell
python -m unittest discover -s tests -v
python materialize_santiago.py --config config/f2g_materialize.example.json
python verify_f2g_artifacts.py --data deepgravity/data/santiago/interim/f2g_spatial --approval docs/territorio/f2d/F2-D_AREA_APROBADA.json --tile-schedule docs/territorio/f2f/F2-F_ASIGNACION_TILES.csv --output docs/verificacion/f2g
~~~

