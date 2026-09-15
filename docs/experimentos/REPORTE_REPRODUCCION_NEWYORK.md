# Auditoría F2-H de Deep Gravity sobre Nueva York

> **Autor:** Pablo Campos  
> **Fecha:** 12 de septiembre de 2026  
> **Estado:** F2-H completada; corrida de 20 épocas y evaluación independiente verificadas  
> **Alcance:** prueba de referencia del pipeline; no constituye evidencia sobre Santiago.

## 1. Dictamen y alcance

F2-H audita la ejecución local de Nueva York y corrige la interpretación del reporte del 13 de agosto. La comparación anterior entre una media filtrada de 0,5119 y un supuesto rango publicado de 0,45–0,50 no acredita la reproducción científica. La tabla 1 del artículo informa **CPC global de 0,70 para Deep Gravity en New York State**. Los promedios por tiles y por deciles son agregaciones diferentes.

La ejecución nueva conserva explícitamente el propósito `legacy_audit`: permite verificar entrenamiento, distancias, conservación y evaluación sobre el caché disponible, pero no acredita equivalencia integral con el protocolo publicado. Quedan documentadas diferencias de pérdida, tamaño de lote, arquitectura descrita, particiones y procedencia/normalización de atributos. Completar esta auditoría no exige afirmar una equivalencia que la evidencia no sostiene.

**Resultado de la corrida nueva:** CPC global **0,506684**, con 20 épocas completas y 50.620 actualizaciones del optimizador. El replay independiente coincide por origen con error máximo de 4,44 × 10⁻¹⁶. No se usó el conjunto de prueba para elegir época ni ajustar esta configuración. La ejecución técnica queda verificada; la reproducción científica integral del artículo no queda acreditada.

| Métrica del checkpoint nuevo | Resultado |
|---|---:|
| CPC global, indicador principal | **0,506684** |
| Media sobre los 193 tiles asignados | 0,773266 |
| Media sobre los 188 tiles con unidades | 0,793831 |
| Media condicionada a los 163 tiles con CPC positivo | 0,915585 |
| Media sobre los 2.836 orígenes | 0,423777 |

Estas medias no sustituyen el CPC global ni demuestran superioridad frente al resultado publicado. Los manifiestos y las métricas completas están enlazados desde [verification.json](f2h/verification.json).

El reporte previo se conserva literalmente en [el archivo histórico](f2h/REPORTE_HISTORICO_20260813.md). Sus conclusiones sobre fidelidad al paper, normalización por área y convergencia a las tres épocas quedan sustituidas por este documento.

## 2. Dataset, particiones y procedencia

Los hashes de todos los archivos locales de Nueva York, del checkpoint antiguo y de su CSV están en [inventory.json](f2h/inventory.json). El código del núcleo corresponde al commit `5fcb6af40428a1f25efe64734d7d83953532e98d`; cada ejecución nueva guarda además una copia de los módulos Python y sus SHA-256.

| Concepto | Evidencia local |
|---|---:|
| Unidades con atributos y centroides en caché | 5.411 |
| Unidades asignadas a tiles | 5.367 |
| Unidades con atributos sin tile; no son orígenes evaluados | 44 |
| Tiles del mapa / con unidades | 475 / 379 |
| Entrenamiento: tiles asignados / con unidades / orígenes | 192 / 191 / 2.531 |
| Prueba: tiles asignados / con unidades / orígenes | 193 / 188 / 2.836 |
| Tiles presentes en ambos conjuntos | 0 |
| Tiles del mapa no incluidos en las particiones | 90; todos vacíos |
| Partición de validación | No existe en este caché |
| Pares OD en el CSV y en el diccionario serializado | 618.316; valores conciliados exactamente |
| Masa total en el CSV procesado | 41.306.407 |
| Pares con algún extremo fuera de los atributos / masa | 133.927 / 8.567.506 |

Los 90 tiles sin partición no deben confundirse con los seis tiles vacíos que sí fueron asignados: uno a entrenamiento y cinco a prueba. Los IDs y conteos completos están en [partitions_tiles.csv](f2h/partitions_tiles.csv). Se conserva el split existente; no hay evidencia suficiente para reconstruir la semilla de su creación ni acreditar estratificación por deciles.

