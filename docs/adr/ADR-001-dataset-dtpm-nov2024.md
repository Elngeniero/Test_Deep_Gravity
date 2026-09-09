# ADR-001: DTPM noviembre de 2024 como fuente de referencia

- **Fecha original:** 2026-08-18
- **Estado:** aceptado, con precisiones del 2026-09-08 y contrato F2-C aprobado el 2026-09-09

## Contexto

El proyecto necesita observaciones OD actuales para construir y evaluar una adaptación de Deep Gravity en Santiago. La fuente elegida es la entrega DTPM de noviembre de 2024, compuesta por archivos diarios de viajes y etapas.

El inventario F2-A verificó 29 fechas completas entre el 1 y el 29 de noviembre. Los archivos de viajes y etapas del día 30 llegaron con errores y quedan excluidos sin imputación. Los conteos de filas mensuales y la calidad final de la unión se determinarán en F2-B.

La cabecera de viajes contiene identificadores, zonas, comunas y secuencias de etapas. Las coordenadas UTM de subida y bajada están en etapas. Por ello, una asignación H3 de extremos de viaje requiere validar primero la unión diaria, el orden de etapas y la calidad del destino.

## Decisión

Se utilizará la cohorte DTPM disponible del 1 al 29 de noviembre de 2024 como fuente de referencia. El contrato F2-C aprobado define como cohorte primaria los viajes con secuencia de etapas coherente, extremos observados en primera y última etapa, zonas de origen y destino disponibles y factor_expansion no negativo. La EOD 2012/2017 se mantiene como antecedente histórico, no como ground truth del modelo.

## Consecuencias

- La rama Zona 777 y la rama H3 partirán de observaciones elegibles comunes.
- La asignación H3 se realizará desde los extremos reconstruidos y validados de etapas, no desde viajes directamente.
- factor_expansion será la masa expandida principal; unexpanded_weight=1.0 queda disponible para sensibilidad.
- La ausencia del día 30 se documentará como una limitación de cobertura, no como un valor faltante que deba imputarse.
- El trabajo de Vicente Mackenzie puede orientar la auditoría, pero no constituye un control experimental equivalente.
