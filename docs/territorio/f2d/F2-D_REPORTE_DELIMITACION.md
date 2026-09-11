# F2-D — Alternativas de delimitación territorial

**Estado:** análisis generado y alternativa de 34 comunas aprobada por el investigador el 9 de septiembre de 2026; F2-D completada. G3 permanece abierta hasta resolver F2-E y F2-F.

La aprobación retiene 60.513.881 viajes y excluye 168.412 (0,2775 % de la cohorte primaria). La regla exige ambos extremos estrictamente dentro de las geometrías comunales seleccionadas. La geometría y el manifiesto se conservan en [F2-D_AREA_APROBADA.geojson](./F2-D_AREA_APROBADA.geojson) y [F2-D_AREA_APROBADA.json](./F2-D_AREA_APROBADA.json). Esta aprobación se registra después del análisis; las métricas que siguen corresponden a su ejecución original.

## Regla evaluada

Los campos comunales de DTPM contienen códigos, no nombres, y no son unívocos frente a los límites administrativos. F2-D clasifica directamente los dos extremos UTM de cada viaje primario contra los polígonos DPA en EPSG:32719. La regla propuesta para congelar el área exige ambos extremos dentro de las comunas seleccionadas.
El 100.00% de los viajes primarios tuvo ambos extremos contenidos por la DPA RM. La auditoría completa código DTPM–DPA confirma por qué esos códigos no se usaron para el recorte: su menor correspondencia modal fue 49.35%.

## Alternativas

| Alternativa | Comunas | Viajes internos | Masa expandida interna | Pares OD zonales | Densidad OD zonal |
|---|---:|---:|---:|---:|---:|
| nucleo_urbano_referencial_34 | 34 | 60,513,881 (99.72%) | 85,777,662.94 (99.69%) | 427,170 | 67.5026% |
| ampliada_contigua_actividad | 34 | 60,513,881 (99.72%) | 85,777,662.94 (99.69%) | 427,170 | 67.5026% |
| region_metropolitana_completa_52 | 52 | 60,682,293 (100.00%) | 86,047,937.93 (100.00%) | 430,655 | 67.4584% |

El núcleo referencial contiene las 34 comunas urbanas tradicionalmente asociadas al Gran Santiago. La alternativa ampliada añade comunas vecinas al núcleo con al menos 0,10 % de la masa expandida de extremos; las adiciones calculadas fueron: ninguna.

## Cobertura espacial completa

| Viajes primarios | Origen dentro de DPA RM | Destino dentro de DPA RM | Ambos extremos dentro de DPA RM |
|---:|---:|---:|---:|
| 60,682,293 | 100.00% | 100.00% | 100.00% |

## Alcance de esta evidencia

La cohorte de referencia contiene 60,682,293 viajes primarios y 86,047,937.93 de masa expandida. Los archivos CSV vecinos contienen las métricas por comuna, por zona y la lista exacta de comunas de cada alternativa. El investigador aprobó posteriormente el núcleo de 34 comunas. La caracterización H3 corresponde al siguiente bloque F2-E.
