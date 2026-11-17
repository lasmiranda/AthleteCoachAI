# Primer modelo local: clasificación de actividades PAMAP2

**Entrenado y evaluado realmente el 5 de noviembre de 2026, hora local.** El manifiesto de entrenamiento quedó congelado a `2026-11-06T01:00:28.854563+00:00`, antes del comando separado de evaluación. Versión: **`pamap2-activity-gnb-v1`**.

Resultado en participantes reservados para prueba: **58.13% accuracy, 0.528234 macro-F1 y 58.44% balanced accuracy**. Supera al comparador trivial, pero tiene fallos importantes por clase. Es un **primer baseline técnico**, no un modelo listo para producción, de readiness, fatiga, pronóstico deportivo ni lesión. No se conectó a Garmin ni al predictor del demo.

Este documento contiene solo metadatos agregados, métricas y matriz de confusión. Los datos individuales, el ejemplo de inferencia, su predicción y el artefacto permanecen locales, en `.research-data`, excluidos de Git.

## 1. Decisión y entorno

La tarea elegida por el usuario fue **clasificar actividades con PAMAP2**. Se intentó crear un entorno aislado e instalar versiones fijadas de scikit-learn y sus dependencias. El endpoint oficial `files.pythonhosted.org` rechazó el handshake TLS con `SSLV3_ALERT_HANDSHAKE_FAILURE`. También fallaron la comprobación con el cliente nativo y la descarga directa oficial, sin desactivar TLS.

El usuario eligió expresamente **«Entrenar Gaussian Naive Bayes ahora, sin dependencias externas»**. Por eso se implementó este baseline clásico, con parámetros aprendidos de datos reales y aritmética contrastada con ejemplos analíticos. **No se presenta como un modelo de scikit-learn** ni como una red neuronal.

- Runtime real: **CPython 3.11.9, Windows**.
- Dependencias externas: **ninguna**. La app y los comandos de adquisición siguen usando biblioteca estándar.
- No hace falta instalar paquetes, GPU, nube, credenciales ni un entorno virtual.
- No hay aleatoriedad en el clasificador: semilla no aplicable. La partición heredada mantiene `athleteos-research-v1` y su hash determinista por participante.
- No se modificaron permisos ni políticas, ni se desactivó la validación TLS. El entorno de instalación fallido y su caché vacía se eliminaron.

Código ejecutable: [`research_data/training.py`](../research_data/training.py). Fixtures exclusivamente sintéticas: [`tests/test_training.py`](../tests/test_training.py).

## 2. Datos, contrato y cobertura

Fuente: Reiss, A. (2012), *PAMAP2 Physical Activity Monitoring [Dataset]*, UCI, **CC BY 4.0**, https://doi.org/10.24432/C5NW2H . Se atribuye la fuente y se documentan las transformaciones. Procedencia, acceso, hashes de los ZIP y límites de adquisición: [`datos-reales-y-preparacion.md`](datos-reales-y-preparacion.md).

Se usó la preparación existente **`pamap2-protocol-v1`**, sin alterar sus sujetos o ventanas: nueve grabaciones **Protocol**, 2,872,533 muestras fuente y 3,833 ventanas de 500 muestras nominalmente de cinco segundos, no solapadas, de una sola actividad y un solo participante. Se excluyen etiqueta transitoria 0, límites/gaps incompletos y el subconjunto Optional. No se fusiona con corredores ni FitRec.

| Partición fija | Ventanas | Participantes | Clases presentes | Clases ausentes |
|---|---:|---:|---:|---|
| Entrenamiento | 2,352 | 5 | 12 | Ninguna |
| Validación | 977 | 2 | 12 | Ninguna |
| Prueba final | 504 | 2 | 12 | Ninguna |

