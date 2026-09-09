# F2-C — Contrato canónico y reconciliación DTPM

**Estado:** particiones canónicas generadas desde lecturas diarias reanudables.

## Cohorte

| Métrica | Valor |
|---|---:|
| Fechas procesadas | 29 |
| Viajes unidos | 86,327,914 |
| Cohorte primaria | 60,682,293 (70.2928 %) |
| Cohorte secundaria observada | 7,737,307 (8.9627 %) |
| Excluidos | 17,908,314 (20.7445 %) |

La primaria requiere secuencia completa, origen de la primera etapa, bajada válida en la etapa final, bandera ultimaetapaconbajada, zonas de viaje y peso no negativo. No incluye filtro territorial.

## Masa primaria

| Métrica | Valor |
|---|---:|
| Masa con factor_expansion | 86,047,937.9315 |
| Conteo sin expansión | 60,682,293 |
| Viajes con peso positivo | 60,682,293 |
| Viajes con peso cero conservados | 0 |

factor_expansion es el peso expandido propuesto porque el diccionario lo define a nivel de matriz OD de zonas 777. Los factores de etapa no sustituyen un peso de viaje; cada fila conserva unexpanded_weight=1.0.

## Causas exclusivas fuera de la primaria

| Causa | Viajes |
|---|---:|
| invalid_origin_coordinate | 16,292 |
| missing_destination_zone | 25,422,348 |
| missing_origin_zone | 15,982 |
| n_etapas_mismatch | 190,216 |
| trip_without_final_bajada_flag | 783 |

## Calidad de extremos

| Calidad | Viajes |
|---|---:|
| no_observed_destination | 17,902,046 |
| observed_final_stage | 61,001,212 |
| observed_latest_valid_bajada | 7,424,656 |

## Trazabilidad

- Las particiones contienen solo trip_key_hash con sal local ignorada por Git; no contienen identificadores de tarjeta, viaje ni etapa.
- La cohorte secundaria se conserva por cobertura, pero no se usará para comparar Zona 777 y H3.
- F2-D decidirá el área y F2-E el tratamiento de viajes intrazonales o intracelda.
