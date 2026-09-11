# F1-C preliminar — Especificación consolidada para G3

La comparación Santiago queda definida sobre la cohorte primaria F2-C y el núcleo urbano aprobado de 34 comunas. Ambos extremos deben estar estrictamente contenidos en los polígonos DPA de F2-D en EPSG:32719; se retienen 60.513.881 viajes (99,7225% de la cohorte) y la exclusión territorial es 0,2775%.

La rama de control usa `origin_zone` y `destination_zone` y la geometría oficial ShapeZona777 de DTPM, con las excepciones de procedencia identificadas en F2-E. La rama H3 transforma coordenadas UTM con `always_xy`, asigna los dos extremos con `latlng_to_cell` y mantiene celdas completas en el borde. H3-r7 y H3-r8 pasan al piloto; r3–r6 no pasan por granularidad insuficiente.

Los tiles son cuadrados de 15 km en EPSG:32719 y no son unidades OD. Se usan 10 tiles comunes para Zona 777, H3-r7 y H3-r8, separados de forma determinística con semilla 20260909 en entrenamiento, validación y prueba. Cada origen pertenece a una sola partición. Los destinos y los flujos entre tiles permanecen en el dominio aprobado; F2-G debe adaptar el loader original, que todavía limita candidatos al tile de origen.

Esta especificación reemplaza las afirmaciones de un único tile metropolitano, de una selección heredada de 743 zonas y de grillas cuadradas vigentes. La selección de resolución e hiperparámetros usará validación; prueba permanece reservada.
