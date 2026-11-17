# Datos reales: adquisición y preparación para investigación

**Fecha de revisión y ejecución: 5 de noviembre de 2026 (hora local; descargas registradas también en UTC).** Se obtuvieron datos reales de fuentes oficiales y se prepararon tablas de entrenamiento/evaluación locales. **No se entrenó un modelo, no se cambió el predictor del demo y no se conectó Garmin.**

Este documento contiene solo metadatos agregados, esquemas, hashes y procedimientos. No incluye filas individuales, identidades, sensores ni resultados de salud de participantes.

**Entrega posterior:** ya se entrenó y evaluó un primer clasificador de actividades PAMAP2. Los resultados y limitaciones están en [`primer-modelo-pamap2.md`](primer-modelo-pamap2.md). Las afirmaciones de «no se entrenó» de este informe describen la entrega anterior de adquisición, no el estado del entrenamiento posterior.

## 1. Resultado verificable y estado por fuente

| Fuente | Acceso/licencia comprobados | Obtenido y preparado en esta entrega | Uso apropiado / límite |
|---|---|---|---|
| Competitive Runners, DataverseNL | Versión 2.0; archivos `restricted:false`, sin solicitud de acceso; CC0-1.0; sin condiciones adicionales en la respuesta pública consultada. | README v2 y **ambos CSV completos**, checksums SHA-1 publicados verificados. Diario: **42,766 filas / 74 sujetos / 583 etiquetas positivas**. Semanal: **42,798 / 74 / 575**. Dos benchmarks separados por representación. | Etiqueta binaria de evento de lesión de esa cohorte, para investigación exploratoria. No equivale a readiness, prevención causal de lesiones ni un producto médico validado. |
| PAMAP2, UCI | CC BY 4.0; tamaño anunciado 656.3 MB. El usuario autorizó expresamente la transferencia completa. | ZIP oficial completo de **688,226,940 bytes**, inspeccionado y leído; archivo interno de **688,167,640 bytes**. Se procesaron los **9 archivos Protocol**, **2,872,533 muestras**, para **3,833 ventanas / 12 actividades**. | Clasificación de actividad con sensores. Optional está en el archivo descargado, pero se excluye deliberadamente de este benchmark. No son etiquetas longitudinales de fatiga, HRV, readiness o Garmin. |
| FitRec / Endomondo | Sitio oficial: **solo uso académico; no comercial; no redistribución**. | Landing page, inventario/tamaños HEAD y código metodológico leídos. **No se descargaron sus registros y no se preparó una tabla FitRec.** Pendiente confirmar finalidad académica y autorizar una transferencia grande. | Secuencias de actividad/FC y tareas de FC/velocidad, no recuperación clínica. El código de GitHub es una referencia del mismo dataset, no otra fuente de atletas. |
| Garmin Health API / Connect Developer Program | El enlace Health API proporcionado devolvió **404**. La página oficial vigente de overview fue accesible. Describe Personal y Business Starter/Enterprise. | **Sin datos descargados, tokens, registro o solicitud de programa.** | API autenticada, no dataset público. Personal requiere credenciales propias; Business requiere solicitud al programa y autorización del usuario de los datos. No se afirma que cada campo sea disponible en cada nivel. |
| PMC8884877 | Artículo y secciones de métodos/resultados consultados; título contrastado en Europe PMC. | Evidencia revisada; **no se presenta como dataset individual** ni se extraen etiquetas ficticias. | Revisión de volumen e hipertrofia, no tabla longitudinal individual para entrenar AthleteOS. |

El manifiesto versionable es [`research_data/sources.json`](../research_data/sources.json). Los registros de descarga reales y los diccionarios completos de cada ejecución están **solo en `.research-data`**, fuera de Git.

## 2. Acceso, referencias y comprobaciones de origen

### Corredores

