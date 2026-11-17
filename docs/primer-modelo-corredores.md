# Primer modelo experimental con el dataset de corredores

**Ejecución real: 11 de noviembre de 2026, UTC** (artefacto congelado a las 01:34:46 UTC). Modelo **`runners-day-logistic-v1`**, ajustado, guardado, recargado y evaluado localmente; no es una simulación de entrenamiento. **El resultado es débil:** en personas retenidas, AP **0.017604** frente a **0.014223** del comparador, ROC-AUC **0.584473** y precisión positiva **1.85%** al umbral exploratorio elegido. No hay evidencia de utilidad clínica o preparación para producción.

## 1. Objetivo y alcance

Este experimento usa datos reales de *Injury Prediction in Competitive Runners With Machine Learning*, depositados en Dataverse bajo **CC0-1.0**. La tarea es clasificar retrospectivamente la **etiqueta binaria original `injury` del día de evento t**, usando exclusivamente las diez variables de cada uno de los siete días anteriores: **t-7 a t-1**. Cada fila es una ventana persona/día de evento; no es una persona independiente.

No es un diagnóstico, un cálculo validado de riesgo individual ni una demostración de prevención de lesiones. Tampoco predice readiness, fatiga, hipertrofia, recuperación o rendimiento. No se integra en la aplicación AthleteOS ni en Garmin. Los documentos científicos sustentan el contexto y las decisiones metodológicas: **no se convierten en ejemplos ni etiquetas de entrenamiento**.

Se revisaron el README oficial completo corregido en 2024, el esquema y los dos archivos locales, el diccionario y la preparación existentes, y el resumen bibliográfico indexado del artículo. El texto completo del artículo no estuvo disponible en esta revisión; no se atribuyen al modelo detalles metodológicos no comprobados allí.

## 2. Qué permite afirmar la fuente

El README v2 corrige expresamente el orden diario que se había descrito incorrectamente en la publicación inicial: **sin sufijo = t-7; `.1` = t-6; ...; `.6` = t-1**. `Date` es un día entero relativo al primer registro del dataset, no una fecha de calendario con zona horaria. El archivo semanal representa semanas previas, con el orden inverso: base = semana previa, `.2` = tercera semana previa.

Por ello se elige **solo la representación diaria** como benchmark principal. Los archivos diario y semanal corresponden a las mismas 74 personas y eventos solapados; no se concatenan como cohortes independientes ni se usa uno como validación externa del otro. El semanal no entrena este modelo.

La documentación accesible **no establece con suficiente precisión** la definición clínica/adjudicación del evento, la demora entre inicio y registro, el manejo de episodios repetidos, la censura, los días fuera de riesgo ni la política de retorno al entrenamiento. No se interpreta cada fila positiva como primera lesión incidente y no se construye un análisis de supervivencia. Los síntomas incipientes podrían influir en cargas/percepciones previas: la ordenación previa al evento no elimina este sesgo ni prueba utilidad prospectiva.

### Variables y exclusiones

| Variables originales, repetidas en siete días | Unidad/interpretación conservada |
|---|---|
| `nr. sessions` | Número de sesiones |
| `total km`, `km Z3-4`, `km Z5-T1-T2`, `km sprinting` | Kilómetros en las categorías originales |
| `strength training` | Indicador original de entrenamiento de fuerza |
| `hours alternative` | Horas de entrenamiento alternativo |
| `perceived exertion`, `perceived trainingSuccess`, `perceived recovery` | Escalas originales; no se equiparan al RPE 0-10 del demo |

Esfuerzo y éxito son valoraciones posteriores a una sesión **de un día anterior**, no del día t. Recuperación se declara antes de esa sesión anterior. Se conservan las 70 columnas en el orden del diccionario local y del manifiesto del modelo. No hay acelerometría, ECG ni otras señales crudas de sensores en estos predictores.

