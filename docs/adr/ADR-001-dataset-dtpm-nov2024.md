# ADR-001: Dataset DTPM Noviembre 2024 como Ground Truth

- **Fecha**: 2026-08-18
- **Estado**: Aceptado

## Contexto

La tesis requiere una fuente de flujos OD reales para Santiago de Chile que sirva como *ground truth* para entrenar y evaluar el modelo Deep Gravity. Existían dos candidatos principales:

1. **EOD SECTRA 2012/2017** (Encuesta Origen-Destino): encuesta domiciliaria de referencia histórica para Santiago.
2. **Dataset DTPM Noviembre 2024**: registros anonimizados de validaciones bip!/RED del sistema de transporte público, correspondientes a todo el mes de noviembre de 2024.

## Decisión

Se utiliza el **dataset DTPM Noviembre 2024** como fuente de *ground truth*.

**Razones:**

- **Actualidad post-pandémica**: la EOD 2012/2017 no refleja la redistribución de los patrones de viaje ocurrida tras la pandemia de COVID-19 (teletrabajo, caída del metro, desconcentración hacia subcentros). El objetivo de la tesis es precisamente modelar la movilidad actual.
- **Volumen y resolución**: el dataset contiene ~3.6 millones de viajes y ~1.5 millones de etapas con alta resolución temporal y coordenadas UTM, muy superior a la muestra domiciliaria de la EOD.
- **Disponibilidad**: los CSV completos están disponibles en el equipo del investigador. La EOD requeriría gestión institucional adicional.
- **Coordenadas UTM**: los campos `x_subida`, `y_subida`, `x_bajada`, `y_bajada` permiten asignar viajes directamente a celdas de la tessellation cuadrada.

## Consecuencias

- **Positivas**: datos frescos, masivos y georreferenciados con precisión para el Gran Santiago.
- **Limitaciones a documentar**: el dataset no cubre viajes caminados, en taxi o en modos no motorizados. Tampoco incluye viajes de regiones fuera del sistema DTPM. Estas limitaciones se documentarán en el capítulo de Validación de la tesis.
- **La EOD 2012** queda como referencia histórica citada en el Marco Conceptual (Sección 2.7) y en la Definición del Problema, pero **no** como fuente de datos para el modelo.