No hay participantes compartidos entre particiones. `verify_prepared` volvió a comprobar hashes, X/y/índices, correspondencia con filas canónicas, ventanas no solapadas y normalización previa calculada solo con entrenamiento. La lectura de prueba anterior al ajuste se limita a estas comprobaciones y cobertura; **no se usan sus predicciones, métricas ni distribución para seleccionar el modelo**.

### Features y unidades

Se cargan las **120 features crudas por ventana**, no el CSV ya normalizado: media, SD poblacional y fracción observada de 40 canales. Se evita normalizar dos veces. Orden exacto en `research_data.pamap2.FEATURES`, `dictionary.json` y `frozen.json`.

- FC: bpm; **no HRV ni FC en reposo**.
- Temperatura por sensor: grados Celsius.
- Acelerómetros de dos rangos, mano/pecho/tobillo y tres ejes: m/s².
- Giroscopios: rad/s; magnetómetros: µT.
- SD: unidad del canal correspondiente; fracción observada: adimensional, entre 0 y 1.
- Orientaciones inválidas de la fuente: excluidas.
- ID de participante, fila, instante, split y etiqueta: **fuera de X**.

Se concatenan después **120 máscaras de ausencia**, dando 240 entradas numéricas internas. No hay selección de features.

### Ausencias: no confundir frecuencia de muestreo con pérdida de todos los datos

En las tres particiones hay **cero celdas nulas de features agregadas**: todos los canales tienen alguna observación en cada ventana. Eso **no significa 100% de muestras sensoriales completas**. Todas las ventanas tienen al menos un canal con fracción observada menor que 1.

| Promedio de fracción observada por canal/familia | Entrenamiento | Validación | Prueba |
|---|---:|---:|---:|
| Frecuencia cardiaca | 0.091269 | 0.091386 | 0.091409 |
| Mano, canales IMU/temperatura | 0.995651 | 0.990583 | 0.994639 |
| Pecho, canales IMU/temperatura | 0.998553 | 0.999257 | 0.998710 |
| Tobillo, canales IMU/temperatura | 0.995758 | 0.995095 | 0.995698 |

La FC llega aproximadamente a 9 Hz frente a la rejilla IMU de 100 Hz; su fracción cercana a 0.09 es esperable y no se interpreta como 91% de pérdida fisiológica. Media y SD agregadas usan solo valores observados, sin interpolar.

El contrato admite `null` solo para media/SD de un canal cuya fracción observada es 0. Si aparece una feature ausente, se usa **mediana ajustada únicamente con entrenamiento** y su máscara explícita. Si una columna fuera enteramente ausente en entrenamiento, permanece no disponible: valor interno 0 y máscara 1, aunque después haya observaciones. Una ventana sin ningún canal observado se rechaza.

En esta ejecución real la imputación estaba preparada para ausencias, **pero no se necesitó rellenar ninguna de las 120 features agregadas**. No se inventan muestras crudas ni señales fisiológicas.

## 3. Entrenamiento y separación de la prueba

1. Se ajustan medianas en entrenamiento. Tras imputación, se ajustan media y SD poblacional de entrenamiento para escalar cada feature; una columna constante usa divisor 1. Se anexan las máscaras, sin identificadores.
2. Se aprende por clase la media, varianza poblacional y prior de frecuencia de entrenamiento de las 240 entradas. El score usa suma de log-verosimilitudes gaussianas, no productos numéricamente inestables.
3. La única búsqueda, fijada antes de evaluar prueba, compara `var_smoothing` **`1e-9` y `0.001`**. La varianza recibe `var_smoothing * max(1, mayor varianza global transformada de entrenamiento)`. Se selecciona por macro-F1 de validación; un empate exacto favorece el primer candidato.
4. Se conserva el modelo entrenado solo con los cinco participantes de entrenamiento: **no se reajusta con validación ni prueba**. Se escriben `model.json` y después `frozen.json`, con configuración, hashes, versiones y métricas de validación. El comando `train` no calcula predicciones de prueba.
5. Otro comando carga el modelo congelado, vuelve a verificar el dataset y evalúa las 504 ventanas reservadas. No llama a ninguna función de ajuste. No se cambia configuración después de observar estos resultados.

