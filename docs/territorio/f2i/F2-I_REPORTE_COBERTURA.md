# F2-I — Cobertura reproducible de población y OSM

> **Reporte histórico sustituido.** La ejecución original terminó, pero su agregación sumaba áreas superpuestas, contaba polígonos como objetos y su candidato macro12 omitía población en el CSV. Sus magnitudes y la afirmación de 27 entradas no constituyen el contrato vigente. Consultar [cierre técnico y decisión](F2-I_CIERRE_TECNICO_Y_DECISION.md), [verificación corregida](F2-I_VERIFICACION_V2.json) y [contratos comprobados](F2-I_INTEGRACION_VERIFICADA.json). Se conserva este texto como evidencia de la primera ejecución.

Generado: `2026-09-13T22:15:11Z`. Este reporte genera alternativas y **no congela** la ontología ni la fuente sin la decisión del investigador.

## Fuentes

- Población: INE, Censo de Poblacion y Vivienda 2024, Manzanas y Entidades (2024); licencia CC BY-SA 4.0.
- OSM: Geofabrik historical OpenStreetMap extract for Chile; instantánea declarada 2024-01-01T23:33:00Z; licencia ODbL-1.0.
- Huella Censo: `75dca77a56128fdd2b950801da645a12b7c1b662f7d7632eb33cb7ee8c3f0a88`.
- Huella OSM: `a10e7a185d5eabc7b1a0ded397c6b7a0a6edba8ce5d50805d440783e311a32a3`.

## Reglas aplicadas

- Población: reparto areal exacto de las manzanas/entidades Censo sobre la geometría completa de cada unidad, en EPSG:32719.
- Usos de suelo: área de la intersección por unidad; vialidad: longitud de la intersección; POI y edificios: conteo por punto representativo interior.
- Cada vía entra a una sola clase. Los POI se priorizan salud, educación, alimentación, comercio y transporte. Un nodo y polígono con igual nombre y categoría se cuentan una vez.
- Los puntos en límite quedan sin asignar. `other` solo registra servicios etiquetados fuera de las clases fijas y no entra al vector paper19.

## Candidatos evaluados

- `paper19`: 19 atributos de ubicación (población + 18 OSM); vector de par `39 = 19 + 19 + distancia`.
- `macro12`: 12 atributos OSM de la propuesta Santiago; vector de par `27 = 12 + 12 + población origen + población destino + distancia`.

## Cobertura

| Representación | Unidades | paper19 finitas | macro12 finitas | Estado |
|---|---:|---:|---:|---|
| zona777 | 796 | 793 | 793 | bloqueada por geometría no oficial |
| h3_r7 | 223 | 223 | 223 | apta para selección |
| h3_r8 | 1210 | 1210 | 1210 | apta para selección |

## Bloqueo Zona777

Las zonas `848, 849, 852` están en el universo activo, pero no tienen polígono oficial en el shapefile DTPM. Bajo `zone_geometry_policy=strict` no se fabrican atributos ni se habilita el entrenamiento científico de Zona777.

## Archivos generados

`C:\Users\pablo\Documents\070.- MEMORIA DE PABLO CAMPOS\Modelo_Deep_Gravity\DeepGravity\deepgravity\data\santiago\processed\f2i` contiene, para cada representación, `paper19_features.csv`, `macro12_features.csv` y el diccionario JSON correspondiente. Los CSV no se cargan al modelo hasta la decisión de ontología.
