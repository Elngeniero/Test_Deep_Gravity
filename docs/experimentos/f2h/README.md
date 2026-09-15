# Evidencia de F2-H

El dictamen y las cifras vigentes están en `../REPORTE_REPRODUCCION_NEWYORK.md`.
`REPORTE_HISTORICO_20260813.md` es una copia literal del reporte previo a esta auditoría; contiene afirmaciones corregidas y no constituye el resultado vigente.

| Archivo | Contenido |
|---|---|
| `inventory.json` | Hashes del dataset y del resultado histórico, versiones, particiones y conciliación del caché |
| `paper_reference.json` | Referencia exacta de la tabla publicada y páginas examinadas |
| `partitions_tiles.csv` | Los 192 tiles asignados a entrenamiento y 193 a prueba, incluidos los vacíos |
| `area_audit.csv` | Área histórica frente a área proyectada en EPSG:5070; diagnóstico sin modificar inputs |
| `historical_legacy_axes_*` | Replay del checkpoint antiguo conservando su interpretación incorrecta de ejes; CPC con soporte coherente y cociente histórico separados |
| `historical_corrected_axes_*` | Sensibilidad del checkpoint antiguo al corregir los ejes durante evaluación, sin reentrenarlo |
| `fresh_20ep_*` | Evaluación independiente del nuevo checkpoint; tablas por origen y por todos los tiles asignados |
| `training_*`, `evaluation_*` | Copias de manifiestos, configuraciones, particiones y métricas de las ejecuciones nuevas |
| `verification.json` | Cierre verificable: 20 épocas, 50.620 pasos, replay independiente, conservación y hashes |

Los archivos `fresh_20ep_*`, `training_*`, `evaluation_*` y `verification.json` se producen únicamente al finalizar correctamente la corrida. Los checkpoints y snapshots completos del código quedan en `runs/f2h_new_york/`, fuera de Git. El checkpoint histórico se conserva en su ruta original.

Para reconstruir en otro entorno, usar las dependencias fijadas en `requirements-f2h.txt` desde Python 3.8.20, los inputs con los hashes de `inventory.json`, el código identificado en el manifiesto y los comandos del reporte. No regenerar silenciosamente el caché histórico: falta `flows.csv` crudo y no se acredita su reconstrucción desde las fuentes originales. Los nombres de corrida son fijos para localizar esta evidencia; el runner rechaza sobrescribir una carpeta existente.

Las versiones fijadas describen el entorno efectivamente usado; la igualdad binaria entre sistemas operativos o bibliotecas numéricas diferentes no se presupone. La comprobación independiente utiliza tolerancias explícitas para CPC y conservación de masa.