| Suavizado candidato | Accuracy validación | Macro-F1 validación | Balanced accuracy validación |
|---|---:|---:|---:|
| `1e-9` | 0.579324 | 0.542465 | 0.606561 |
| **`0.001`, seleccionado** | **0.595701** | **0.560883** | **0.620699** |

Gaussian NB supone independencia condicional y distribuciones gaussianas por feature/clase. Las medias/SD de acelerómetros correlacionados violan parte de esas hipótesis; no se oculta esta debilidad. Los scores no se publican como probabilidades calibradas.

## 4. Evaluación real reservada

El comparador **most-frequent** aprende solo la clase más frecuente en entrenamiento: `17`, ironing. No calcula la clase mayoritaria de prueba. En un empate de frecuencias se elegiría el menor ID.

| Modelo congelado | Accuracy | Macro-F1 | Balanced accuracy |
|---|---:|---:|---:|
| Gaussian Naive Bayes | **0.581349** | **0.528234** | **0.584406** |
| Siempre clase más frecuente de entrenamiento | 0.093254 | 0.014217 | 0.083333 |

Son **293 aciertos de 504**, frente a 47 del comparador. Accuracy usa todas las ventanas; macro-F1 da igual peso a las 12 clases; balanced accuracy promedia recall entre clases presentes, que aquí son las 12. Para clases ausentes o nunca predichas, el JSON conserva soporte y flags de métrica definida; no se fabrican valores. No se presentan intervalos de confianza que traten ventanas correlacionadas como participantes independientes.

### Precision, recall, F1 y soporte de prueba

| ID / actividad fuente | Precision | Recall | F1 | Soporte |
|---|---:|---:|---:|---:|
| 1 lying | 0.637500 | 0.944444 | 0.761194 | 54 |
| 2 sitting | N/D: ninguna predicción | 0.000000 | 0.000000 | 46 |
| 3 standing | 0.605263 | 0.534884 | 0.567901 | 43 |
| 4 walking | 1.000000 | 0.340909 | 0.508475 | 44 |
| 5 running | 0.402062 | 0.928571 | 0.561151 | 42 |
| 6 cycling | 0.900000 | 0.765957 | 0.827586 | 47 |
| 7 Nordic walking | 1.000000 | 0.050000 | 0.095238 | 40 |
| 12 ascending stairs | 0.509434 | 0.870968 | 0.642857 | 31 |
| 13 descending stairs | 0.705882 | 0.857143 | 0.774194 | 28 |
| 16 vacuum cleaning | 0.424242 | 0.933333 | 0.583333 | 45 |
| 17 ironing | 0.676471 | 0.489362 | 0.567901 | 47 |
| 24 rope jumping | 0.916667 | 0.297297 | 0.448980 | 37 |

Para sitting, la implementación guarda precision=0 por convención de agregación, junto con `precision_defined:false`; no se interpreta como una precisión estimada sobre predicciones inexistentes.

### Matriz de confusión, conteos agregados

Filas: actividad real. Columnas: actividad predicha. El orden numérico corresponde a los IDs anteriores, no a una nueva escala de intensidad.

| Real \ Predicha | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 12 | 13 | 16 | 17 | 24 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 51 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 |
| 2 | 26 | 0 | 12 | 0 | 0 | 0 | 0 | 1 | 1 | 6 | 0 | 0 |
| 3 | 3 | 0 | 23 | 0 | 0 | 0 | 0 | 0 | 0 | 11 | 5 | 1 |
| 4 | 0 | 0 | 0 | 15 | 15 | 0 | 0 | 11 | 1 | 1 | 1 | 0 |
| 5 | 0 | 0 | 0 | 0 | 39 | 0 | 0 | 1 | 1 | 0 | 1 | 0 |
| 6 | 0 | 0 | 1 | 0 | 0 | 36 | 0 | 0 | 0 | 10 | 0 | 0 |
| 7 | 0 | 0 | 1 | 0 | 19 | 1 | 2 | 11 | 4 | 2 | 0 | 0 |
| 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 27 | 1 | 0 | 3 | 0 |
| 13 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 24 | 2 | 0 | 0 |
| 16 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 42 | 1 | 0 |
| 17 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 21 | 23 | 0 |
| 24 | 0 | 0 | 0 | 0 | 24 | 1 | 0 | 0 | 0 | 1 | 0 | 11 |

