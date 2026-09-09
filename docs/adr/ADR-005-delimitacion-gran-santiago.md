# ADR-005: Delimitación territorial de Santiago

- **Fecha original:** 2026-09-01
- **Estado:** propuesto; pendiente de G3
- **Revisión:** 2026-09-08

## Contexto

Una delimitación territorial debe retener actividad urbana suficiente sin incorporar una esparsidad periférica que distorsione la comparación. La lista de comunas y el polígono descritos en la versión inicial eran una referencia de trabajo, no una decisión respaldada por EDA.

## Decisión provisional

F2-D evaluará alternativas territoriales con densidad de viajes, orígenes, destinos, unidades activas, cobertura y esparsidad. La decisión final incluirá:

- procedencia y versión de límites comunales;
- polígono y CRS;
- comunas incluidas;
- regla de frontera;
- criterio para exigir uno o ambos extremos dentro del área;
- tratamiento de celdas H3 que intersecten el borde.

## Consecuencias

- No se aplicará aún un clip definitivo ni se usará la cifra de 743 zonas como selección heredada.
- La regla territorial será común a Zona 777 y H3 en la medida que permitan sus geometrías.
- Si el piloto modifica sustancialmente el área, se emitirá un ADR nuevo que reemplace esta decisión provisional y preserve su historia.