Se excluyen de X: `injury`, `Athlete ID`, `Date`, identificador de fila, asignación de split y metadatos temporales. Los identificadores enmascarados se usan únicamente para verificar agrupaciones. No se generan cocientes derivados de etiquetas, normalización sobre personas sanas seleccionadas con el resultado, ni variables posteriores al evento. No se reproduce el procedimiento de normalización dependiente de etiqueta observado en material de replicación.

## 3. Datos, independencia y faltantes

El archivo diario contiene **42,766 ventanas, 74 personas, 583 etiquetas positivas y 42,183 negativas**: prevalencia global **1.3632%**. No se muestrea ni se reequilibran las clases. Las ventanas de días adyacentes se solapan y se correlacionan; los miles de registros no equivalen a miles de participantes independientes.

### Protocolo principal: participantes separados

Se conserva la asignación determinista ya preparada: ordenación hash con semilla de partición `athleteos-research-v1`, sin barajar ni buscar una partición con mejores resultados.

| Partición | Personas | Ventanas | Positivas | Negativas | Celdas faltantes de las 70 variables |
|---|---:|---:|---:|---:|---:|
| Entrenamiento | 44 | 23,963 | 300 | 23,663 | 134,505 (8.02%) |
| Validación | 15 | 8,257 | 133 | 8,124 | 54,705 (9.46%) |
| Test retenido | 15 | 10,546 | 150 | 10,396 | 51,837 (7.02%) |

No se comparte ninguna persona entre particiones. La verificación comprueba la asignación heredada y la integridad/alineación de archivos antes del ajuste. El test representa personas diferentes dentro de este dataset, no una cohorte externa ni validación clínica.

### Protocolo secundario: tiempo con purga

Se conserva también el benchmark temporal preparado, pero se ajusta **otro modelo independiente**. Sus resultados no se mezclan ni se usan para seleccionar el modelo principal. Cortes relativos 1,608 y 2,131; purga de siete días en cada frontera; **185 ventanas excluidas**, no asignadas silenciosamente a otra partición.

| Partición | Personas presentes | Días de evento relativos | Ventanas | Positivas | Negativas | Celdas faltantes |
|---|---:|---|---:|---:|---:|---:|
| Entrenamiento | 64 | 0-1,608 | 27,339 | 327 | 27,012 | 164,703 (8.61%) |
| Validación | 36 | 1,616-2,131 | 7,646 | 129 | 7,517 | 38,688 (7.23%) |
| Test retenido | 32 | 2,139-2,673 | 7,596 | 122 | 7,474 | 36,714 (6.90%) |

Aquí sí reaparecen personas entre periodos; por tanto, se interpreta como tiempo posterior de una cohorte conocida. La purga evita compartir días subyacentes de ventanas entre bloques, no elimina dependencia dentro de cada bloque ni convierte este protocolo en validación por personas nuevas. Las dos clases están presentes en las seis particiones.

### Tratamiento de faltantes

Solo las **21 columnas subjetivas** presentan faltantes: el centinela de descanso `-0.01` se convirtió previamente en `null`, no en recuperación/esfuerzo cero. No hay columnas completamente vacías en entrenamiento. Las 49 columnas objetivas están observadas; no se simulan mediciones de sensores.

En cada protocolo se aprende **solo con entrenamiento** la mediana por columna; se rellenan los `null`, se calculan media y desviación estándar poblacional de ese entrenamiento imputado y se estandariza. Una columna constante usa divisor 1; una hipotética columna sin observaciones de entrenamiento se fuerza a cero y se marca ausente, sin aprender de validación/test. Se agregan **70 indicadores de ausencia**, obteniendo 140 entradas. Esta elección preserva la señal de descanso/falta de valoración, pero también puede aprender hábitos de registro: es una limitación, no una prueba fisiológica.

## 4. Receta fijada antes del test

