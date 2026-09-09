# F2-C — Contrato canónico de viaje DTPM

**Versión:** 1.0 aprobada  
**Fecha:** 9 de septiembre de 2026  
**Estado:** aprobada; G2 cerrada el 9 de septiembre de 2026.

## Unidad y privacidad

Una fila representa un viaje unido por la clave validada en F2-B: viajes.(id_tarjeta, id_viaje) con etapas.(id_etapa, correlativo_viajes).

La tabla no conserva esos identificadores. Usa trip_key_hash, un SHA-256 con una sal local persistente e ignorada por Git.

## Campos y reglas

| Grupo | Procedencia y transformación |
|---|---|
| Fecha y tipo de día | Nombre del archivo y calendario civil. |
| Tiempo y periodo | Viajes; los tiempos se convierten a timestamp cuando el formato fuente es válido. |
| Origen | Primera etapa por correlativo_etapas, con coordenadas UTM dentro del rango técnico amplio. |
| Destino | Bajada válida de la etapa final; la secundaria usa la última bajada válida disponible. |
| Zona y comuna | Campos consolidados de viajes. |
| Masa | trip_weight usa factor_expansion; unexpanded_weight es 1.0. |
| Calidad | Cohorte, calidad de extremos y causa exclusiva de no pertenecer a la primaria. |

El rango técnico de coordenadas es X 100.000 a 900.000 e Y 5.000.000 a 10.000.000. No define el área de estudio.

## Cohortes

La primaria para comparar Zona 777 y H3 exige secuencia completa de etapas, origen de la primera etapa, bajada válida en la etapa final, bandera ultimaetapaconbajada, zonas de origen y destino y factor de expansión no negativo.

La secundaria conserva viajes con origen y última bajada observada que no cumplen todos los requisitos de la primaria. Se reporta por separado y no se usa para la comparación principal.

Los intrazonales se mantienen marcados. F2-D decidirá el área territorial y F2-E definirá el tratamiento de intrazonales e intracelda.

## Peso aprobado

factor_expansion es el peso expandido principal porque el diccionario DTPM lo define a nivel de matriz OD de zonas 777. Los factores de expansión de etapas no sustituyen el peso de viaje. El contrato conserva ambas masas, expandida y sin expansión, para sensibilidad.
