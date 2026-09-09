# F1-B — Conciliación del alcance y decisiones

**Fecha:** 8 de septiembre de 2026
**Estado:** completado

## Decisiones consolidadas

| Tema | Estado al cierre de F1-B | Referencia |
|---|---|---|
| Fuente y periodo | DTPM del 1 al 29 de noviembre de 2024; el día 30 se excluye por errores, sin imputación. | ADR-001 y preflight F2-A |
| Unidad espacial comparada | Se contrastarán Zona 777 y H3 desde una cohorte primaria común. | ADR-004 |
| H3 | Sistema jerárquico; la resolución, el área y los tiles aún no se seleccionan. No se asume área idéntica, seis vecinos universales ni eliminación del MAUP. | ADR-004 y arquitectura Santiago |
| Reconstrucción espacial | Las coordenadas están en etapas. La unión viaje–etapas debe validarse antes de asignar extremos H3. | ADR-001 y F2-B |
| Pesos y atributos | Población censal, generación observada, flujo expandido y atributos OSM son variables distintas. El factor principal, población y OSM quedan pendientes. | alcance y F2-I |
| Evidencia previa | La reproducción de Nueva York y el trabajo de Vicente son antecedentes internos; no son controles formales ni evidencia de Santiago. | alcance y arquitectura Santiago |
| Hipótesis | La comparación Zona 777–H3 es bilateral y falsable: se medirá cambio, ausencia de cambio o deterioro en desempeño y atribuciones predictivas. | arquitectura Santiago |

## Correcciones documentales efectuadas

1. Se actualizó el alcance de la tesis y la arquitectura de Santiago para reflejar el inventario F2-A, las dependencias entre F2-B/F2-C y las puertas pendientes.
2. Se corrigió ADR-001 por la exclusión del día 30 y por la ubicación de las coordenadas en etapas.
3. Se corrigió ADR-004 para describir H3 sin afirmaciones geométricas universales y dejar la resolución en evaluación.
4. Se devolvió ADR-005 a estado propuesto hasta que F2-D determine y versione la delimitación territorial.
5. Se etiquetaron las notas históricas de Nueva York y del código base para que no gobiernen decisiones de Santiago antes de sus auditorías previstas.

## Puertas que permanecen abiertas

| Puerta | Evidencia requerida antes de decidir |
|---|---|
| G2 | Auditoría completa de la unión viaje–etapas, contrato canónico y tratamiento de destinos. |
| G3 | Área de estudio, resoluciones H3 que superan factibilidad y particiones espaciales. |
| F2-I | Fuente de población, instantánea y ontología OSM, agregación, normalización y dimensión de atributos. |
| G4 | Piloto reproducible con comparabilidad Zona 777–H3, baselines y métricas estables. |

F1-B no selecciona estas opciones ni modifica el código heredado. Su resultado es dejar explícitos los supuestos, dependencias y criterios para que las fases posteriores puedan resolverlos con evidencia.