- Dataset: https://doi.org/10.34894/UWU9PV
- Metadata oficial: https://dataverse.nl/api/datasets/:persistentId/?persistentId=doi:10.34894/UWU9PV
- README corregido v2: https://dataverse.nl/api/access/datafile/422690
- CSV diario: https://dataverse.nl/api/access/datafile/47972
- CSV semanal: https://dataverse.nl/api/access/datafile/47971
- Artículo: Lövdal, den Hartigh y Azzopardi (2021), *Injury Prediction in Competitive Runners With Machine Learning*, https://doi.org/10.1123/ijspp.2020-0518 ; abstract indexado: https://pubmed.ncbi.nlm.nih.gov/33931574/

Dataverse describe un equipo neerlandés de medio/largo fondo, registros de siete años, 74 corredores y entrenamiento comparable bajo el mismo entrenador. Los CSV tienen los IDs ya enmascarados por la fuente. Se conservan únicamente como claves internas de partición, no como features ni identidades. No se intenta identificar personas.

El editor del artículo devolvió 403; se utilizaron metadata/README oficiales, abstract indexado y lectura inerte del código de replicación. **No se afirma haber verificado íntegramente la definición clínica de lesión ni el texto completo**. `injury=1` se mantiene como etiqueta fuente, sin inventar localización, gravedad, días perdidos, diagnóstico o probabilidad clínica. Una entrada institucional consultada muestra 77 sujetos, en desacuerdo con los CSV y la metadata; las cifras de este documento proceden de los **archivos descargados, 74**, no de esa descripción.

| Archivo completo | Bytes | SHA-1 publicado, coincidente |
|---|---:|---|
| README.txt | 5,750 | `ce2cd69963ca27c9d18cceed58da9b63e7a035ce` |
| day_approach_maskedID_timeseries.csv | 13,547,450 | `c6edbd3aefb2f61e62971d629012fa2890e1ea6a` |
| week_approach_maskedID_timeseries.csv | 15,152,612 | `dd3eed3abb8014d6a69ffc6f6b569bcf0660805e` |

SHA-256 calculados localmente:

```text
README: 60cb848f9cb0c18c374af03627ff698b3e31dbc49e614afe21f0c7931e1e04f0
day:    9c06ecefae9caa4ca831c08c7ebe4d25b0b01e8aa285df526a4e6791c673b6e8
week:   261ba3a481f3428611cc175eac2b67749ee3d97980d81168af13bd9f932d5a31
```

### PAMAP2

Reiss, A. (2012), *PAMAP2 Physical Activity Monitoring [Dataset]*, UCI, https://doi.org/10.24432/C5NW2H .

- Landing page y licencia: https://archive.ics.uci.edu/dataset/231/pamap2+physical+activity+monitoring
- Archivo oficial: https://archive.ics.uci.edu/static/public/231/pamap2+physical+activity+monitoring.zip
- Licencia: https://creativecommons.org/licenses/by/4.0/

La página anuncia **18 actividades en total y 3,850,505 instancias** para la fuente completa, incluidas actividades opcionales. **No se atribuyen esas cifras al subconjunto Protocol preparado**. Este contiene 12 etiquetas activas y una categoría transitoria 0 que no se usa como clase de entrenamiento.

No se localizó un checksum independiente publicado en la landing page. Se registraron estos SHA-256 de la descarga real, que permiten reproducir y detectar cambios locales, pero **no se llaman checksums certificados por UCI**:

```text
ZIP UCI: 76b3580bd5a804121f507717cb498c66a312ef5c774f4a78ac470e6558add352
ZIP interior: 6c2282b5b52775cd0588d450d10a315260c94fa3228b9fe453f48c47fda106f4
```

Se comprueba formato ZIP y CRC al leer, límites de expansión/tamaño/número de miembros, rutas inseguras, duplicados, enlaces y cifrado. Solo se materializa el ZIP interno en una ruta fija; los archivos `.dat` se leen en streaming, sin extraer rutas arbitrarias del archivo. Los PDF de información personal de sujetos **no se convierten en features ni se publican**.

### FitRec y su código

