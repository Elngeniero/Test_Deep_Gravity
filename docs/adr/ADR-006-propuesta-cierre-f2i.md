# ADR-006: Contrato aprobado de atributos y cohorte común para F2-I

- **Fecha:** 2026-09-14.
- **Estado:** Aceptado por el investigador el 2026-09-14 mediante el mensaje «si apruebo».
- **Relación:** Complementa ADR-005 y el contrato operativo F2-G para los experimentos posteriores. Conserva los datos originales y fija una cohorte común derivada para F2-J. Se mantiene el nombre histórico de este archivo para preservar los enlaces de la propuesta.

## Contexto

Las zonas activas 848, 849 y 852 carecen de polígono oficial verificable. Las referencias cartográficas alternativas examinadas no acreditan correspondencia con la codificación operativa DTPM. Sin geometría, no pueden asignarse población, área o características OSM científicamente justificadas a esas unidades. La comparación exige la misma cohorte fuente en Zona777 y H3.

## Decisión aprobada

1. Adoptar INE Censo 2024, manzanas y entidades, con interpolación areal en EPSG:32719 y densidad por área de unidad.
2. Adoptar OSM Chile del 1 de enero de 2024 y `paper19` corregido como diccionario principal: 19 variables por ubicación y 39 entradas por par OD. Mantener `macro12_geometry20`, con 20 variables y 41 entradas, como alternativa diagnóstica.
3. Excluir de las tres ramas los mismos viajes que tengan origen o destino en 848, 849 o 852, después del filtro territorial aprobado y antes de agregar OD. Se retiran 1.904 viajes y 3.140,5316 de masa expandida; quedan 60.511.977 viajes y 85.774.522,4070 de masa en cada rama.
4. Mantener las 34 comunas, reglas de extremos estrictos, tiles y particiones espaciales. Conservar las celdas H3 completas como destinos; retirar únicamente los tres IDs sin polígono del universo zonal. Ajustar normalización exclusivamente con orígenes activos de entrenamiento de la cohorte resultante.
5. Preservar F2-C/F2-G y los atributos originales como evidencia histórica; adoptar los productos verificados en `processed/f2i/proposal_common_exclusion/` mediante los hashes del [contrato aprobado](../territorio/f2i/F2-I_CONTRATO_APROBADO.json). Los manifiestos de propuesta conservan su estado histórico; el nuevo registro acredita su adopción.

## Consecuencias

La comparación queda materializada con 793 zonas, 223 celdas H3-r7 y 1.210 celdas H3-r8. No se introduce geometría fabricada ni se confunde población con generación observada. Se pierde una fracción pequeña pero explícita de los viajes: 0,003146 %. La exclusión condiciona el alcance de los experimentos y debe declararse en la tesis.

La ausencia en OSM, la antigüedad relativa de la instantánea, la interpolación censal y la correspondencia temática incompleta con el artículo siguen siendo limitaciones. El resultado no acredita reproducción integral del artículo ni desempeño de Santiago. F2-H permanece cerrada; F2-J y G4 esperan el piloto.

## Evidencia y adopción

Los seis contratos candidatos pasaron la integración sin entrenamiento. Tras la aprobación se verificaron los hashes de los productos y se cargaron nuevamente los tres contratos principales con el adaptador científico, conservando la masa mensual y las 19 variables por unidad. El registro definitivo es [F2-I_CONTRATO_APROBADO.json](../territorio/f2i/F2-I_CONTRATO_APROBADO.json); las configuraciones de datos adoptadas son `config/f2i_approved_{zona777,h3_r7,h3_r8}_paper19.example.json`.

**F2-I y la etapa 6 quedan cerradas.** F2-J queda habilitada para comenzar por una muestra pequeña; no se ha iniciado entrenamiento. G4 sigue abierta hasta verificar el piloto y G5 espera la sincronización documental posterior.
