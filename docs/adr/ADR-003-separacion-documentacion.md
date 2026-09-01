# ADR-003: Separación de Documentación Técnica

- **Fecha**: 2026-08-20
- **Estado**: Aceptado

## Contexto

El archivo `architecture.md` existente en `docs/` contenía únicamente una auditoría técnica del repositorio base de los autores de Deep Gravity (código original + dataset de Nueva York). Sin embargo, este proyecto requiere documentar también la arquitectura propia: el pipeline de datos DTPM, la tessellation para Santiago y la integración con SHAP.

El problema era que cualquier lector de `architecture.md` podía confundir la arquitectura del repositorio base con la arquitectura de la tesis, especialmente en lo relativo a las fuentes de datos.

## Decisión

Se separa la documentación en dos archivos con propósitos distintos:

1. **`architecture.md`** (existente, refactorizado): auditoría técnica del repositorio base original. Se agregó un bloque de advertencia (`[!WARNING]`) al inicio señalando explícitamente que este documento describe el código de los autores originales (dataset Nueva York) y **no** el pipeline de la tesis. Redirige al lector a `arquitectura_santiago.md`.

2. **`arquitectura_santiago.md`** (nuevo): documento propio del proyecto, que describe el pipeline completo para el Gran Santiago: fuentes DTPM, **tessellation hexagonal H3** (Uber H3, resoluciones a explorar según ADR-004), redistribución de viajes de zona a hexágono, extracción OSM, correcciones al código base, y módulo XAI con SHAP comparativo entre modelos.

## Consecuencias

- **Positivas**: separación clara entre código heredado y contribución propia. No hay riesgo de confundir datasets o decisiones de diseño entre NY y Santiago.
- **Mantenimiento**: ambos archivos deben actualizarse por separado. `architecture.md` es estático (auditoría del código base); `arquitectura_santiago.md` es el documento vivo del proyecto y debe reflejar los cambios de ADR-004 (doble modelo comparativo: Modelo 1 zona 777 + Modelo 2 hexagonal H3).