- Dataset: https://cseweb.ucsd.edu/~jmcauley/datasets/fitrec.html
- Referencia: Ni, Muhlstein y McAuley (2019), *Modeling heart rate and activity data for personalized fitness recommendation*, WWW, https://cseweb.ucsd.edu/~jmcauley/pdfs/www19.pdf
- Código leído, sin ejecutarlo: https://github.com/nijianmo/fit-rec/tree/107f37d32e57f1a4ac9bae0a60cb9689751026ad

Inventario oficial verificado por HEAD, **sin descargar registros**:

| Archivo | Bytes |
|---|---:|
| `endomondoHR.json.gz` | 1,995,378,519 |
| `endomondoMeta.json.gz` | 1,088,266,461 |
| `endomondoHR_proper.json` | 4,929,126,138 |
| `processed_endomondoHR_proper.npy` | 8,011,208,302 |
| `processed_endomondoHR_proper_interpolate.npy` | 6,457,513,404 |

La fuente anuncia 253,020 workouts/1,104 usuarios originales; 167,373/956 filtrados; 102,343/887 interpolados a 10 s. **Son cifras publicadas, no cobertura local obtenida**. Algunas mediciones filtradas ya están normalizadas a z-scores; los campos `tar_*` y unidades deben verificarse antes de diseñar una tarea. No se reinterpretan valores normalizados como bpm/km/h.

El código de referencia usa orden temporal por usuario, un mínimo de 10 workouts y reserva los workouts más recientes para validación/test. También contiene `eval`, pickle/NPY de objetos y normalizaciones previas al split: **no se ejecuta ni copia ese flujo inseguro o con potencial fuga**. Una implementación futura deberá parsear formatos como datos, sin `eval` o deserialización de objetos, y ajustar sus transformaciones solo en train. Esta entrega no incluye un parser FitRec que no haya podido probarse con registros autorizados.

Para incorporarlo falta una decisión expresa sobre finalidad académica no comercial y tamaño/alcance de transferencia. No se ofrece una descarga automatizada que eluda esa decisión. Las URLs oficiales de los archivos figuran en el manifiesto para una adquisición posterior autorizada; no se usan mirrors no oficiales ni rangos truncados presentados como dataset representativo.

### Garmin y revisión de hipertrofia

Overview vigente comprobado: https://developer.garmin.com/gc-developer-program/overview/ . Personal describe acceso pull mediante clave/tokens propios. Business Starter describe solicitud, capacidad limitada y sin histórico; Enterprise describe opciones/histórico sujetos a condiciones. Son descripciones de acceso, **no aprobación concedida ni conexión implementada**. No se solicitaron credenciales ni se enviaron formularios.

PMC8884877 corresponde a **Baz-Valle et al. (2022), *A Systematic Review of The Effects of Different Resistance Training Volumes on Muscle Hypertrophy***, DOI https://doi.org/10.2478/hukin-2022-0017 , no a una tabla de participantes:

- https://pmc.ncbi.nlm.nih.gov/articles/PMC8884877/
- Registro de título/DOI: https://europepmc.org/article/MED/35291645

Siete estudios cualitativos/seis cuantitativos; participantes jóvenes entrenados, medidas directas de grosor/área muscular. El abstract compara 12–20 frente a >20 series: no diferencia significativa para cuádriceps/bíceps, resultado distinto para tríceps. No se convierte la recomendación de grupo en una etiqueta individual de crecimiento o una nueva dosis automática del demo. Europe PMC indica que no hay suplemento en ese registro; no se afirma haber obtenido datos individuales subyacentes.

## 3. Esquemas separados y diccionario de datos

**No se fuerza ninguna fuente dentro del CSV de una sesión por día del MVP**. Un flujo IMU a 100 Hz, múltiples workouts y eventos con ventanas retrospectivas tienen granularidades distintas. No se unen sujetos de fuentes diferentes, ni se fusionan día/semana como si fueran observaciones independientes.

### Corredores: un evento y sus antecedentes por fila

