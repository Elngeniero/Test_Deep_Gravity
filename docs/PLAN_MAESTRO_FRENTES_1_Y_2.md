# Plan maestro de ejecución — Frentes 1 y 2

> **Estado:** F2-I cerrada y aprobada; siguiente fase F2-J, aún no iniciada  
> **Fecha de consolidación:** 8 de septiembre de 2026  
> **Última actualización:** 14 de septiembre de 2026; G4 permanece abierta  
> **Proyecto:** adaptación y evaluación de Deep Gravity para Santiago  
> **Uso previsto:** fuente única para continuar el trabajo en este u otro chat

## 1. Propósito y relación entre los frentes

Este documento contiene dos planes coordinados:

- **`PLAN-F1` — Frente 1:** corregir y consolidar la definición científica del proyecto, el capítulo 4 y la documentación técnica de `docs/`.
- **`PLAN-F2` — Frente 2:** auditar los datos DTPM, construir el contrato común de viajes, adaptar el código, validar Nueva York y ejecutar el piloto de Santiago.

La relación rectora es:

> **El Frente 1 fija las preguntas, las reglas y los criterios de evaluación; el Frente 2 produce la evidencia para confirmarlos, modificarlos o descartarlos.**

Los frentes pueden avanzar parcialmente en paralelo. Sin embargo, el Frente 1 no debe presentar como implementado u observado aquello que el Frente 2 todavía no haya verificado.

## 2. Decisiones vigentes que deben respetarse

1. El *ground truth* será el conjunto DTPM de noviembre de 2024, no la EOD 2012.
2. Se compararán dos representaciones espaciales construidas desde una cohorte común:
   - **rama zonal:** zonas DTPM/777 irregulares;
   - **rama H3:** celdas H3, con resoluciones 3–8 sometidas primero a un análisis de factibilidad.
3. H3-r3 a H3-r5 probablemente serán demasiado gruesas para modelación intraurbana; esto debe demostrarse con el área seleccionada, no imponerse como resultado previo. H3-r6 puede actuar como control grueso y H3-r7/H3-r8 son las candidatas iniciales al piloto.
4. La resolución H3 final no se escogerá únicamente por el CPC. También se evaluarán número de celdas, viajes por celda, cobertura, esparsidad, estabilidad y costo computacional.
5. La hipótesis sobre H3 y la importancia de variables del destino es **abierta y falsable**. Que las variables de destino no aumenten su importancia también es un resultado válido.
6. El trabajo de Vicente Mackenzie se utilizará solo como apoyo interno y antecedente orientador. Su CPC no es un control experimental equivalente ni una referencia formal obligatoria de la memoria.
7. Ambas ramas deben utilizar las mismas observaciones elegibles, ventanas temporales, pesos, fuentes de atributos y reglas de partición siempre que sea posible.
8. El área de estudio aprobada el 9 de septiembre de 2026 corresponde al núcleo referencial de 34 comunas de F2-D, con ambos extremos estrictamente dentro de los polígonos seleccionados. Retiene 60.513.881 viajes primarios; la geometría y regla están fijadas en ADR-005 y `docs/territorio/f2d/F2-D_AREA_APROBADA.json`.
9. Las unidades H3 y los *tiles* no son lo mismo:
   - la celda o zona es la unidad origen-destino;
   - el *tile* es un bloque espacial mayor utilizado para particionar o evaluar.
10. SHAP/XAI se ejecutará después de estabilizar datos, entrenamiento y evaluación. El capítulo 5 y las conclusiones se redactarán al final.
11. La introducción puede conservar por ahora su orientación al resultado esperado, pero deberá revisarse contra los resultados finales.
12. Los datos crudos permanecen fuera del repositorio. El código debe recibir su ruta mediante configuración y nunca depender de una ruta personal escrita dentro de los módulos.

## 3. Hechos verificados al preparar este plan

### 3.1 Inventario de datos disponible

Ruta externa actual:

```text
C:\Users\pablo\Desktop\dptm\dtpm
```

Contenido observado:

| Componente | Archivos | Fechas observadas | Tamaño aproximado |
|---|---:|---|---:|
| `etapas/*.etapas.csv` | 29 | 2024-11-01 a 2024-11-29 | 30,93 GiB |
| `viajes/*.viajes.csv` | 29 | 2024-11-01 a 2024-11-29 | 33,01 GiB |
| Diccionario `.xlsx` | 1 | versión julio de 2024 | 19 KiB |
| **Total CSV** | **58** | falta verificar por qué no aparece el día 30 | **63,94 GiB** |

Los CSV usan `|` como separador y poseen un separador final en la cabecera y las filas, lo que puede originar una columna vacía adicional al leerlos.

### 3.2 Hallazgo que cambia el preprocesamiento previsto

- La cabecera de `etapas` contiene `x_subida`, `y_subida`, `x_bajada` y `y_bajada`.
- La cabecera de `viajes` no contiene esas coordenadas; contiene zonas, comunas y la secuencia de etapas.
- La asignación H3 del viaje completo no puede asumirse directamente desde `viajes`. Primero debe validarse una unión diaria entre:
  - `viajes.(id_tarjeta, id_viaje)`; y
  - la clave candidata `etapas.(id_etapa, correlativo_viajes)`.
- La hipótesis inicial es reconstruir el origen con la primera etapa y el destino con la última etapa que tenga bajada válida. Esta regla no se adopta hasta medir unicidad, orden, completitud y coherencia con `n_etapas`, `netapassinbajada` y `ultimaetapaconbajada`.

### 3.3 Inconsistencias documentales ya detectadas