El caché no tiene manifiesto de generación ni está acompañado de `flows.csv` crudo. Por eso la reproducción documentada comienza desde esos archivos procesados, identificados mediante hashes. El artículo menciona 5.367 CT y una masa de 41.070.279; coincidir en el número de unidades asignadas no demuestra igualdad de versiones o de soporte de los flujos. La masa del CSV local difiere en 236.128 y no se fuerza su conciliación sin procedencia adicional.

El adaptador excluye pares fuera de cobertura para formar el dominio con atributos y conserva el flujo saliente del CSV completo como diagnóstico y predictor heredado. El soporte objetivo de esta auditoría son los destinos del mismo tile del origen; los flujos que lo cruzan quedan fuera del CPC. Esta elección corresponde al ensayo NY y no modifica el soporte metropolitano global aprobado para Santiago.

## 3. Coordenadas, áreas y atributos

El caché almacena coordenadas en orden longitud–latitud. El código anterior las entregaba a una función que esperaba latitud–longitud. F2-G corrigió esa interpretación; la corrida nueva usa el orden correcto tanto al entrenar como al evaluar. La distancia es esférica, en km, con radio 6.371,01 km. La geometría original declara EPSG:4269; esta auditoría conserva sus anclajes históricos y no acredita una nueva derivación geográfica desde fuentes.

El campo histórico `area_km2` se obtuvo calculando área sobre coordenadas angulares y dividiendo por un millón. La mediana de su cociente respecto del área proyectada en EPSG:5070 es aproximadamente 1,068 × 10⁻¹⁰. [area_audit.csv](f2h/area_audit.csv) permite comprobar el problema por unidad. Ese campo no se usa para transformar los atributos en la ejecución auditada; no se corrige el caché silenciosamente durante el experimento.

Los 18 atributos guardados coinciden con las columnas numéricas 0–17 de `features.csv` para las 5.367 unidades disponibles en ese CSV: diferencia absoluta máxima 8,47 × 10⁻²². No hay diccionario local suficiente para acreditar sus categorías, magnitudes y normalización previa. El runner los utiliza como fueron suministrados y no divide por área. Se retira, por tanto, la afirmación anterior de que todos los atributos efectivos estaban normalizados por el área de la zona.

El vector efectivo tiene 39 componentes: 18 atributos y el logaritmo del flujo saliente por cada extremo, más la distancia. El flujo saliente se limita inferiormente a 10⁻⁶ antes del logaritmo. **El artículo sí declara esta aproximación de población para Nueva York**, en Methods, página 11. Su presencia no es por sí sola una desviación respecto del caso NY publicado; tampoco la convierte en población censal independiente ni autoriza su uso automático en Santiago. La restricción que permite utilizarla solamente en `legacy_audit` se mantiene.

## 4. CPC y soporte verificado

Para un conjunto de pares OD S:

    CPC(S) = 2 × sum(min(observado, predicho)) / (sum(observado) + sum(predicho))

Ambas sumas y el numerador utilizan exactamente S. Por origen, las probabilidades softmax se multiplican por la masa observada dirigida a los destinos de su mismo tile. Se incluyen los viajes intrazonales y todos los destinos candidatos, también los pares observados en cero. La evaluación no muestrea ni trunca destinos.

| Soporte de prueba | Valor |
|---|---:|
| Orígenes visitados una vez | 2.836 |
| Pares OD candidatos evaluados | 939.888 |
| Masa observada dentro del tile | 12.421.750 |
| Flujo saliente completo de esos orígenes en el CSV | 18.176.489 |
| Flujo fuera del soporte intratile | 5.754.739 |
| Fracción del flujo completo cubierta por el soporte | 68,3397 % |

El **CPC global** se obtiene sumando los componentes de todos los pares antes de dividir. El CPC de un tile suma primero los componentes de sus orígenes. La media aritmética entre tiles les asigna igual peso y no equivale al global: cuatro tiles con más de 100 unidades concentran el 64,8562 % de la masa evaluada, mientras 48 tiles tienen una sola unidad. Véase [support_by_tile_size.csv](f2h/support_by_tile_size.csv).

Se reportan tres medias distintas: sobre los 193 tiles asignados, sobre los 188 que contienen unidades y sobre los 163 con CPC positivo. Para denominador nulo se registra CPC = 0 como convención explícita; no se interpreta como un fracaso predictivo. Los 25 tiles no vacíos con masa nula tampoco tienen flujo saliente en el CSV completo. Los cinco tiles sin unidades se incorporan al promedio sobre los 193 asignados con esa misma convención. Filtrar los ceros no constituye un criterio de validez científica.