| Campo/familia | Semántica/unidad | Tratamiento |
|---|---|---|
| `Athlete ID` | Seudónimo enmascarado de la fuente | Solo índice local/agrupación; excluido de X. |
| `Date` | Día entero relativo al primer registro | Sin fecha de calendario ni zona horaria inventada; excluido de X. |
| `injury` | Etiqueta fuente binaria del evento, 0/1 | Solo y; no feature ni diagnóstico generado. |
| Diario: `nr. sessions`, kilómetros totales/zonas/sprints, `strength training`, `hours alternative` | Recuentos, km, indicador y horas de cross-training | 10 variables × 7 días = **70 features**. Fuerza sí/no no equivale a series, kg o hipertrofia. |
| Diario: `perceived exertion`, `perceived trainingSuccess`, `perceived recovery` | Valoraciones originales de cansancio posterior, éxito y recuperación previa | Se conservan sus escalas, **no se asumen equivalentes a RPE AthleteOS 0–10**. El sentinel documentado `-0.01` en descanso se convierte en `null`, no en una buena/mala recuperación. |
| Semanal: sesiones, descansos, km/zonas/máximos, sesiones intensas, horas alternativas y sesiones de fuerza | Agregados fuente | 22 variables × 3 semanas = **66 features**. Valoraciones medias/mínimas/máximas se conservan; no se reconstruyen muestras diarias inexistentes. |
| `rel total kms week 0_1`, `0_2`, `1_2` | Tres ratios adicionales de la fuente semanal | Excluidos de X: derivación exacta y manejo de ceros no quedan establecidos por el README revisado. El original descargado se conserva intacto. |

**Corrección esencial del README v2 (2024):** en diario, el nombre sin sufijo corresponde a **7 días antes** del evento; `.6` a **1 día antes**. En semanal, sin sufijo es la semana anterior; `.2`, la tercera semana anterior. La descripción original del artículo tenía mal el orden diario. El diccionario y la preparación conservan los nombres originales y documentan el significado corregido.

### PAMAP2: muestras a ventanas de actividad

Cada muestra tiene **54 columnas**: segundos del registro, `activityID`, FC en bpm y tres bloques IMU de 17 columnas (mano, pecho, tobillo). IMU a 100 Hz; FC aproximadamente a 9 Hz. `NaN` se conserva como ausencia, no cero.

Se utilizan **40 canales**: FC y, por IMU, temperatura °C, aceleración 3D ±16g y ±6g en m/s², giroscopio rad/s y magnetómetro µT. Se excluyen cuatro columnas de orientación por IMU, declaradas inválidas por la fuente. Por cada canal se calculan media, SD poblacional y fracción observada: **120 features**. La FC no se convierte en HRV ni en FC de reposo.

Ventanas de **500 muestras contiguas**, no solapadas, de una sola actividad/sujeto. El intervalo nominal cubre cinco segundos; la distancia entre primera/última muestra es 4.99 s. Un salto temporal, cambio de etiqueta o sujeto reinicia la ventana. No se interpola, no se rellena hacia atrás y no se mezcla una transición con otra actividad.

Se procesaron 2,872,533 muestras Protocol: 929,661 de etiqueta transitoria 0, 1,916,500 muestras en 3,833 ventanas, y 26,372 muestras activas descartadas por bordes/gaps/segmentos incompletos. Esta política y la exclusión Optional son un benchmark explícito, **no una muestra aleatoria representativa ni el total completo publicado**.

Clases preparadas:

| ID | Actividad | Ventanas |
|---:|---|---:|
| 1 | lying | 382 |
| 2 | sitting | 365 |
| 3 | standing | 377 |
| 4 | walking | 475 |
| 5 | running | 194 |
| 6 | cycling | 326 |
| 7 | Nordic walking | 373 |
| 12 | ascending stairs | 228 |
| 13 | descending stairs | 199 |
| 16 | vacuum cleaning | 347 |
| 17 | ironing | 472 |
| 24 | rope jumping | 95 |