- `docs/contexto/ALCANCE_Y_LINEAMIENTOS_TESIS.md` todavía define grillas cuadradas de 500 m–5 km.
- `docs/arquitectura_santiago.md`, ADR-004 y `propuesta_de_solucion.tex` afirman erróneamente igualdad exacta de área, seis vecinos para toda celda y eliminación del MAUP.
- `propuesta_de_solucion.tex` confunde valores de H3-r7 y H3-r8 y usa arista/radio de manera incorrecta.
- Algunos documentos dicen que los CSV de `viajes` contienen coordenadas UTM directas; el inventario de cabeceras no lo confirma.
- Se presenta la selección de 12 variables OSM y una cobertura inferior al 30 % como si ya estuvieran verificadas.
- Se describe un único *tile* metropolitano, mientras la decisión vigente exige particiones espaciales por *tiles*.
- Algunas correcciones de código se narran como ejecutadas aunque siguen pendientes.
- El reporte de Nueva York da demasiado peso interpretativo al ensayo de 3 épocas y mezcla CPC sobre todos los *tiles* con CPC condicionado a *tiles* no nulos.
- El capítulo 4 describe BatchNorm, seis capas de 256 unidades y nueve de 128; el código inspeccionado no usa BatchNorm y contiene cinco salidas ocultas de 256 seguidas de diez de 128.
- El modelo declara `dropout_p=0.35` como valor por defecto, pero la ruta actual de ejecución lo instancia con `dropout_p=0.0`.
- La variable llamada `oa2pop` se obtiene actualmente del flujo saliente observado, mientras la documentación habla de población censal. Ambas magnitudes no son intercambiables y existe riesgo de fuga si se derivan usando información fuera de la partición permitida.
- La función actual de CPC repite la suma predicha en el denominador en vez de sumar observado más predicho. El error puede quedar oculto cuando ambas masas coinciden y, por eso, requiere pruebas no simétricas.
- El `FlowDataset` limita actualmente los destinos candidatos a las unidades del *tile* del origen. Esta semántica debe conciliarse con el sistema metropolitano y con el uso de *tiles* como particiones espaciales.

## 4. Reglas de orquestación con subagentes

### 4.1 Roles

Cada fase será dirigida por un **agente coordinador** y podrá usar hasta tres subagentes simultáneos:

1. **Subagente de inventario/auditoría:** trabaja en modo solo lectura y entrega evidencia con archivos, líneas, comandos y resultados.
2. **Subagente de implementación/redacción:** modifica únicamente los archivos que le asigne el coordinador.
3. **Subagente de verificación independiente:** revisa cambios, pruebas, consistencia y criterios de aceptación; no corrige silenciosamente el trabajo del implementador.

El coordinador integra los resultados, resuelve contradicciones, ejecuta la validación final y comunica el *handoff*.

### 4.2 Normas para evitar conflictos

- No se asignará el mismo archivo a dos subagentes que escriban en paralelo.
- Antes de editar, el coordinador registrará el estado del repositorio y preservará cambios preexistentes del usuario.
- Los subagentes de auditoría no editarán archivos.
- Los cambios compartidos o transversales —configuración, contratos, índices documentales— los integrará el coordinador.
- Cada implementación se hará en lotes pequeños revisables. No se mezclarán en un mismo lote correcciones documentales, refactor estructural y resultados experimentales.
- Ningún agente copiará los 64 GiB de datos crudos al repositorio ni expondrá identificadores sensibles en reportes o muestras versionadas.
- Los artefactos generados grandes, cachés, modelos y datos intermedios se mantendrán fuera de Git mediante reglas explícitas de `.gitignore`.

### 4.3 Formato obligatorio de entrega de un subagente

```text
Subtarea:
Archivos inspeccionados o modificados:
Evidencia obtenida:
Decisiones asumidas:
Pruebas ejecutadas y resultado:
Riesgos o dudas pendientes:
Estado: completado / requiere integración / bloqueado
```

### 4.4 Puertas de control conjuntas

| Puerta | Condición para cruzarla | Responsable final |
|---|---|---|
| G0 — Preflight | Estado de archivos conocido; datos localizados; entorno inventariado | Coordinador |
| G1 — Contrato científico | Objetivos, hipótesis, unidades y términos consistentes | Frente 1 |
| G2 — Contrato de datos | Cohorte, claves, extremos, pesos y descartes trazables | Frente 2 |
| G3 — Factibilidad espacial | Área, ramas, H3 y *tiles* caracterizados | Ambos |
| G4 — Pipeline válido | Pruebas, NY auditado y piloto Santiago reproducible | Frente 2 |
| G5 — Sincronización | Capítulo 4 y `docs/` reflejan solo lo verificado | Frente 1 |

---

# Plan 1 — Frente 1: capítulo 4 y documentación

## F1.1 Objetivo

Transformar el capítulo 4 y `DeepGravity/docs/` en una especificación científica coherente, verificable y sincronizada con el estado real del código y los datos, sin anticipar resultados del piloto ni de XAI.

## F1.2 Alcance

Archivos principales:

- `../../tex-thesis-template/propuesta_de_solucion.tex`
- `docs/arquitectura_santiago.md`
- `docs/contexto/ALCANCE_Y_LINEAMIENTOS_TESIS.md`
- `docs/conocimiento/hallazgos_tecnicos.md`
- `docs/experimentos/REPORTE_REPRODUCCION_NEWYORK.md`
- `docs/adr/ADR-001-dataset-dtpm-nov2024.md`
- `docs/adr/ADR-004-grilla-hexagonal-h3-doble-modelo.md`
- `docs/adr/ADR-005-delimitacion-gran-santiago.md`
- índices `docs/**/README.md`
- `../../Analisis Proyecto Deep Gravity.md`

El capítulo 5, las conclusiones y el análisis XAI final quedan fuera de esta ejecución.

## F1.3 Secuencia de trabajo

### F1-A — Matriz de afirmaciones y contradicciones

**Subagentes en paralelo:**

- A1 audita objetivos, alcance, ADR y estado del proyecto.
- A2 audita capítulo 4: matemáticas, H3, variables, entrenamiento y lenguaje de resultados.
- A3 contrasta la documentación con cabeceras de datos y código actual.

**Salida:** `docs/revisiones/MATRIZ_TRAZABILIDAD_CAP4.md`, con columnas:

