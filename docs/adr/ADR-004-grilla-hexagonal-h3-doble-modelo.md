# ADR-004: Comparación Zona 777-H3

- **Fecha original:** 2026-09-01
- **Estado:** aceptado, con corrección factual del 2026-09-08
- **Reemplaza:** ADR-002 como decisión espacial activa

## Contexto

La tesis compara dos representaciones espaciales para evaluar la sensibilidad de Deep Gravity a la discretización:

1. zonas DTPM o 777 irregulares;
2. celdas H3.

El trabajo de Vicente Mackenzie se conserva como antecedente interno. No determina un resultado esperado, un número definitivo de zonas, ni funciona como réplica o control experimental equivalente.

## Decisión

Las dos ramas se construirán desde una cohorte canónica común y compartirán, en lo posible, periodos, pesos, fuentes de atributos y particiones.

H3-r3 a H3-r8 se evaluarán primero en factibilidad. La resolución final se elegirá con validación y diagnósticos de cobertura, viajes por celda, esparsidad, estabilidad y costo computacional. No se ha seleccionado todavía una resolución ni se ha fijado la extensión del área.

La asignación H3 se hará desde extremos válidos de etapas reconstruidos a nivel de viaje, una vez validada la unión viajes-etapas. No se presupone asignación directa desde viajes.

## Corrección factual fechada

H3 es un sistema jerárquico de índices geoespaciales, no una grilla plana de hexágonos exactamente iguales. Sus áreas y distancias varían geográficamente, hay pentágonos y no toda celda tiene seis vecinos. Las medidas de área y arista de referencia son promedios, no radios intercambiables.

H3 tampoco elimina el MAUP. El efecto de la discretización es precisamente la hipótesis metodológica que se medirá.

## Consecuencias

- No se construyen pipelines independientes: hay un núcleo común de viajes y dos adaptadores.
- Un resultado nulo o contrario sobre CPC o atribuciones de destino sigue siendo válido.
- Los tiles son bloques de partición o evaluación y no equivalen a una zona o celda OD.
- SHAP u otra XAI se ejecutará solo después de estabilizar datos, modelo y evaluación.