**Fallos materiales:** no reconoce ninguna de las 46 ventanas sitting; solo reconoce 2 de 40 Nordic walking y 11 de 37 rope jumping. Precision=1 para walking/Nordic walking no implica buen detector: sus recalls son bajos y Nordic walking solo tiene dos predicciones. La accuracy global no basta para decidir uso real.

## 5. Artefactos, hashes y comandos ejecutados

Todos los artefactos generados quedan en la carpeta ignorada:

```text
.research-data\models\pamap2-gnb-v1\model.json
.research-data\models\pamap2-gnb-v1\frozen.json
.research-data\models\pamap2-gnb-v1\evaluation.json
.research-data\models\pamap2-gnb-v1\test-confusion.csv
.research-data\models\pamap2-gnb-v1\example-input.json
.research-data\models\pamap2-gnb-v1\example-prediction.json
.research-data\models\pamap2-gnb-replay\model.json
```

`model.json` tiene **188,627 bytes** y SHA-256:

```text
e154b04b8ae95024cc7da923472fe27b50ef281efdb11a70bda19f96c4314853
```

Huellas SHA-256 de los inputs preparados:

```text
summary.json: 330d4d413a29c8324aedca57836ab5b3c12fd1e669216cd001810cf73fbd1d2b
dictionary.json: 228912a5f05e99b4f02d2adf42111de127a4d2d8e51ce3f2ffa24bf2f12caecf
subject-disjoint/records.jsonl: dec420a7e4fb53c2689f94215a4fd635d449817ce85902acce7163780b8750e6
training.py: ed661f4fe10cd95b2923005831e62447710455842224f6cae7bcef659119b4f0
```

`frozen.json` también conserva hashes del código de adquisición, preparación y verificación, feature order, mapa de etiquetas, cobertura, versión de Python, regla de selección, ambos candidatos y prueba de integridad. `evaluation.json` referencia los hashes del artefacto y manifiesto congelados.

Desde la raíz del repo, **sin instalar dependencias**:

```powershell
python -m research_data verify .research-data\prepared\pamap2-protocol-v1
python -m research_data.training train
python -m research_data.training evaluate
python -m research_data.training sample-input --output .research-data\models\pamap2-gnb-v1\example-input.json
python -m research_data.training infer --input .research-data\models\pamap2-gnb-v1\example-input.json --output .research-data\models\pamap2-gnb-v1\example-prediction.json
```

Estos comandos **ya se ejecutaron con éxito**. El directorio por defecto ya existe: `train` rechaza sobrescribirlo. Para otra ejecución, usar `--output .research-data\models\otro-nombre`; `evaluate` e `infer` admiten `--model` para elegirla. Los ejemplos/predicciones tampoco se sobrescriben: usar otro nombre local.

Se ejecutó además una reproducción de la **misma receta congelada**, sin cambios ni búsqueda nueva basada en test:

```powershell
python -m research_data.training train --output .research-data\models\pamap2-gnb-replay
```

Su `model.json` fue **idéntico byte a byte** al original. Se verificó la carga posterior del artefacto y una inferencia real; su resultado individual no se publica aquí.

### Contrato de inferencia

El JSON local debe tener exactamente `contract_version: 1` y `features`, con las 120 claves crudas completas. No requiere que el orden de claves JSON sea el de la matriz: el código aplica el orden guardado. Las unidades y el cálculo de las ventanas deben ser los mismos que en entrenamiento.