```text
ID | afirmación | archivo/línea | tipo | evidencia | estado | acción
```

Tipos: `decisión`, `procedimiento previsto`, `implementado`, `resultado observado` o `limitación`.

**Criterio de término:** toda afirmación relevante del capítulo 4 queda asociada a evidencia o marcada inequívocamente como futura.

### F1-B — Conciliación del alcance y las decisiones

1. Sustituir las grillas cuadradas activas por el diseño comparativo Zona 777–H3; conservar ADR-002 solo como historia reemplazada.
2. Reformular la contribución central como evaluación de sensibilidad del desempeño y de las explicaciones frente a la discretización espacial.
3. Definir H3 correctamente como índice jerárquico de celdas, no como grilla de hexágonos planos idénticos.
4. Corregir las afirmaciones sobre áreas, vecinos, jerarquía y MAUP.
5. Expresar la hipótesis sobre H3, CPC y variables de destino como pregunta empírica, sin resultado esperado obligatorio.
6. Reubicar a Vicente como apoyo interno/antecedente no equivalente, eliminando frases que lo convierten en control formal reproducido.
7. Distinguir población censal, flujo observado DTPM, factor de expansión y características OSM.
8. Declarar que área de estudio, resolución H3 y partición por *tiles* quedan sujetas a las puertas G2–G3.

**Política para ADR:** corregir errores factuales con una nota fechada. Si el piloto cambia una decisión metodológica —por ejemplo, rango H3, área o cohorte— crear un ADR nuevo que reemplace la decisión anterior en vez de borrar su historia.

### F1-C — Reescritura del capítulo 4 como especificación verificable

La nueva estructura deberá cubrir:

1. fuente DTPM y unidad observacional todavía por confirmar;
2. reconstrucción de viajes desde `viajes` y `etapas`;
3. cohorte común y reglas de exclusión;
4. delimitación territorial reproducible;
5. adaptadores espaciales Zona 777 y H3;
6. análisis de factibilidad H3-r3–r8 y selección mediante validación;
7. definición y construcción de *tiles*;
8. contrato de población y de características OSM;
9. arquitectura realmente implementada por Deep Gravity;
10. soporte de destinos, muestreo negativo y función de pérdida;
11. baselines y protocolo de comparación;
12. reproducibilidad, semillas, configuración y versionado de resultados;
13. limitaciones y amenazas a la validez.

Correcciones obligatorias:

- eliminar igualdad exacta de áreas y eliminación del MAUP;
- no afirmar que toda celda tiene seis vecinos;
- corregir áreas y longitudes de H3-r7/H3-r8, aclarando que son promedios y que arista no es radio;
- no afirmar asignación directa desde `viajes` hasta cerrar la unión con `etapas`;
- no presentar las 12 categorías OSM ni el umbral del 30 % como resultado observado antes del EDA;
- revisar la dimensión del vector de entrada después de fijar el contrato de *features*;
- reemplazar “single tile” por el protocolo espacial que se apruebe;
- describir el muestreo negativo con precisión: universo de candidatos, proporción de positivos, distribución, reposición y efecto en entrenamiento/evaluación;
- separar hiperparámetros heredados de parámetros efectivamente verificados para Santiago;
- no decir que los bugs fueron corregidos antes de que existan cambios y pruebas que lo demuestren.

Bloque teórico obligatorio:

1. **Gravedad y Logit:** si la utilidad es `V_ij = β1 ln(P_j) + β2 ln(d_ij)`, el *softmax* induce una disuasión de potencia `P_j^β1 d_ij^β2`, no una disuasión exponencial en distancia. Para una gravedad exponencial se requiere una utilidad coherente del tipo `V_ij = α ln(P_j) - β d_ij`. Las ecuaciones deben alinearse con el capítulo 2.
2. **Entropía cruzada:** minimizar entropía cruzada equivale a maximizar la log-verosimilitud multinomial bajo el contrato correspondiente, pero no equivale automáticamente a maximizar la entropía de Wilson. La conexión solo puede presentarse con sus restricciones y supuestos, o como relación conceptual limitada.
3. **Aproximación universal:** el teorema es un resultado de existencia; no demuestra que una arquitectura específica de 15 capas aprenderá, optimizará o generalizará adecuadamente con datos finitos.

Bloque de fidelidad al código:

- contrastar número y ancho de capas, activaciones, ausencia/presencia de BatchNorm y valor efectivo de dropout;
- separar arquitectura heredada, arquitectura ejecutada en NY y configuración propuesta para Santiago;
- resolver si la masa de entrada será población censal o generación observada; no llamar `población` al *outflow*;
- describir el universo de destinos que realmente usa el loader y decidir si los *tiles* particionan orígenes, candidatos o ambos.

### F1-D — Figuras y tablas permitidas antes de resultados

Se pueden agregar:

- diagrama del pipeline y sus dos adaptadores espaciales;
- esquema que distinga área, celda/zona y *tile*;
- tabla de contrato de datos y procedencia de cada variable;
- tabla de decisiones/hipótesis y evidencia requerida;
- tabla de resoluciones H3 con estadísticas oficiales claramente identificadas como promedios.

No se agregarán gráficos que parezcan resultados propios sin datos producidos por el Frente 2.

### F1-E — Sincronización documental

Actualizar todos los documentos de alcance y estado para que coincidan con el capítulo 4. La auditoría original de Nueva York (`docs/architecture.md`) se mantiene como descripción del repositorio base, no como arquitectura activa de Santiago.

En particular:

- reemplazar tamaños antiguos de CSV por el inventario mensual real;
- registrar que las coordenadas observadas están en `etapas`;
- sincronizar bugs como `pendiente`, `corregido` o `verificado`, nunca estados ambiguos;
- retirar la grilla cuadrada de las instrucciones activas;
- calificar correctamente el estado de NY y retirar el ensayo de tres épocas como evidencia científica;
- reparar enlaces e índices de `docs/`.

### F1-F — Verificación independiente

