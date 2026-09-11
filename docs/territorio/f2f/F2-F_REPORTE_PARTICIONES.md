# F2-F — Tiles y particiones espaciales reproducibles

**Estado:** completada el 9 de septiembre de 2026; segunda mitad de G3.

## Regla fijada

Un *tile* es un cuadrado de **15.000 m** en EPSG:32719, indexado por `floor(x/15000), floor(y/15000)`. No es una unidad OD. La mayor extensión de una unidad activa es 11740.3 m, inferior al lado del tile; por eso cada bloque supera las unidades Zona 777, H3-r7 y H3-r8 que contiene.

La misma cuadrícula y la misma asignación de tiles se usan en las tres representaciones. La agenda se elige una vez mediante la masa originada Zona 777, objetivo 70%/15%/15%, semilla `20260909` y búsqueda determinista. No se usa el conjunto de prueba para elegir resolución o hiperparámetros.

## Agenda común

partition,tile_count,actual_origin_mass_share
test,1,0.18781762600983876
train,7,0.6819677660520177
validation,2,0.13021460793814343


`F2-F_ASIGNACION_TILES.csv` guarda cada tile y `F2-F_PARTICIONES_UNIDADES.csv` cada unidad activa. Las aserciones de construcción verifican que toda unidad origen aparece una sola vez y que no hay discrepancias de asignación entre ramas.

## Flujos que cruzan bloques

La política retiene flujos cruzados; su tabla OD agregada se materializará con el adaptador F2-G.

Los destinos quedan permitidos en todo el dominio metropolitano aprobado, incluso si pertenecen a otro tile o a otra partición. La partición se aplica al **origen**; los flujos cruzados se mantienen. Así se evita borrar viajes metropolitanos y se preserva una prueba espacial genuina por origen.

## Auditoría del código base y condición para F2-G

La auditoría confirma que `deepgravity/data_loader.py` limita hoy el universo de destinos a las unidades del tile de origen y que `deepgravity/main.py` se apoya en `train_tiles.csv`/`test_tiles.csv`. Esa semántica no implementa todavía este protocolo. F2-G debe cambiarla para que tiles separen orígenes, mientras el universo de candidatos conserva todos los destinos del dominio y los flujos cruzados.

## Salidas

- `F2-F_ESTADISTICAS_PARTICION.csv`: unidades, masa y tamaño por rama y partición.
- `F2-F_FLUJOS_CRUZADOS.csv`: masa y viajes por partición de origen/destino, sin pares OD individuales.
- `F2-F_MANIFIESTO_EJECUCION.json`: parámetros, hashes y resultado de las aserciones.
