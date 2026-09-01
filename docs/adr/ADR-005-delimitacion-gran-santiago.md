# ADR-005: Delimitación del Área de Estudio — Gran Santiago Urbano

- **Fecha**: 2026-09-01
- **Estado**: Aceptado

## Contexto

El dataset DTPM cubre técnicamente toda la Región Metropolitana (777 zonas), pero la cobertura operativa del sistema de transporte público (Red/Transantiago + Metro) es heterogénea: en comunas periféricas y rurales la densidad de validaciones bip! es muy baja, lo que genera matrices OD con alta esparsidad en esas zonas. Entrenar Deep Gravity con zonas de señal rala introduce ruido que degrada la calidad global del modelo.

Evidencia del trabajo previo: Vicente Mackenzie (2026) acotó a **743 de las 777 zonas operativas**, excluyendo 34 zonas periféricas de baja representatividad, sin documentar explícitamente el criterio de exclusión.

## Decisión

El área de estudio se acota al **Gran Santiago urbano con cobertura densa de transporte público**. Se excluyen comunas periféricas y zonas rurales de la Región Metropolitana.

### Criterio de delimitación

Se define una lista cerrada de comunas del Gran Santiago a incluir en el análisis. El criterio de inclusión es:
1. La comuna pertenece al continuo urbano del Gran Santiago (definición INE/SECTRA).
2. La comuna tiene cobertura de al menos una línea de bus Red o una estación de Metro en operación.
3. La densidad de validaciones bip! en el periodo noviembre 2024 supera un umbral mínimo (a definir en el piloto exploratorio de datos).

### Lista referencial de comunas incluidas (sujeta a validación con datos)

Las siguientes comunas conforman el núcleo urbano del Gran Santiago según la práctica de planificación del DTPM:

**Comunas centrales:** Santiago, Providencia, Las Condes, Ñuñoa, Vitacura, Lo Barnechea, La Reina, Peñalolén, Macul, San Joaquín, La Granja, La Florida, Puente Alto, San Bernardo, El Bosque, Pedro Aguirre Cerda, Lo Espejo, La Cisterna, San Miguel, Estación Central, Quinta Normal, Independencia, Recoleta, Conchalí, Huechuraba, Pudahuel, Lo Prado, Cerrillos, Maipú, Quilicura, Renca, Cerro Navia, La Pintana.

**Comunas limítrofes a evaluar (incluir si la densidad de datos lo justifica):** Pirque, San José de Maipo, Buin, Paine, Lampa, Colina, Til Til.

**Comunas excluidas (periferia rural, sin cobertura densa):** el resto de la Región Metropolitana (Melipilla, Curacaví, María Pinto, San Pedro, Alhué, Calera de Tango, etc.).

### Implementación técnica

- Para el **Modelo 1 (zona 777):** filtrar el GeoDataFrame de zonas para conservar solo las zonas cuyo centroide cae dentro del polígono del Gran Santiago definido.
- Para el **Modelo 2 (hexagonal H3):** generar la grilla H3 sobre el bounding box del Gran Santiago y recortar (clip) con el polígono de área de estudio.
- El polígono del área de estudio se construye como la unión geométrica de los límites comunales seleccionados (disponibles en shapefiles INE/BCNCHILE).

## Consecuencias

- **Positivas:**
  - Reduce la esparsidad de la matriz OD: zonas con señal rala quedan fuera del entrenamiento.
  - Mejora la comparabilidad con el trabajo de Vicente (743 zonas similares al Gran Santiago).
  - Facilita la reproducibilidad: el área de estudio es documentable con una lista de comunas.
- **Negativas/Limitaciones:**
  - Se excluyen viajes de la periferia, lo que reduce la representatividad del modelo para comunas limítrofes.
  - Esta limitación debe documentarse explícitamente en el capítulo de Validación de la tesis.
- **Pendientes:**
  - Confirmar la lista definitiva de comunas con la profesora guía (Pregunta 4 del Acta).
  - Validar el criterio de densidad mínima con el piloto exploratorio de datos (EDA).
  - Asegurar que el shapefile de límites comunales esté disponible en el proyecto (`data/shapefiles/`).