Un subagente distinto del redactor debe comprobar:

1. búsqueda global de conceptos obsoletos;
2. consistencia de nombres de columnas con las cabeceras reales;
3. consistencia entre objetivos, ADR, capítulo 4 y resumen de estado;
4. ausencia de resultados inventados o futuros narrados en pasado;
5. compilación completa de `main.tex`;
6. revisión visual de `main.pdf`, referencias, tablas, figuras y advertencias relevantes de LaTeX.

## F1.4 Entregables

- capítulo 4 corregido y compilado;
- documentación de `docs/` sincronizada;
- matriz de trazabilidad de afirmaciones;
- registro de decisiones pendientes y su puerta de resolución;
- reporte breve de compilación y control de calidad.

## F1.5 Criterios de aceptación

- No quedan grillas cuadradas como decisión vigente fuera del registro histórico.
- H3 no se describe como exactamente equiárea ni como solución que elimina el MAUP.
- No se presenta una mejora de CPC o SHAP como garantizada.
- Los datos, campos y transformaciones coinciden con lo verificado por el Frente 2.
- Vicente no aparece como control experimental equivalente ni como referencia formal central.
- Toda característica tiene definición, unidad, fuente y regla de agregación; lo pendiente queda marcado.
- La función de *tiles* y muestreo negativo es comprensible y consistente con la implementación prevista.
- `main.tex` compila y el PDF no presenta defectos introducidos por la revisión.

## F1.6 Punto de detención

El Frente 1 se detiene tras G5. No redacta resultados del capítulo 5, discusión causal ni conclusiones antes de contar con experimentos finales trazables.

---

# Plan 2 — Frente 2: datos, código, Nueva York y piloto Santiago

## F2.1 Objetivo

Construir una cadena reproducible que permita demostrar qué viajes entraron, cómo se reconstruyeron y agregaron, cómo se generaron ambas representaciones espaciales y qué evaluó exactamente cada ejecución de Deep Gravity.

## F2.2 Principio arquitectónico

Implementar un **núcleo común de datos** y dos adaptadores espaciales. No construir dos pipelines independientes.

```text
CSV viajes + CSV etapas
          ↓
viajes canónicos y auditados
          ↓
cohorte y área comunes
          ↓
    ┌─────┴────────┐
adaptador Zona   adaptador H3
    └─────┬────────┘
          ↓
contrato Deep Gravity común
          ↓
entrenamiento, baselines y evaluación
```

## F2.3 Secuencia de trabajo

### F2-A — Preflight técnico y protección de datos

**Subagentes en paralelo:**

- A1 inventario de entorno, dependencias, almacenamiento y hardware;
- A2 inventario de código, bugs, formatos y pruebas existentes;
- A3 inventario muestral de CSV y diccionario, sin leer todavía los 64 GiB completos.

Acciones:

1. configurar la ruta de datos mediante archivo local no versionado o variable específica del proyecto;
2. extender `.gitignore` para crudos, intermedios, cachés, checkpoints y secretos;
3. definir límites de RAM, disco y tiempo antes del procesamiento mensual;
4. adoptar lectura por lotes o motor columnar; queda prohibido cargar el mes completo con `pandas.read_csv()` en una sola operación;
5. crear un manifiesto con archivos, fechas, bytes, esquema, separador y estado de lectura;
6. investigar la ausencia aparente del 30 de noviembre y documentar si es esperada.

**Salida:** manifiesto reproducible y reporte de capacidad.  
**Puerta:** G0.

### F2-B — Auditoría estructural y semántica

Para cada fecha, medir sin exponer identificadores:

- número de filas y columnas;
- estabilidad de esquema y tipos;
- valores especiales (`-`, vacío, cero, negativos);
- duplicados y unicidad de claves candidatas;
- distribución de `n_etapas` y coherencia con etapas enlazadas;
- proporción con bajada y destino estimado;
- validez y rangos UTM;
- cobertura de zona/comuna;
- distribución y significado de los tres factores de expansión disponibles;
- consistencia temporal, distancias y duraciones;
- diferencias entre laboral, sábado y domingo.

Validar específicamente la unión candidata:

```text
viajes.(id_tarjeta, id_viaje)
    ↔ etapas.(id_etapa, correlativo_viajes)
```

No conservar identificadores de tarjeta en artefactos analíticos una vez realizada la unión.

**Salida:** perfil por fecha, informe de unión y diccionario de datos corregido.  
**Criterio de término:** se puede explicar cada descarte y reconciliar filas de entrada, uniones, viajes válidos y salidas.

### F2-C — Contrato canónico de viaje

Crear una tabla intermedia particionada por fecha, preferentemente Parquet, con un esquema mínimo como:

```text
trip_key_hash
service_date
day_type
start_time / end_time / period
origin_x / origin_y
destination_x / destination_y
origin_zone / destination_zone
origin_commune / destination_commune
trip_weight
n_stages
endpoint_quality
exclusion_reason
```

Decisiones que debe resolver el informe antes de producir la cohorte final:

1. clave definitiva de unión;
2. regla para primera etapa y última bajada válida;
3. tratamiento de viajes sin bajada o con destinos imputados;
4. elección del peso principal y sensibilidad sin expansión;
5. viajes intrazonales/intracelda;
6. coordenadas fuera de rango y viajes fuera del área;
7. ventanas horarias y tipos de día;
8. granularidad mensual frente a muestras por día.

La **cohorte primaria comparativa** debe exigir los campos mínimos necesarios para ambas ramas. Cualquier cohorte secundaria de mayor cobertura se reportará por separado y no se usará para afirmar una comparación directa.

**Salidas:** contrato versionado, tabla canónica y reporte de conservación de masa.  
**Puerta:** G2.

### F2-D — Delimitación territorial basada en evidencia