Las clases opcionales 9/10/11/18/19/20 no se inventan en Protocol. El número de ventanas por sujeto es desigual, especialmente porque uno de los registros Protocol es mucho más corto; no se interpreta cada ventana como un sujeto independiente.

## 4. Particiones, fuga de información y transformación

### Benchmark principal: sujetos diferentes

Se ordenan seudónimos por SHA-256 de `athleteos-research-v1:<seudónimo>` y se asignan aproximadamente 60%/20%/20% **por sujeto**, no por fila. Es reproducible, independiente del orden del CSV y de las etiquetas; no se prueba una serie de semillas para escoger el test favorable.

| Fuente | Train: filas / sujetos / positivos | Validación | Test |
|---|---|---|---|
| Corredores diario | 23,963 / 44 / 300 | 8,257 / 15 / 133 | 10,546 / 15 / 150 |
| Corredores semanal | 23,955 / 44 / 295 | 8,326 / 15 / 132 | 10,517 / 15 / 148 |
| PAMAP2 Protocol | 2,352 ventanas / 5 sujetos | 977 / 2 | 504 / 2 |

Los solapamientos de sujetos train/validación/test son **cero** en los tres benchmarks principales. Todas las 12 clases PAMAP2 aparecen en las tres particiones de esta ejecución; eso no elimina el límite de solo nueve participantes.

### Benchmark adicional: tiempo futuro, cohorte conocida

Para corredores se genera también `temporal-purged`. Cortes relativos calculados sin consultar las etiquetas: días **1608 y 2131**. Purga posterior de **7 días** para diario o **21 días** para semanal. Así, las ventanas de entradas no comparten días entre bloques; no se hace un split aleatorio de eventos consecutivos.

| Representación | Train | Validación | Test | Filas purgadas |
|---|---:|---:|---:|---:|
| Diario | 27,339 (327 positivas) | 7,646 (129) | 7,596 (122) | 185 |
| Semanal | 27,400 (321 positivas) | 7,352 (125) | 7,423 (118) | 623 |

Este benchmark **permite los mismos sujetos en distintas épocas**: evalúa tiempo futuro en una cohorte conocida, no generalización a atletas nuevos. Los días relativos no se convierten en fechas exactas. PAMAP2 son sesiones de sensores, no historia deportiva longitudinal; aquí se usa retención por sujeto, no se finge un benchmark de readiness temporal.

### X, y, índices y escalas

Cada esquema contiene:

- `records.jsonl`: valores canónicos en unidades fuente, ausencias `null`, etiqueta e índice local, más partición. No publicar.
- `{train,validation,test}.features.csv`: **solo X**, z-scores más máscaras explícitas `__missing`.
- `{train,validation,test}.labels.csv`: `row_id,label`, alineados con X.
- `{train,validation,test}.index.csv`: row ID, seudónimo, tiempo relativo y split; **no alimentar como features**.
- `transforms.json`: conteo, media y SD poblacional calculados **solo en train**.
- `summary.json`: clases/cobertura, advertencias, hashes de outputs y verificación de particiones.

Los blancos de X siguen siendo ausencias: no se imputa con medias calculadas globalmente. Una columna constante en train utiliza escala 1; una totalmente ausente en train permanece no disponible aunque aparezca después. Las máscaras distinguen indisponibilidad para ese modelo. Si el algoritmo elegido requiere imputación, ajustarla solo en train y conservar las máscaras; validación/test no se usan para ajustar nada.

El código de replicación de corredores, leído como texto y no ejecutado, calcula estadísticas sobre eventos etiquetados `injury==0`, incluso para su test. **No reproducimos esa normalización que requeriría conocer etiquetas de evaluación**. Nuestros transformadores no usan y ni ajustan estadísticas de sujetos nuevos con el test. Tampoco se replica el bootstrap balanceado del notebook ni se afirman sus métricas publicadas.

No se recombinan los archivos día/semana: tienen filas y positivos ligeramente distintos y muchos eventos subyacentes compartidos. Elegir una representación y mantener la misma asignación de sujetos para cualquier comparación. Ningún esquema se declara réplica exacta o split oficial prescrito por las publicaciones.

