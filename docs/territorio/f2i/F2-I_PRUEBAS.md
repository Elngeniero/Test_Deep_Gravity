# F2-I — Registro de verificaciones

Estado documental: 14 de septiembre de 2026.

| Comprobación | Entorno | Resultado |
|---|---|---|
| `python -B -m unittest tests.test_f2i_geometry_v2 tests.test_f2i_feature_rules -v` | Runtime geoespacial Python 3.12, verificación final 14/09 | 11 pruebas aprobadas |
| `python -B -m unittest discover -s tests -p test_f2g.py -v` | Entorno `deepgravity`, Python 3.8.20, ejecución 14/09 | 37 pruebas aprobadas en 10,802 s |
| `python tools/verify_f2i_integration.py` | Entorno `deepgravity`, PyTorch 1.13.1 CPU, ejecución 13/09 | Seis contratos aprobados; salida de proceso 0 |
| `python -B tools/adopt_f2i_contract.py --approval-note "si apruebo"` | Entorno `deepgravity`, registro 14/09 | Tres contratos principales cargados, hashes originales y propuestos verificados, masa conciliada; salida de proceso 0 |

Las 8 pruebas geométricas nuevas cubren unión de áreas superpuestas, agujeros, reparto de vías sobre límites, pertenencia estricta de puntos, taxonomía cerrada, separación de magnitudes y dimensiones, ajuste exclusivo con entrenamiento y construcción de áreas antes del filtro nativo OSM. Las 3 pruebas previas conservan la auditoría histórica de reglas.

El primer intento de cargar F2-G mediante `tests.test_f2g` falló por resolución del módulo en Python 3.8; la orden correcta de descubrimiento indicada arriba ejecutó las 37 pruebas. Hubo avisos de GDAL_DATA y deprecación de bibliotecas, sin pruebas fallidas. Las corridas de esa suite usan datos sintéticos y no constituyen F2-J.

La [verificación de integración](F2-I_INTEGRACION_VERIFICADA.json) registra todas las formas de tensor, reconciliación de masa, hashes y normalización. No se creó optimizador ni se evaluaron métricas de desempeño del modelo sobre datos Santiago. El contrato original Zona777 con valores ausentes continúa rechazado.

La [adopción definitiva](F2-I_CONTRATO_APROBADO.json) fija los tres contratos principales tras la aprobación explícita del investigador. Los manifiestos y configuraciones de propuesta conservan su estado histórico; el registro aprobado identifica sus hashes y los reemplaza como autoridad de estado. No fue necesario regenerar CSV ni repetir entrenamiento o pruebas sin cambios de lógica.