1. obtener o incorporar límites comunales con procedencia y versión;
2. calcular densidad de viajes/orígenes/destinos por comuna y zona;
3. comparar alternativas de área: núcleo urbano, conjunto ampliado y exclusiones periféricas;
4. cuantificar viajes retenidos, celdas activas, cobertura y esparsidad;
5. presentar las alternativas al usuario antes de congelar el polígono;
6. guardar el polígono, CRS, lista de comunas y regla de frontera como artefactos versionados.

La regla de inclusión debe indicar si se exigen ambos extremos dentro del área y cómo se tratan celdas H3 que intersectan el borde.

### F2-E — Adaptadores espaciales y factibilidad H3

**Trabajo paralelo con archivos separados:**

- E1 implementa/adapta la rama Zona 777;
- E2 implementa la rama H3;
- E3 crea pruebas comunes de conservación y geometría.

Rama Zona 777:

- usar los campos zonales auditados de la cohorte canónica;
- incorporar la geometría oficial correspondiente y verificar CRS/IDs;
- no heredar automáticamente la selección de 743 zonas de otro trabajo.

Rama H3:

- transformar EPSG:32719 a WGS84 con orden de ejes probado;
- asignar ambos extremos con `latlng_to_cell`;
- computar H3-r3–r8 en el análisis de factibilidad;
- calcular áreas reales de las celdas presentes, además de promedios globales de referencia;
- conservar celdas completas o documentar explícitamente cualquier recorte/fracción de borde.

Para cada representación producir:

- número total y activo de unidades;
- viajes y masa ponderada por unidad;
- pares OD observados y densidad/esparsidad;
- distribución de flujos;
- proporción de ceros y colas raras;
- costo estimado de memoria/entrenamiento;
- mapas diagnósticos sin datos personales.

**Salida:** informe que recomienda qué resoluciones pasan al piloto; se espera evaluar H3-r6–r8 con especial atención a r7/r8, pero la evidencia decide.  
**Puerta:** primera mitad de G3.

### F2-F — Diseño reproducible de *tiles* y particiones

1. auditar qué significa `tile` en el código original y cómo condiciona destinos, lotes y CPC;
2. definir bloques espaciales mayores que las unidades OD;
3. crear particiones determinísticas de entrenamiento, validación y prueba;
4. evitar que una misma unidad de origen aparezca en más de una partición;
5. documentar el tratamiento de destinos cruzados entre bloques;
6. usar una semilla fija y guardar la asignación completa;
7. buscar equivalencia razonable entre la rama zonal y H3 sin fingir correspondencia perfecta;
8. reservar el conjunto de prueba: la resolución y los hiperparámetros se eligen con validación, no con test.

**Salidas:** archivos de partición, informe de fuga espacial y estadísticas comparables.  
**Puerta:** G3.

### F2-G — Refactor mínimo y pruebas del modelo

Antes de Santiago, crear pruebas pequeñas con resultados conocidos para:

- serialización correcta de `od2flow.pkl`;
- regeneración condicional de caché;
- CPC en casos idéntico, disjunto, nulo y parcialmente solapado;
- conservación del *outflow* por origen;
- universo y muestreo de destinos;
- distancias y centroides;
- carga de particiones;
- evaluación de todos los lotes, sin `break` residual;
- comportamiento con semillas;
- separación entre modo entrenamiento y evaluación.

La prueba de CPC debe detectar expresamente el error del denominador actual: usar un caso donde la masa observada difiera de la predicha y verificar `2·sum(min(obs,pred))/(sum(obs)+sum(pred))`.

Refactor acotado:

1. reemplazar imports dependientes del CWD por imports de paquete;
2. separar preprocesamiento de carga del modelo;
3. introducir configuración declarativa de dataset, resolución, periodo, semilla y rutas;
4. implementar una interfaz común para Zona 777 y H3;
5. versionar cada ejecución en un directorio único;
6. guardar configuración, versiones, logs, métricas, partición y checkpoint;
7. impedir sobrescritura silenciosa de resultados existentes;
8. corregir el denominador de CPC y auditar sus agregaciones por origen y *tile*;
9. resolver si los destinos se restringen al *tile* del origen o al dominio metropolitano, documentando el efecto sobre entrenamiento y evaluación;
10. alinear la arquitectura documentada con la implementación real: sin BatchNorm actualmente, cinco capas con salida 256, diez con salida 128 y dropout efectivo igual a cero en la ruta vigente.

No hacer una reescritura total del repositorio ni cambiar simultáneamente arquitectura, datos e hiperparámetros sin una ablación explícita.

### F2-H — Auditoría de la reproducción de Nueva York

La reproducción de Nueva York es una prueba de referencia del pipeline, no evidencia sobre Santiago.

Acciones:

1. verificar versión del código, dataset, particiones, semillas, dropout y configuración usados;
2. comprobar CPC global y CPC por *tile* con la fórmula y el soporte correctos;
3. separar claramente media sobre todos los *tiles* y media condicionada a *tiles* con CPC no nulo;
4. revisar contra las definiciones y resultados realmente publicados, sin equiparar rangos de manera informal;
5. ejecutar o validar la corrida completa de 20 épocas;
6. conservar el ensayo de 3 épocas solo como *smoke test* técnico, fuera de las conclusiones científicas;
7. producir un manifiesto de ejecución y actualizar el reporte.

**Criterio de término:** otro entorno puede reconstruir qué se ejecutó y por qué el resultado se considera o no una reproducción válida.

**Cierre F2-H — 12 de septiembre de 2026:** auditoría completada. Nueva corrida trazable de 20 épocas, 50.620 actualizaciones y CPC global 0,506684; evaluación de 2.836 orígenes sobre 939.888 pares, conservación de masa y replay independiente verificados. Se corrigieron el soporte del CPC histórico, los conteos de particiones y la comparación con la tabla 1 del artículo (CPC global NY = 0,70). Las medias sobre 193 tiles asignados, 188 con unidades y 163 con CPC positivo se reportan por separado. La ejecución técnica queda validada, pero no se acredita reproducción científica integral: difieren el lote, la pérdida y otros elementos del protocolo o de la procedencia de atributos. Evidencia en `docs/experimentos/REPORTE_REPRODUCCION_NEWYORK.md` y `docs/experimentos/f2h/verification.json`. Continuar F2-I; G4 sigue abierta hasta el piloto de F2-J.

