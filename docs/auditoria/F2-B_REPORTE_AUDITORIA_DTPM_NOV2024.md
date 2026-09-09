# F2-B — Auditoría estructural y semántica DTPM

**Estado:** resultados generados automáticamente desde lecturas por lotes.

## Cobertura procesada

| Tabla | Filas procesadas |
|---|---:|
| viajes | 86,327,914 |
| etapas | 114,918,834 |

Se procesaron 29 fechas: 2024-11-01, 2024-11-02, 2024-11-03, 2024-11-04, 2024-11-05, 2024-11-06, 2024-11-07, 2024-11-08, 2024-11-09, 2024-11-10, 2024-11-11, 2024-11-12, 2024-11-13, 2024-11-14, 2024-11-15, 2024-11-16, 2024-11-17, 2024-11-18, 2024-11-19, 2024-11-20, 2024-11-21, 2024-11-22, 2024-11-23, 2024-11-24, 2024-11-25, 2024-11-26, 2024-11-27, 2024-11-28, 2024-11-29.

## Unión candidata

La prueba usa viajes.(id_tarjeta,id_viaje) y etapas.(id_etapa,correlativo_viajes). Solo se almacenaron hashes efímeros con una sal por fecha; las bases temporales se eliminaron.

| Métrica | Valor |
|---|---:|
| Claves únicas de viajes | 86,327,914 |
| Grupos de etapas | 86,327,914 |
| Grupos enlazados | 86,327,914 |
| Cobertura de grupos de etapas | 100.0 % |
| Coincidencia exacta n_etapas con número de etapas | 99.7797 % |

Los resultados diarios y las métricas de campos, números, categorías y cobertura se guardan en los CSV vecinos de este reporte.

## Coordenadas de etapas

| Extremo | Pares completos | Dentro de rango UTM amplio EPSG:32719 |
|---|---:|---:|
| subida | 114,918,834 | 114,886,024 |
| bajada | 87,440,384 | 87,440,384 |

El rango UTM usado para este control es amplio (X 100.000–900.000; Y 5.000.000–10.000.000) y no constituye todavía la regla territorial final.

## Límites de interpretación

- Esta auditoría no construye la cohorte canónica ni decide pesos, exclusiones o área de estudio.
- Los archivos del 30 de noviembre fueron entregados con errores; la cohorte se limita a los días 1–29 y no se imputará ese día.
- La semántica definitiva de los factores de expansión se cerrará tras contrastar estas métricas con el diccionario y la documentación de origen.