## 5. Comandos reproducibles y ubicaciones locales

Python 3.11+, **solo biblioteca estándar**, desde la raíz del repo:

```powershell
python -m research_data sources
python -m research_data acquire runners
python -m research_data prepare-runners --approach day
python -m research_data prepare-runners --approach week
python -m research_data acquire pamap2 --allow-large
python -m research_data prepare-pamap2
```

`--allow-large` es deliberado: sin él no se transfiere PAMAP2. Solo se automatizan estas dos fuentes abiertas. La descarga impone tamaño/disco/tiempo, valida checksums publicados cuando existen y registra SHA-256/procedencia. Una descarga fallida no se publica como archivo completo. El archivo temporal propio se elimina al fallar, sin tocar otros archivos.

Ubicaciones reales de esta ejecución:

```text
.research-data\raw\runners\README.txt
.research-data\raw\runners\day_approach_maskedID_timeseries.csv
.research-data\raw\runners\week_approach_maskedID_timeseries.csv
.research-data\raw\runners\acquisition.json
.research-data\raw\pamap2\pamap2.zip
.research-data\raw\pamap2\PAMAP2_Dataset.zip
.research-data\raw\pamap2\acquisition.json
.research-data\prepared\runners-day-v1\
.research-data\prepared\runners-week-v1\
.research-data\prepared\pamap2-protocol-v1\
```

Corredores diario: 26 archivos preparados / 288,896,728 bytes. Semanal: 26 / 298,602,808 bytes. PAMAP2: 15 / 56,475,153 bytes. Aproximadamente **2.05 GB locales** para las tres ejecuciones originales con ambos ZIP, fuentes y tablas; la expansión `.dat` completa no se guarda. La reproducción adicional de PAMAP2 ocupa otros 56,475,153 bytes. Los índices/JSON individuales siguen siendo datos sensibles aunque haya licencia abierta: no adjuntarlos al chat ni subirlos a Git.

Las descargas existentes se verifican y reutilizan; las preparaciones **nunca sobrescriben una ejecución existente**. Para reproducir con otra carpeta:

```powershell
python -m research_data prepare-runners --approach day --output .research-data\prepared\runners-day-replay
python -m research_data prepare-pamap2 --output .research-data\prepared\pamap2-protocol-replay
```

Cada ejecución incluye `dictionary.json` con nombres de todas las features y semántica. En PAMAP2 también se conserva `windows.jsonl` canónico local.

Verificación realizada sobre **todas** las filas/ventanas preparadas, no solo el header:

```powershell
python -m research_data verify .research-data\prepared\runners-day-v1
python -m research_data verify .research-data\prepared\runners-week-v1
python -m research_data verify .research-data\prepared\pamap2-protocol-v1
python -m unittest discover -s tests -p "test_research.py" -q
```

`verify` comprueba hashes, número/alineación de X/y/índices, correspondencia con filas canónicas, transformación numérica y ausencias; **recalcula** medias/SD a partir de train y comprueba ausencia de solapamiento de sujetos o ventanas temporales según el esquema. Las fixtures de las pruebas son pequeñas y **sintéticas**, no muestras de los atletas reales.

### Validación final y bloqueos del entorno

Se repitió la preparación completa de los nueve registros Protocol con el parser final y sus límites de lectura, en `.research-data\prepared\pamap2-protocol-replay`. Su verificación volvió a cubrir las **3,833 ventanas**; `summary.json` resultó idéntico byte a byte al original, incluidos los hashes de las tablas. La compilación de `research_data` también terminó correctamente.

La suite final ejecutó **70 pruebas**, con **12 errores reportados por restricciones de permisos**, por lo que **no se declara que la suite completa, build o navegador hayan pasado**. De las 15 pruebas de investigación, 14 terminaron sin error; la repetición de una preparación sintética de corredores quedó bloqueada al renombrar su carpeta temporal (`WinError 5`, dentro de `.research-data\synthetic-test-euowt22l`). Los demás errores reportados fueron conexiones HTTP locales denegadas (`WinError 10013`). El comando de navegador no llegó a iniciar Playwright: PowerShell rechazó la ejecución de `npm` con `AuthorizationManager check failed`. El build posterior a la suite no se ejecutó porque esta no terminó correctamente.