### F2-I — Población y características OSM

Esta fase comienza después de congelar cohorte, área y unidades candidatas.

1. elegir una fuente de población con año, resolución, licencia y método de asignación documentados;
2. obtener una instantánea OSM con fecha y procedencia reproducibles;
3. evaluar primero las categorías del paper y la propuesta de 12 macro-categorías;
4. seleccionar la ontología según cobertura, redundancia y significado, no por un umbral inventado;
5. definir `other` de forma cerrada y auditable;
6. tratar cada geometría según su magnitud:
   - puntos: conteos o tasas;
   - polígonos: área o cobertura;
   - vías: longitud;
7. evitar doble conteo de entidades y definir elementos que cruzan límites;
8. producir para cada variable: nombre, fuente, filtros, unidad, agregación, nulos y normalización;
9. ajustar el tamaño del vector de entrada a las variables efectivamente adoptadas.

**Salidas:** `features` por rama, diccionario de características y pruebas de cobertura.

**Cierre aprobado — 14 de septiembre de 2026:** el investigador aprobó Censo 2024, `paper19` corregido como diccionario principal (19 variables por ubicación, 39 entradas por par) y la exclusión común de los 1.904 viajes con algún extremo en 848, 849 o 852, que carecen de polígono oficial. Las tres ramas conservan 60.511.977 viajes y masa 85.774.522,4070, con 793 zonas, 223 celdas r7 y 1.210 celdas r8. Áreas, puntos y vías usan magnitudes geométricas coherentes; la normalización se ajusta exclusivamente con orígenes activos de entrenamiento. Los seis candidatos pasaron la integración, y los tres contratos principales aprobados se cargaron nuevamente con masa y hashes verificados. Pasaron 11 pruebas F2-I y 37 F2-G antes de la adopción. `macro12_geometry20` queda disponible para diagnóstico; no reemplaza el contrato principal. Los datos F2-C/F2-G originales se conservan como historial. La decisión y los archivos exactos quedan fijados en [ADR-006 aceptado](adr/ADR-006-propuesta-cierre-f2i.md), [contrato aprobado](territorio/f2i/F2-I_CONTRATO_APROBADO.json) y [reporte F2-I](territorio/f2i/F2-I_CIERRE_TECNICO_Y_DECISION.md). **La etapa 6 queda cerrada.** F2-J no se ha iniciado; comenzará por una muestra pequeña, un día laboral y periodos horarios antes del piloto estable. G4 permanece abierta. F2-H no se reabre para perseguir una reproducción integral de Nueva York.

### F2-J — Piloto de Santiago

Ejecutar en escalones:

1. muestra pequeña para verificar el recorrido completo;
2. un día laboral completo elegido por calidad;
3. periodos punta mañana, valle y punta tarde;
4. rama Zona 777 y resoluciones H3 que superaron factibilidad;
5. baselines y Deep Gravity con la misma cohorte y particiones;
6. corridas cortas de diagnóstico separadas de las corridas científicas;
7. corrida piloto estable con semillas y configuración guardadas.

Evaluar al menos:

- CPC con definición y soporte explícitos;
- conservación de masa y *outflow*;
- esparsidad y cobertura;
- desempeño por *tile* y heterogeneidad espacial;
- estabilidad entre semillas;
- tiempo, memoria y tamaño de artefactos;
- comparación Deep Gravity–baselines dentro de cada representación.

El CPC entre resoluciones no se interpreta de manera aislada: una agregación más gruesa puede aumentar el solapamiento por construcción.

**Salida:** reporte del piloto y recomendación de resolución/área/configuración para experimentos finales.  
**Puerta:** G4.

### F2-K — Escalamiento mensual y experimentos finales

Solo después de aprobar el piloto:

1. procesar las 29 fechas de forma incremental y reanudable;
2. comprobar reconciliación diaria y mensual;
3. congelar versiones de cohortes, geometrías, *features* y particiones;
4. ejecutar matriz experimental predefinida, sin seleccionar resultados a posteriori;
5. conservar todos los manifiestos y checkpoints;
6. generar tablas y figuras consumibles por el Frente 1 y posteriormente por el capítulo 5.

### F2-L — XAI diferido

No ejecutar como parte del primer piloto salvo un *smoke test* sintético de compatibilidad.

Cuando el modelo final sea estable:

- fijar función explicada, fondo, muestra, modo `eval` y semilla;
- aplicar SHAP u otra técnica compatible con la salida real del modelo;
- comparar origen/destino sin imponer qué grupo debe dominar;
- acompañar rankings con estabilidad, dispersión y pruebas de sensibilidad;
- evitar conclusiones causales a partir de atribuciones predictivas.

## F2.4 Entregables

- manifiesto de los 58 CSV y del diccionario;
- perfil de calidad y reporte de unión viaje–etapas;
- contrato canónico de viaje y datos intermedios particionados;
- delimitación territorial versionada;
- matrices OD comparables para Zona 777 y H3;
- análisis de factibilidad H3-r3–r8;
- particiones espaciales reproducibles;
- suite mínima de pruebas;
- código adaptado y configurable;
- reproducción de NY re-auditada;
- *features* y diccionario de variables;
- reporte y artefactos del piloto Santiago;
- posteriormente, matriz de experimentos finales y XAI.

## F2.5 Criterios de aceptación