Se usa **regresión logística L2**, implementada de forma acotada con la biblioteca estándar de Python. `scikit-learn` no está disponible y la instalación anterior desde la fuente oficial falló por TLS; no se repitió ni se desactivó la verificación. No hay cambios en dependencias del demo.

La función objetivo es pérdida logística binaria media sin ponderar más `lambda * suma(coeficientes^2) / 2`; el intercepto no se penaliza. Se inicializan coeficientes en cero e intercepto con el logit de la prevalencia de entrenamiento. Se aplican **160 iteraciones full-batch de gradiente acelerado de Nesterov**, con paso determinado por una cota superior conservadora de Lipschitz basada en la traza. Se conserva el menor objetivo de entrenamiento comprobado cada 20 iteraciones y al final. El presupuesto fijo **no demuestra convergencia**; el manifiesto registra objetivos inicial/final y paso.

No hay selección de variables, balanceo, sobremuestreo, recorte, búsqueda de redes neuronales ni aleatoriedad en el optimizador. Se comparan únicamente **L2 = 0.01 y 0.1** por average precision de validación; un empate exacto conserva el primer candidato. No se reentrena con train+validation.

Para cada modelo se fija, usando solo validación, el umbral que maximiza F1 entre **0.01, 0.02, 0.05, 0.1, 0.2 y 0.5**; los empates prefieren el umbral mayor. Es un intercambio exploratorio precisión/recall, **no un punto operativo clínico**. También se reporta el umbral convencional 0.5 aunque no detecte positivos. Se congela JSON, transformaciones, variables y umbral antes de ejecutar el comando separado de test.

El comparador de clase mayoritaria produce siempre negativo con umbral 0.5; su puntuación constante es la prevalencia de **entrenamiento**, no una prevalencia aprendida del test. Su average precision en test coincide matemáticamente con la prevalencia del test y su ROC-AUC es 0.5.

### Convenciones de evaluación

Se informa **average precision (AP)** no interpolada: suma de cada incremento de recall por la precisión del grupo de puntuación correspondiente, agrupando empates. No se presenta como área trapezoidal de la curva precision-recall. ROC-AUC usa trapecios con empates agrupados. Se muestran precisión, recall, F1, matriz `[[TN, FP], [FN, TP]]`, prevalencia y número de alertas. Precisión sin ninguna predicción positiva es **indefinida (`null`)**, no una precisión perfecta ni un valor oculto. La exactitud se incluye solo como referencia engañosa ante el fuerte desequilibrio.

Las puntuaciones logísticas están entre 0 y 1 pero **no se ha evaluado su calibración**: no se denominan probabilidades clínicas. No se inventan intervalos de confianza a nivel fila; cualquier evaluación de incertidumbre futura deberá respetar agrupación por persona y dependencia temporal.

## 5. Reproducción, contrato y privacidad

Ejecutar desde la raíz con **Python 3.11+**, sin instalar paquetes:

```powershell
python -m research_data verify .research-data\prepared\runners-day-v1
python -m research_data.runners_training train
python -m research_data.runners_training evaluate
python -m research_data.runners_training sample-input --output .research-data\models\runners-day-logistic-v1\example-input.json
python -m research_data.runners_training infer --input .research-data\models\runners-day-logistic-v1\example-input.json --output .research-data\models\runners-day-logistic-v1\example-prediction.json
```