## 5. Reconstrucción de la evidencia histórica

El checkpoint previo contiene únicamente los estados del modelo y del optimizador. Los 32 estados de parámetros registran 50.620 pasos: son compatibles con 20 épocas de 2.531 orígenes y lote 1. No almacenan época, semilla ni configuración, por lo que no bastan para acreditar todos los detalles de la corrida histórica.

| Evaluación del checkpoint histórico | CPC global coherente | Media 193 asignados | Media 188 con unidades | Media 163 con CPC positivo |
|---|---:|---:|---:|---:|
| Conservando la interpretación antigua de los ejes | 0,488422 | 0,769563 | 0,790031 | 0,911201 |
| Corrigiendo los ejes solamente al evaluar | 0,509373 | 0,775742 | 0,796374 | 0,918517 |

La segunda fila es una sensibilidad del mismo checkpoint; no es un modelo reentrenado con distancias correctas. No se usa para escoger hiperparámetros de la corrida nueva, cuya configuración quedó fijada antes de estos diagnósticos.

El CSV original tenía media 0,443844 sobre 188 tiles y 0,511919 sobre los 163 con CPC positivo. Se reconstruye con error absoluto máximo de 5,154 × 10⁻⁸ al conservar los ejes antiguos y su cociente mixto:

    numerador de los pares dentro del tile / (2 × flujo saliente completo)

Ese cociente no es el CPC de las predicciones intratile con denominador observado más predicho sobre el mismo soporte. Las columnas `legacy_mixed_support_ratio` y `cpc` de los CSV de auditoría lo distinguen. El error de soporte y el error general del denominador repetido eran problemas distintos; la conservación de masa podía ocultar este último.

El ensayo histórico de tres épocas se conserva exclusivamente como smoke test relatado en el reporte anterior. No se dispone de un checkpoint separado y trazable para comprobarlo. Se retiran las conclusiones de convergencia a tres épocas y de equivalencia científica entre tres y veinte épocas.

## 6. Protocolo publicado frente a ejecución efectiva