- Ningún paso requiere rutas personales hardcodeadas.
- El procesamiento mensual es incremental y no exige cargar todos los CSV en memoria.
- La clave viaje–etapas y la reconstrucción de extremos tienen métricas de cobertura y coherencia.
- Cada fila descartada pertenece a una categoría contabilizada.
- La masa sin expansión y expandida se reconcilia antes y después de cada transformación.
- Las ramas Zona 777 y H3 parten de una cohorte primaria idéntica.
- H3 se genera desde coordenadas válidas, no mediante redistribución zonal en el escenario principal.
- Resolución, área y *tiles* se seleccionan con validación y diagnósticos, no con el conjunto de prueba.
- CPC y normalización por origen tienen pruebas unitarias.
- La evaluación recorre todo el conjunto correspondiente.
- Cada corrida crea un directorio inmutable con configuración y resultados.
- La evidencia de Nueva York está separada de la de Santiago.
- El piloto puede repetirse desde datos crudos con instrucciones documentadas.

## F2.6 Decisiones que requieren intervención del usuario

El equipo puede preparar evidencia y alternativas, pero no debe congelar unilateralmente:

1. área final de estudio;
2. inclusión/exclusión de viajes sin destino confiable;
3. factor de expansión principal;
4. resoluciones H3 que pasan del piloto;
5. ontología OSM final;
6. fuente de población;
7. protocolo final de partición si existen alternativas con distinto significado científico;
8. presupuesto de cómputo para experimentos mensuales.

---

## 5. Orden recomendado de ejecución

1. **En paralelo:** F1-A y F2-A/F2-B.
2. **Con evidencia inicial:** F1-B y F2-C.
3. **En paralelo coordinado:** F1-C preliminar y F2-D/F2-E/F2-F.
4. **Bloque técnico:** F2-G y F2-H.
5. **Datos enriquecidos:** F2-I.
6. **Integración:** F2-J y decisión de piloto.
7. **Sincronización:** cierre definitivo de F1-C y F1-D/F1-E/F1-F con resultados verificados del piloto.
8. **Después de aprobación:** F2-K, XAI, capítulo 5 y conclusiones.

## 6. Instrucción para iniciar en un nuevo chat

Usar una instrucción como:

> Lee completo `DeepGravity/docs/PLAN_MAESTRO_FRENTES_1_Y_2.md`. Ejecuta únicamente **[indicar fase]**, respetando sus puertas de control, criterios de aceptación y protocolo de subagentes. Antes de editar, inspecciona el estado actual y no sobrescribas cambios ajenos. Al terminar, actualiza en el plan el registro de ejecución y entrega evidencia de las pruebas.

No solicitar “implementar todo el plan” en una única ejecución. Cada fase debe cerrarse y verificarse antes de iniciar la siguiente.

## 7. Registro de ejecución

| Fecha | Frente/fase | Estado | Evidencia o salida | Decisiones pendientes |
|---|---|---|---|---|
| 2026-09-08 | Creación del plan maestro | completado | Este documento | Iniciar F1-A o F2-A/F2-B |
| 2026-09-08 | F2-A — Preflight técnico y protección de datos | completado; G0 cerrado | docs/preflight/F2-A_PREFLIGHT_TECNICO.md, manifiesto de 58 CSV y configuración local ignorada | El 30 de noviembre fue entregado con errores; la cohorte disponible queda en 29 fechas y no se imputará |
| 2026-09-08 | F1-A — Matriz de afirmaciones y contradicciones | completado | docs/revisiones/MATRIZ_TRAZABILIDAD_CAP4.md | Resolver contratos de datos, área, peso, resolución, tiles y arquitectura en sus puertas correspondientes |
| 2026-09-09 | F2-B — Auditoría estructural y semántica | completado; 29 de 29 fechas auditadas | docs/auditoria/F2-B_*.csv y F2-B_REPORTE_AUDITORIA_DTPM_NOV2024.md | F2-C debe resolver el contrato canónico, los destinos sin bajada, el peso principal y la discrepancia de 0,2203 % en n_etapas |
| 2026-09-08 | F1-B — Conciliación del alcance y decisiones | completado | docs/revisiones/F1-B_CONCILIACION_DECISIONES.md; alcance, arquitectura y ADR actualizados | Cerrar contratos de datos, área, peso, resolución, tiles, población y OSM en sus puertas correspondientes |
| 2026-09-09 | F2-C — Contrato canónico de viaje | completado; G2 cerrado | docs/contratos/F2-C_CONTRATO_CANONICO_VIAJE.md, docs/auditoria/F2-C_REPORTE_CONTRATO_DTPM_NOV2024.md y 29 particiones Parquet ignoradas | F2-D decidirá el área territorial; F2-E/F caracterizarán representaciones y tiles |
| 2026-09-09 | G2 — Contrato de datos | cerrado; cohorte primaria y peso aprobados | 60.682.293 viajes primarios; factor_expansion como masa principal y unexpanded_weight=1.0 para sensibilidad | Iniciar F2-D, F2-E y F2-F coordinadamente |
| 2026-09-09 | F2-D — Delimitación territorial | evidencia generada; pendiente de decisión del investigador | docs/territorio/f2d/: DPA 2023, clasificación directa de extremos y alternativas comparables | Elegir núcleo urbano referencial de 34 comunas o Región Metropolitana completa; la regla propuesta exige ambos extremos dentro del área |
| 2026-09-09 | F2-D — Aprobación y fijación territorial | completado; núcleo referencial de 34 comunas aprobado por el investigador | ADR-005, F2-D_AREA_APROBADA.geojson y F2-D_AREA_APROBADA.json; 60.513.881 viajes retenidos, 168.412 fuera del área | Continuar F2-E y F2-F, junto con F1-C preliminar; G3 permanece abierta |
| 2026-09-09 | F2-E y F2-F — Factibilidad y particiones | completadas; G3 cerrada | Zona 777 y H3-r3–r8 medidos sobre la cohorte F2-D; H3-r7/r8 pasan al piloto y 10 tiles de 15 km comparten agenda reproducible | F2-G debe materializar los flujos cruzados en el adaptador y mantener destinos metropolitanos globales |
| 2026-09-10 | G1 — Contrato científico | cerrado; formalización del contrato científico vigente | docs/revisiones/F1-B_CONCILIACION_DECISIONES.md y docs/revisiones/F1-C_ESPECIFICACION_PRELIMINAR_G3.md; objetivos, hipótesis, unidades y términos consolidados | Resolver y verificar las contradicciones pendientes del capítulo 4 en F1-C/F1-E/F1-F antes de cerrar G5; véase la nota de alcance siguiente |
| 2026-09-10 | F2-G — Refactor mínimo y pruebas del modelo | completado; 37 pruebas aprobadas y 29 fechas materializadas | docs/verificacion/f2g/F2-G_REPORTE_IMPLEMENTACION.md, F2-G_VERIFICACION.json y F2-G_PRUEBAS.txt; CPC, caché, destinos globales, evaluación completa y ejecuciones trazables verificados; 60.513.881 viajes y 85.777.662,9386 de masa por rama | Continuar F2-H; población, OSM y geometría faltante zonal antes del entrenamiento científico en F2-I/F2-J; G4 sigue abierta |
| 2026-09-10 | F2-G — Corrección de asignación H3-r7 | verificada; asignación directa conforme al contrato | F2-G_UNIDADES_H3_R7.csv y F2-G_PARTICIONES_UNIDADES.csv: 223 unidades, 220 orígenes activos y 37.196 pares OD; se conserva la agenda de 10 tiles de F2-F | Usar las tablas operativas de docs/verificacion/f2g/ en las siguientes fases; conservar F2-E/F como evidencia histórica y regenerar r3–r6 con el script corregido antes de usar sus estadísticas en la redacción final |
| 2026-09-12 | F2-H — Auditoría de Nueva York | completada; ejecución técnica verificada, equivalencia científica integral no acreditada | docs/experimentos/REPORTE_REPRODUCCION_NEWYORK.md y f2h/verification.json: 20 épocas, CPC global 0,506684, replay independiente, hashes y 37 pruebas aprobadas; reporte histórico archivado | Continuar F2-I con fuentes y transformaciones explícitas; declarar pérdida efectiva y resolver geometría pendiente antes del piloto F2-J; G4 sigue abierta |
| 2026-09-14 | F2-I — Atributos corregidos e integración | ejecución técnica completa; adopción metodológica pendiente | docs/territorio/f2i/F2-I_CIERRE_TECNICO_Y_DECISION.md y F2-I_INTEGRACION_VERIFICADA.json; seis contratos, 11 pruebas F2-I y 37 F2-G aprobadas; ADR-006 propuesto | Adoptar población, ontología y alternativa común de exclusión de 1.904 viajes antes de cerrar la etapa 6; F2-J no iniciado y G4 abierta |
| 2026-09-14 | F2-I — Aprobación y cierre de la etapa 6 | completada y aprobada por el investigador | ADR-006 aceptado, F2-I_CONTRATO_APROBADO.json y tres configuraciones f2i_approved_*_paper19.example.json: Censo 2024, 39 entradas, 60.511.977 viajes comunes y hashes comprobados | Continuar F2-J desde una muestra pequeña; no iniciar directamente experimentos mensuales finales; G4 permanece abierta |

