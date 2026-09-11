# ADR-005: Delimitación territorial de Santiago

- **Fecha original:** 2026-09-01
- **Estado:** aceptado por el investigador el 2026-09-09; área F2-D fijada y G3 cerrada con F2-E/F
- **Revisión:** 2026-09-09

## Contexto

Una delimitación territorial debe retener actividad urbana suficiente sin incorporar una esparsidad periférica que distorsione la comparación. La lista de comunas y el polígono descritos en la versión inicial eran una referencia de trabajo, no una decisión respaldada por EDA.

## Propuesta previa a F2-D

F2-D evaluará alternativas territoriales con densidad de viajes, orígenes, destinos, unidades activas, cobertura y esparsidad. La decisión final incluirá:

- procedencia y versión de límites comunales;
- polígono y CRS;
- comunas incluidas;
- regla de frontera;
- criterio para exigir uno o ambos extremos dentro del área;
- tratamiento de celdas H3 que intersecten el borde.

## Consecuencias

- El filtro territorial aprobado se aplicará desde F2-E a las mismas observaciones de ambas ramas. No se usará la cifra de 743 zonas como selección heredada.
- La regla territorial será común a Zona 777 y H3 en la medida que permitan sus geometrías.
- Si el piloto modifica sustancialmente el área, se emitirá un ADR nuevo que reemplace esta decisión provisional y preserve su historia.

## Evidencia F2-D — 9 de septiembre de 2026

F2-D clasificó directamente los dos extremos UTM de los 60.682.293 viajes de la cohorte primaria contra los polígonos comunales DPA 2023, en EPSG:32719. La totalidad de los extremos quedó contenida por las 52 comunas de la Región Metropolitana. Los códigos presentes en los campos `comuna_inicio_viaje` y `comuna_fin_viaje` no se usaron para el recorte: su correspondencia empírica con las comunas DPA no fue unívoca.

La alternativa de núcleo urbano referencial de 34 comunas retiene 60.513.881 viajes (99,72 %) y 85.777.662,94 de masa expandida (99,69 %); la Región Metropolitana completa retiene el 100 %. La alternativa contigua basada en actividad no agregó comunas, porque ninguna comuna vecina superó el umbral predefinido de 0,10 % de la masa de extremos.

Los artefactos completos, incluida la fuente geométrica y los listados de comunas, se encuentran en `docs/territorio/f2d/`.

## Decisión aprobada — 9 de septiembre de 2026

El investigador aprobó el núcleo referencial de 34 comunas y consideró aceptable perder 168.412 viajes, equivalentes al 0,2775 % de la cohorte primaria de F2-C. Se retienen 60.513.881 viajes y 85.777.662,9386 de masa expandida; la pérdida de masa expandida es 0,3141 %.

La geometría aprobada es [F2-D_AREA_APROBADA.geojson](../territorio/f2d/F2-D_AREA_APROBADA.geojson). Conserva las 34 geometrías comunales DPA originales por separado para reproducir el criterio exacto de F2-D: cada extremo UTM debe estar estrictamente contenido en al menos un polígono seleccionado, proyectado a EPSG:32719. Se exigen ambos extremos dentro del área; el predicado `contains` excluye puntos exactamente sobre límites comunales.

El [manifiesto del área](../territorio/f2d/F2-D_AREA_APROBADA.json) registra la lista de comunas, CRS, hashes, regla de inclusión y fecha de aprobación. `tools/freeze_f2d_area.py` materializa estos artefactos desde los insumos auditados sin sobrescribir decisiones existentes.

F2-D queda completada. F2-E resolvió el tratamiento de bordes como celda H3 completa observada y seleccionó H3-r7 y H3-r8 para el piloto. F2-F fijó 10 tiles de 15 km en EPSG:32719, compartidos por Zona 777, H3-r7 y H3-r8; los tiles separan orígenes, mientras todos los destinos y los flujos cruzados permanecen disponibles en el dominio aprobado. Con los informes F2-E/F y la especificación F1-C, G3 queda cerrada el 2026-09-09.