Estas restricciones no se eludieron ni se alteraron las pruebas para ocultarlas. El usuario eligió **entregar los archivos con los bloqueos documentados**, sin modificar la política del sandbox. Los resultados reales preparados/verificados permanecen en disco; esta entrega no tiene un commit nuevo y no se hizo push, merge ni PR. Para cerrar la validación completa será necesario habilitar esas operaciones en la política y ejecutar los comandos existentes.

## 6. Primer modelo recomendado y lo que estos datos no resuelven

**Primer objetivo bien delimitado: clasificar las 12 actividades Protocol de PAMAP2 a partir de ventanas sensoriales.** Las etiquetas existen, la tarea es clara y permite establecer un baseline antes de redes neuronales. Evaluar macro-F1, balanced accuracy y confusión por clase, además de sensibilidad a sujetos dejados fuera; la exactitud global puede ocultar clases/sujetos minoritarios. No hay un modelo entrenado ni métricas propias en esta entrega. Con nueve participantes, considerar posteriormente evaluación leave-one-subject-out; no afirmar validez poblacional a partir de miles de ventanas correlacionadas.

**Segundo estudio separado:** etiqueta binaria fuente de corredores, con solo aproximadamente 1.36% y 1.34% de positivos diario/semanal. Preservar prevalencia en evaluación, comparar con baselines triviales, usar PR-AUC además de ROC-AUC, precisión/recall, calibración e intervalos agrupados por atleta. Cualquier balanceo/imputación/selección de variables se ajusta solo en train; umbrales en validación, test una vez. Los eventos cercanos del mismo sujeto siguen correlacionados incluso dentro de un split; no tratarlos como ensayos clínicos independientes.

Ninguna de estas fuentes entrega un target universal de **readiness, fatiga Garmin, ganancia muscular medida o tiempo de carrera futuro** compatible automáticamente con el producto. No se fabrican sueño, HRV, RIR, series/cargas o etiquetas ausentes. Las valoraciones de recuperación de corredores pueden ser variables fuente, no validación de la fórmula de readiness del demo.

Para un modelo Daily Coach real faltan población/objetivo/horizonte definidos, protocolos comparables, consentimiento/retención, labels pertinentes y evaluación externa/temporal. La futura frontera de inferencia del producto sigue en `athleteos/domain.py::predict_demo`; **no se conecta un clasificador PAMAP2 o un estudio de lesión como reemplazo de readiness**. Las reglas científicas/versiones y snapshots existentes se preservan.

## 7. Decisiones y límites pendientes

1. **FitRec:** confirmar uso académico no comercial y autorizar tamaño/alcance de descarga; si el objetivo es comercial, solicitar permiso adecuado al titular antes de utilizarlo. No hay acceso concedido implícitamente por que la URL sea pública.
2. **Garmin:** elegir Personal con credenciales propias o el programa Business apropiado, revisar términos/consentimiento y disponibilidad real de campos. No se pide ni almacena una clave en el repo.
3. **Target de producto:** elegir un outcome medible y población. Las tablas listas no autorizan decisiones médicas ni convierten asociaciones en prevención.
4. **Commit y validación del código, al momento de esta entrega:** Git estaba bloqueado por la política del sandbox al leer la configuración global del Git incluido con la aplicación (`Permission denied`). Código/docs/datos locales estaban escritos; faltaba habilitar esa lectura para verificar estado y crear el commit, además de los permisos de pruebas descritos arriba. El usuario eligió recibir esta entrega sin desbloquearlos. No se eludió el bloqueo; en esta entrega no se realizó commit nuevo, push, merge ni PR. Se omite la ruta personal del equipo para compartir este informe.