**Alcance del cierre de G1 (10 de septiembre de 2026).** Se formaliza el cierre del contrato científico consolidado en F1-B y precisado en F1-C preliminar: comparación Zona 777–H3 desde una cohorte común, hipótesis abierta y falsable, distinción entre unidades OD y *tiles*, y diferenciación de población censal, generación observada, flujo expandido y atributos OSM. Estas definiciones gobiernan la ejecución posterior. Las contradicciones pendientes del capítulo 4 están identificadas en `docs/revisiones/MATRIZ_TRAZABILIDAD_CAP4.md` y deberán resolverse y verificarse en F1-C/F1-E/F1-F antes de cerrar G5. El cierre de G1 no implica el cierre del Frente 1 ni la sincronización integral del capítulo 4 y `docs/`, que corresponde a G5.

## 8. Estado consolidado — actualización F2-I

| Etapa | Fases | Estado | Cierre o trabajo restante |
|---|---|---|---|
| 1 | F2-A y F1-A | Completada | Preflight, inventario, protección de datos y matriz de trazabilidad; G0 cerrado |
| 2 | F2-B y F1-B | Completada; G1 cerrada | Auditoría de 29 fechas, unión validada y alcance conciliado; cierre del contrato científico formalizado el 10 de septiembre de 2026, con el alcance y la evidencia registrados en la sección 7 |
| 3 | F2-C | Completada | Contrato aprobado, 29 particiones canónicas y G2 cerrado |
| 4 | F2-D; F1-C preliminar, F2-E y F2-F | Completada; G3 cerrada | Dominio F2-D aprobado, factibilidad exacta Zona 777/H3, H3-r7/r8 para piloto y 10 tiles determinísticos documentados en `docs/territorio/f2e`, `docs/territorio/f2f` y `docs/revisiones/F1-C_ESPECIFICACION_PRELIMINAR_G3.md` |
| 5 | F2-G y F2-H | Completadas | 37 pruebas, OD mensual reconciliada y Nueva York auditado con 20 épocas y CPC global 0,506684. Dictamen técnico y límites de reproducción científica documentados en `docs/experimentos/`; G4 sigue abierta hasta el piloto Santiago |
| 6 | F2-I | Completada y aprobada | Censo 2024, paper19 corregido (39 entradas), cohorte común de 60.511.977 viajes y contratos fijados en ADR-006 y F2-I_CONTRATO_APROBADO.json |
| 7 | F2-J | Habilitada; aún no iniciada | Comenzar por muestra pequeña, día laboral y periodos horarios; piloto Santiago reproducible para cerrar G4 |
| 8 | Cierre F1-C; F1-D, F1-E y F1-F | Pendiente | Capítulo 4 y documentación sincronizados y verificados; G5 |
| 9 | F2-K | Pendiente tras aprobar el piloto | Experimentos mensuales finales reutilizando las particiones canónicas existentes |
| 10 | F2-L, capítulo 5 y conclusiones | Pendiente | XAI final y redacción de resultados |