La referencia examinada es [Simini et al. (2021), A Deep Gravity model for mobility flows generation](https://www.nature.com/articles/s41467-021-26752-4), especialmente páginas 3–6, 8 y 10–12. La tabla 1 se verificó visualmente en la copia PDF local. [paper_reference.json](f2h/paper_reference.json) fija su hash y los valores consultados.

| Aspecto | Publicación | Ejecución F2-H |
|---|---|---|
| CPC global NY, tabla 1 | DG 0,70; NG 0,68; MFG 0,28; G 0,06 | DG 0,506684; no se entrenan aquí los otros modelos |
| Repeticiones y split | Cinco experimentos; 50/50 estratificado por deciles | Un split heredado fijo; una semilla nueva, 1234 |
| Épocas y optimizador | 20; RMSprop, lr 5 × 10⁻⁶, momentum 0,9 | Coinciden; las 20 épocas se completaron |
| Tamaño de lote | 64 orígenes | 1 origen |
| Pérdida, ecuación 4 | Objetivos fraccionales y_ij/O_i | Suma de conteos × log-softmax, sin dividir cada origen por O_i |
| Capas ocultas descritas | Seis de 256 y nueve de 128 | Cinco de 256 y diez de 128; sin BatchNorm |
| Dropout | No se deduce un valor de la tabla de resultados | Efectivo 0,0; no proporciona regularización por descarte |
| Destinos de entrenamiento | Hasta 512 muestreados | Hasta 512, sin reemplazo, sin cuota forzada de destinos positivos |
| Soporte espacial NY | Viajes dentro de cada región de interés | Destinos del mismo tile, completos en evaluación |
| Atributo poblacional NY | Aproximación por flujo saliente | log del flujo saliente completo del caché |
| Normalización por área | Declarada para atributos de cada lugar | No acreditada en el caché; el runner no la aplica |

El texto y el código local no deben presentarse como idénticos. La referencia 83 remite al [registro de código en Zenodo](https://zenodo.org/records/5573573), rotulado como versión 1.1.0 y enlazado a una release v.1.0.0; F2-H identifica esa referencia, pero no acredita una reconstrucción byte a byte de dicho archivo histórico. Las diferencias anteriores bastan para no afirmar reproducción científica integral, independientemente de la cercanía numérica del CPC.

## 7. Ejecución nueva, evidencia y reconstrucción

Entorno observado: Windows, CPU con dos hilos de PyTorch, Python 3.8.20, torch 1.13.1+cpu, numpy 1.24.3 y pandas 2.0.3. Las bibliotecas de la auditoría geográfica y sus versiones están registradas en el inventario y en [requirements-f2h.txt](f2h/requirements-f2h.txt). Estas son versiones efectivamente utilizadas; no se atribuyen al paper restricciones de instalación que no fueron verificadas.

La configuración de entrenamiento está en `config/f2h_new_york.example.json`. Se fijaron 20 épocas desde el inicio, sin evaluación de test por época ni selección de checkpoint. El runner no realiza evaluación de validación porque esa partición no existe. La semilla base inicializa modelo y generadores; cada época usa 1234 + época, y el muestreo de destinos tiene derivación determinista por origen y época.

Desde la raíz de DeepGravity, con el entorno anterior activo:

    python -B audit_f2h_new_york.py inventory
    python -B run_deepgravity.py --config config/f2h_new_york.example.json
    python -B audit_f2h_new_york.py finalize

La primera operación audita el caché y reproduce el resultado antiguo. La segunda crea la corrida de 20 épocas. La tercera exige checkpoint completo y 50.620 pasos, ejecuta una evaluación separada y contrasta cada origen con un replay independiente que calcula distancias vectorizadas y CPC mediante la identidad de error L1. Los resultados deben coincidir dentro de tolerancias explícitas. No se importa la función de CPC del runner para esa comprobación independiente.

Los nombres de corrida identifican esta ejecución y el runner rechaza sobrescribir carpetas existentes. Para repetir desde cero en el mismo checkout, se necesita otra raíz de resultados y actualizar las rutas de entrenamiento/evaluación del script; no borrar el experimento existente. En un entorno limpio se pueden usar directamente los nombres registrados. Los inputs procesados deben coincidir con los hashes del inventario.

El checkpoint nuevo, la copia de código y las salidas completas quedan en `runs/f2h_new_york/`, ignorado por Git. Las copias de manifiestos, configuraciones, historia de entrenamiento y tablas por origen/tile se conservan en `docs/experimentos/f2h/`. El índice de archivos está en [README.md](f2h/README.md). La huella del checkpoint permite verificar una copia transferida; la equivalencia binaria entre plataformas diferentes no se presupone.

**Verificación final aprobada:** 20 épocas consecutivas, 2.531 orígenes por época y 50.620 pasos en los 32 estados de parámetros del optimizador. El entrenamiento tomó 987,17 s (16 min 27 s); la evaluación del runner, 37,64 s. La pérdida de entrenamiento por origen pasó de 11.330,71 a 10.100,26; esta magnitud ponderada por conteos no es un CPC ni acredita convergencia científica.

Se verificaron 2.836 orígenes sin duplicación, sus 939.888 pares candidatos y la conservación de 12.421.750 de masa; el error máximo de conservación por origen fue 3,64 × 10⁻¹². El replay independiente coincide con el runner en el CPC global y difiere como máximo 4,44 × 10⁻¹⁶ por origen. También pasaron las **37 pruebas de regresión** en 10,603 s; el detalle está en [regression_tests.txt](f2h/regression_tests.txt). Todos los hashes de los inputs y del resultado histórico permanecen iguales; los módulos del núcleo coinciden con el snapshot del entrenamiento.

El checkpoint final tiene SHA-256 `3eed68726dcb08f59b72fa20916bb1f3e35d8f265d2f769a4f0ec28b935662c4`. [verification.json](f2h/verification.json) registra su ruta, las tolerancias observadas y las huellas de la evidencia. F2-H cumple su criterio de término como auditoría reproducible con dictamen explícito de sus límites.

## 8. Continuación del plan

El siguiente paso es F2-I: fijar población y atributos OSM para Santiago, con fuentes y transformaciones explícitas. Deben resolverse allí las cuestiones de atributos y geometría pendientes para poder ejecutar el piloto de F2-J, cuyo protocolo debe declarar también la pérdida efectiva. G4 permanece abierta hasta contar con ese piloto reproducible; esta auditoría de Nueva York no la cierra por sí sola.