Se rechazan claves ausentes o adicionales, etiquetas/metadata infiltradas, strings numéricos, booleanos, infinitos/NaN, SD negativa, fracciones fuera de [0,1], canales con media/SD incompatibles con su cobertura, ventanas totalmente ausentes y operaciones fuera del rango aritmético finito. Los `null` válidos se tratan mediante el transform aprendido; no se rellenan claves omitidas.

El modelo es **JSON de parámetros, no pickle/joblib**, y no ejecuta código al cargarlo. Solo se carga desde almacenamiento local ignorado con contrato y hash del manifiesto verificados. Los hashes detectan cambios, **no son firmas ni prueban autenticidad frente a un atacante**: conservar el propio modelo/manifiesto y no reemplazarlos por archivos externos. No cargar nunca pickle/joblib de terceros.

## 6. Validación y estado de publicación

Ejecutado correctamente:

```powershell
python -m unittest discover -s tests -p test_training.py -v
python -m unittest discover -s tests -p "test_[de]*.py" -q
python -m compileall -q research_data
```

**8 pruebas nuevas y 33 regresiones de dominio/evidencia pasaron.** Cubren parámetros gaussianos y métricas contra ejemplos analíticos, features sin metadata, separación de sujetos, medianas/escalado ajustados solo en train, columnas constantes/ausentes, congelación anterior a test, evaluación sin ajuste, artefactos reproducibles, round-trip y errores de inferencia/procedencia. Las fixtures son sintéticas y no se presentan como validación poblacional.

La preparación real de 3,833 ventanas se verificó otra vez; entrenamiento, evaluación y carga/inferencia posteriores terminaron correctamente. Una primera invocación por nombres de módulos no encontró el import compartido de los tests existentes; se corrigió el comando a discovery y las 33 pruebas pasaron, sin cambiar esos tests.

No se reintentaron las operaciones previamente denegadas: lectura del Git config, renombrado temporal de aquella fixture, HTTP local o npm. **No se afirma que toda la suite o el navegador/build hayan pasado ahora.** No hay cambios en UI ni en las reglas científicas del demo.

Al momento de esta entrega, el código y este documento quedaron persistidos, **sin commit nuevo**, por el bloqueo conocido de lectura de la configuración global del Git incluido con la aplicación. En esta entrega no se hizo push, merge ni PR. Se omite la ruta personal del equipo para compartir este informe. No se publica el artefacto ni ningún registro individual.

## 7. Interpretación y siguiente evaluación

Este resultado demuestra entrenamiento real, inferencia reproducible y separación técnica de sujetos; **no demuestra generalización poblacional**. Solo hay nueve participantes y dos reservados para prueba, con aportes desiguales y ventanas correlacionadas. No comparar estos porcentajes con artículos que usen otro preprocesado, clases, ventanas o split aleatorio por muestra.

Las limitaciones de Gaussian NB, correlaciones entre features y diferencias de temperatura/orientación/dispositivo entre sujetos pueden afectar el rendimiento; no se atribuye causalmente un error a una feature sin estudio de ablación. No se entrenaron otros modelos ni se usó el resultado de prueba para elegir cambios.

Una iteración posterior podría comparar otro baseline y validación agrupada/leave-one-subject-out bajo un protocolo nuevo predefinido; este test ya fue observado y no debe reutilizarse repetidamente como criterio de desarrollo. Conviene estudiar errores por actividad y robustez ante sensores ausentes, sin confundir muchas ventanas con muchos participantes independientes.

Para **readiness de AthleteOS** siguen faltando otro target verificable, datos longitudinales apropiados, población/consentimiento, protocolos comparables y validación externa. Este clasificador requiere sensores PAMAP2 crudos y no acepta automáticamente un resumen Garmin. `athleteos.domain.predict_demo` permanece sin modificaciones y continúa claramente identificado como heurística demo.