La carpeta ignorada `.research-data\models\runners-day-logistic-v1\` contiene `model.json`, `frozen.json` y, tras evaluar, `evaluation.json`. El manifiesto registra hashes SHA-1/SHA-256 de fuentes, tablas preparadas y código, versión de Python, orden exacto de variables, etiquetas, parámetros, cobertura, validación y política de test. El modelo incluye dos ajustes independientes: `subject-disjoint` y `temporal-purged`. La inferencia pública de esta herramienta usa **solo el principal por participantes separados**, sin elegir el protocolo por conveniencia.

No se sobrescriben ejecuciones existentes. Para repetir el ajuste usar, por ejemplo, `train --output .research-data\models\runners-day-logistic-replay`, y el mismo directorio en `evaluate --model ...` e `infer --model ...`; usar también nuevos nombres para entradas/predicciones. La repetición debe conservar los mismos datos, variables y configuración, no convertirse en otra búsqueda sobre el test ya observado.

El contrato de inferencia exige exactamente `{"contract_version": 1, "features": {...}}`, con las 70 claves originales del diccionario diario y valores numéricos finitos no negativos; únicamente las columnas subjetivas permiten `null`. Rechaza booleanos, infinitos, columnas extra/faltantes y datos arbitrarios del demo. Los centinelas crudos negativos deben haber pasado por la preparación oficial. El comando `sample-input` crea un ejemplo real **solo en almacenamiento local ignorado**; no imprime sus variables ni las añade al informe.

Se carga JSON local comprobado contra su manifiesto, **no pickle/joblib ejecutable**. Solo se deben abrir artefactos propios y confiables: un hash no es una firma contra la sustitución conjunta de modelo y manifiesto. Nunca cargar modelos pickle/joblib no confiables en herramientas futuras. Ni el modelo, ni registros, identificadores, entradas de ejemplo o predicciones individuales son adjuntos ni archivos para Git. Este informe y el gráfico asociado contienen únicamente agregados.

### Fuentes y trazabilidad pública

| Recurso | Referencia y alcance inspeccionado |
|---|---|
| Dataset oficial | [DOI 10.34894/UWU9PV](https://doi.org/10.34894/UWU9PV), versión 2.0, licencia CC0-1.0; fuente de datos, no validación del producto |
| Metadatos de Dataverse | https://dataverse.nl/api/datasets/:persistentId/?persistentId=doi:10.34894/UWU9PV |
| README corregido v2 | https://dataverse.nl/api/access/datafile/422690 ; leído completo, incluidas correcciones del orden diario |
| Archivo diario | https://dataverse.nl/api/access/datafile/47972 ; esquema y preparación locales verificados |
| Archivo semanal | https://dataverse.nl/api/access/datafile/47971 ; inspeccionado como representación solapada, excluido del ajuste |
| Artículo original | Lövdal, Azzopardi y den Hartigh (2021), *Injury Prediction in Competitive Runners With Machine Learning*, https://doi.org/10.1123/ijspp.2020-0518 ; texto completo no revisado |
| Resumen bibliográfico consultado | https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3A33931574%20AND%20SRC%3AMED&format=json&resultType=core ; PMID 33931574 |
| Licencia | https://creativecommons.org/publicdomain/zero/1.0/ |

El resumen del artículo describe modelos XGBoost con ensambles y ROC-AUC diario/semanal de 0.724/0.678. **No son resultados nuestros ni un comparador reproducido**: algoritmos, particiones y evaluación no equivalen a los de esta entrega. Para contexto previo y límites de otras fuentes ver [datos reales y preparación](datos-reales-y-preparacion.md); para el modelo de actividad independiente ver [PAMAP2](primer-modelo-pamap2.md). Ninguno reemplaza el predictor heurístico de readiness del demo.

## 6. Resultados reales congelados

### Selección usando únicamente validación

| Protocolo | AP con L2 0.01 | AP con L2 0.1 | L2 elegida | Umbral elegido | F1 de validación |
|---|---:|---:|---:|---:|---:|
| Participantes separados | 0.028811 | 0.027712 | 0.01 | 0.02 | 0.067316 |
| Temporal con purga | 0.028991 | 0.024795 | 0.01 | 0.02 | 0.054333 |

Con L2 elegida, el objetivo de entrenamiento bajó de **0.067281198 a 0.064393017** en participantes separados y de **0.064829522 a 0.062898174** en temporal. Esto confirma optimización efectiva, no que se alcanzara el óptimo ni que el resultado generalice. El test no intervino en estas decisiones.

### Test principal: personas no vistas

**10,546 ventanas de 15 personas, 150 positivas y 10,396 negativas; prevalencia 1.4223%.**

| Método | Umbral | AP | ROC-AUC | Precisión (%) | Recall (%) | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Logística, umbral de validación | 0.02 | 0.017604 | 0.584473 | 1.8459 | 34.6667 | 0.035052 |
| Mismo modelo, umbral convencional | 0.5 | 0.017604 | 0.584473 | 3.0303 | 0.6667 | 0.010929 |
| Comparador, siempre negativo | 0.5 | 0.014223 | 0.500000 | Indefinida | 0.0000 | 0.000000 |

| Método | TN | FP | FN | TP | Alertas totales | Exactitud (%) |
|---|---:|---:|---:|---:|---:|---:|
| Logística, 0.02 | 7,631 | 2,765 | 98 | 52 | 2,817 | 72.8523 |
| Logística, 0.5 | 10,364 | 32 | 149 | 1 | 33 | 98.2837 |
| Comparador negativo | 10,396 | 0 | 150 | 0 | 0 | 98.5777 |

**Fallo material:** al umbral 0.02, solo **52 de 2,817 alertas** corresponden a etiqueta positiva; hay **2,765 falsos positivos** y se omiten **98 de 150 positivos**. Al umbral 0.5 se identifica únicamente **1 de 150**. El comparador logra 98.58% de exactitud sin identificar un solo positivo: reportar solo accuracy escondería el fracaso de detección.

La AP de test cae frente a validación (0.028811 a 0.017604) y permanece cerca de la prevalencia. Una mejora descriptiva pequeña sobre el comparador no demuestra significación, calibración, transportabilidad ni utilidad para decidir entrenamiento.

### Test secundario: periodo posterior de una cohorte conocida

**7,596 ventanas, 32 personas presentes, 122 positivas y 7,474 negativas; prevalencia 1.6061%.** No son 32 personas nuevas ni un conjunto externo.

| Método | Umbral | AP | ROC-AUC | Precisión (%) | Recall (%) | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Logística, umbral de validación | 0.02 | 0.021839 | 0.587050 | 2.3486 | 36.8852 | 0.044161 |
| Mismo modelo, umbral convencional | 0.5 | 0.021839 | 0.587050 | Indefinida | 0.0000 | 0.000000 |
| Comparador, siempre negativo | 0.5 | 0.016061 | 0.500000 | Indefinida | 0.0000 | 0.000000 |

| Método | TN | FP | FN | TP | Alertas totales | Exactitud (%) |
|---|---:|---:|---:|---:|---:|---:|
| Logística, 0.02 | 5,603 | 1,871 | 77 | 45 | 1,916 | 74.3549 |
| Logística, 0.5 | 7,474 | 0 | 122 | 0 | 0 | 98.3939 |
| Comparador negativo | 7,474 | 0 | 122 | 0 | 0 | 98.3939 |

Aquí el umbral 0.5 **no produce ninguna alerta**. La precisión es indefinida, no 0% ni 100%. Reducirlo a 0.02 recupera 45 etiquetas positivas, pero produce 1,871 falsos positivos y sigue omitiendo 77. No se modifica el modelo a partir de este resultado.

Gráfico compartible exclusivamente agregado: [resultados-corredores.svg](resultados-corredores.svg). Incluye las dos matrices al umbral congelado y AP frente al comparador; **no** es una captura del producto ni contiene observaciones individuales.

## 7. Artefactos, verificación y estado de entrega

| Elemento | Valor verificado |
|---|---|
| Versión | `runners-day-logistic-v1` |
| Entorno real | Python **3.11.9**, biblioteca estándar, sin NumPy/scikit-learn |
| Artefacto | `.research-data\models\runners-day-logistic-v1\model.json`, **32,017 bytes** |
| SHA-256 del modelo | `1567e208a523fc50369fc32b10a608c62e3a8b2fb39cead3abb53f3e9c005ade` |
| SHA-256 del manifiesto congelado | `31a30052a63949faf6f70ea71f9ca3c894a7af7ca20157c3849591cede69da34` |
| SHA-256 del CSV diario fuente | `9c06ecefae9caa4ca831c08c7ebe4d25b0b01e8aa285df526a4e6791c673b6e8` |
| SHA-256 del README fuente | `60cb848f9cb0c18c374af03627ff698b3e31dbc49e614afe21f0c7931e1e04f0` |

Se ejecutaron realmente los comandos de entrenamiento, evaluación separada, generación local del ejemplo e inferencia del apartado 5. Se comprobaron la recarga y los hashes del artefacto/código; una segunda evaluación produjo el mismo resultado sin modificar los archivos congelados y la inferencia recargada coincidió exactamente con la guardada. No se publican las variables ni la predicción individual del ejemplo. Las ocho celdas y las cuatro barras del SVG se contrastaron programáticamente con la evaluación; su renderizado completo se revisó en el navegador, sin texto fuera de los límites.

**Pruebas enfocadas ejecutadas: siete nuevas, todas correctas.** Cubren solución analítica de intercepto, dirección de coeficientes, gradiente numérico cerca de un óptimo sintético, pérdida reducida, sigmoid estable, AP/ROC con empates, métricas indefinidas, contrato estricto, transformaciones aprendidas solo con entrenamiento, columnas constantes/vacías, exclusiones de metadatos, asignación por participante y purga, cambio de huellas tras congelar, ajuste/guardado/recarga/inferencia y reproducción byte a byte con fixtures sintéticos. La evaluación sintética falla si intenta llamar al ajuste. Los fixtures se eliminan al terminar y no dependen de filas reales.

También pasaron **41 regresiones existentes**: 8 de entrenamiento PAMAP2, 15 de dominio del demo y 18 de evidencia/trazabilidad. Se compiló `research_data`. No se afirma que se haya repetido o aprobado toda la suite HTTP/frontend: persisten antecedentes de restricciones en ciertas operaciones del entorno. El servidor de usuario previamente iniciado no se reinició, no se resembraron datos y no se modificó el frontend/backend del demo.

Código, informe y resultados agregados quedan persistidos localmente. **No hay nuevo commit ni push**: no se reintentó el acceso Git previamente denegado ni se cambió la política del sandbox. Los datasets y artefactos permanecen ignorados; los documentos históricos de overview/PAMAP2 se conservan como entregas fechadas, sin reescribirlos con resultados nuevos.

## 8. Qué falta antes de cualquier uso práctico

Esta entrega completa un primer benchmark reproducible, **no un predictor listo para usar**. Un siguiente experimento necesitaría resolver primero definición y adjudicación del evento, disponibilidad real antes del registro, episodios/censura/retorno al entrenamiento y representatividad; sin ello no se puede prometer un horizonte clínico o interpretar el score como riesgo.

Después correspondería diseñar otra evaluación preespecificada, con datos externos o prospectivos realmente disponibles, tratamiento de dependencia por persona/episodio, comprobación de calibración y análisis de costos de falsos positivos/negativos. Cualquier búsqueda adicional debe usar entrenamiento/validación y un nuevo test independiente: el test aquí ya fue observado. Mejoras en features/optimización solo tendrían sentido con hipótesis comprobables y seguimiento de esa separación, no para elevar retrospectivamente este número.

Para AthleteOS readiness se requieren un objetivo diferente, etiquetas apropiadas, fuentes consentidas y un contrato compatible con las observaciones del producto. **Ni la etiqueta de evento de corredores ni la actividad PAMAP2 son readiness.** Hasta cumplir ese trabajo, el demo conserva `demo-heuristic-v2`; no se prescribe descanso, intensidad u otra intervención a partir de este clasificador.
