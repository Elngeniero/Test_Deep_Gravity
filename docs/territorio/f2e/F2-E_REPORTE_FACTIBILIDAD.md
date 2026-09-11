# F2-E — Factibilidad espacial

**Estado:** completada. La cohorte primaria se filtró nuevamente con el dominio F2-D de 34 comunas y el predicado estricto `contains`: 60.513.881 viajes y 85.777.662,9386 de masa expandida se conservan en ambas ramas.

Zona 777 usa los campos canónicos y el ShapeZona777 publicado por DTPM. La fuente tiene 804 partes, normalizadas a 803 unidades (la zona 493 tiene dos partes); se declaró EPSG:4326 después de verificar sus bounds y se reparó la topología de la zona 543 conservando su ID. Seis IDs activos sin polígono en esa descarga se identifican en `F2-E_UNIDADES_ZONA777.csv` y usan sólo un anclaje agregado de extremos para tiles; no se presentan como geometría oficial.

H3 transforma EPSG:32719 a WGS84 con orden `always_xy` y asigna ambos extremos con `latlng_to_cell`. Se evaluaron r3–r8 sobre todos los viajes retenidos. La política de borde es **celda completa observada**: F2-D define los extremos retenidos; las celdas no se recortan ni se fracciona flujo.

| Representación | Orígenes activos | Pares OD | Densidad |
|---|---:|---:|---:|
| Zona 777 | 795 | 427.170 | 67,50% |
| H3-r6 | 43 | 1.736 | 93,89% |
| H3-r7 | 221 | 37.589 | 76,27% |
| H3-r8 | 1.194 | 617.070 | 43,76% |

H3-r7 y H3-r8 pasan al piloto: ambos conservan exactamente la cohorte, superan 100 orígenes activos y sus matrices densas de una pasada requieren menos de 128 MiB. r3–r6 son demasiado gruesas para la comparación. Las métricas completas están en `F2-E_METRICAS_REPRESENTACION.csv`.
