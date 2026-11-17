# AthleteOS AI: avance real, datos y resultados

**Resumen para el profesor. Revisión: 10 de noviembre de 2026, hora local UTC-6.**

**Contribución ejecutada:** se construyó una aplicación frontend/backend funcional, un registro de evidencia y un pipeline reproducible que ya entrenó, guardó y evaluó dos modelos con datos reales. PAMAP2 alcanzó **58.13% de accuracy frente a 9.33%** del comparador; el modelo de corredores obtuvo **AP 0.017603849 frente a 0.014223402**. Son resultados de modelos, no porcentajes de mejora deportiva o de lesiones prevenidas.

## Avances demostrables y pregunta de investigación

AthleteOS busca apoyar decisiones de entrenamiento individualizadas mediante carga, respuesta y contexto. La pregunta de investigación es si esas observaciones permiten estimar resultados pertinentes y, en una evaluación posterior, si utilizar recomendaciones mejora al atleta. El trabajo actual completa la infraestructura y dos benchmarks iniciales; no presupone la respuesta.

El MVP conecta Goal, Today, Dashboard, Adaptive Plan, Micro Wins y AI Coach a una API Python con CSV validado, check-ins y persistencia local. Calcula carga sRPE, ritmo descriptivo, baselines y volumen de fuerza, con calidad y ausencias explícitas. El registro de evidencia versiona fuentes/reglas y guarda snapshots de decisiones. El coach explica cálculos mediante `demo-heuristic-v2`; los modelos reales siguen separados de la app.

Ya existen artefactos JSON y manifiestos verificables de **`pamap2-activity-gnb-v1`** y **`runners-day-logistic-v1`**, con entrenamiento, evaluación e inferencia local reales. Se registran hashes, configuración, orden de variables y resultados negativos; no es una simulación de entrenamiento. El avance favorece el objetivo de investigar rendimiento y riesgo al permitir comparar hipótesis de forma reproducible, no al demostrar todavía su beneficio.

## Datos utilizados y normalización reproducible

| Dataset y tarea | Datos utilizados | Train / validación / test |
|---|---|---|
| PAMAP2, UCI, CC BY 4.0: actividad, 12 clases | Protocol: 2,872,533 muestras; 3,833 ventanas de nueve personas. Optional y transiciones excluidos. | Personas: 5 / 2 / 2. Ventanas: 2,352 / 977 / 504. |
| Corredores, Dataverse, CC0: etiqueta fuente `injury` del día t | 42,766 ventanas diarias de 74 personas; 583 positivas. Predictores de t-7 a t-1; base=t-7 y `.6`=t-1 según README corregido. | Personas: 44 / 15 / 15. Ventanas: 23,963 / 8,257 / 10,546; test con 150 positivas. |

Son cohortes/tareas distintas. Diario y semanal de corredores son representaciones solapadas, **no se concatenan**. El protocolo principal separa personas; ID, fecha, etiqueta y split no entran en X. No se utilizan variables del día del evento o posteriores. Los detalles de onset clínico, demora de registro y episodios/censura no están resueltos: la clasificación de etiqueta fuente es retrospectiva.

**1. Normalización del esquema de la app:** se validan columnas, fechas, tipos, unidades y rangos declarados, por ejemplo minutos, km y RPE 0-10. Vacío significa ausente, no cero. Esto estandariza el contrato de entrada; no convierte automáticamente sensores o escalas de investigación al CSV demo ni aplica un z-score al coach.

**2. Extracción PAMAP2:** se conservan 40 canales en sus unidades fuente (bpm, temperatura, aceleración, giroscopio y magnetómetro); no se deriva HRV de FC. Cada ventana no solapada de 500 muestras, nominalmente cinco segundos y de una sola actividad/persona, produce media, desviación estándar poblacional y fracción observada por canal: **40 × 3 = 120 features**. Se reinicia ante gaps/cambios; no se interpolan datos.

**3. Limpieza de corredores:** diez variables por cada uno de siete días dan **70 features**: sesiones, km/zonas, fuerza, horas alternativas y percepciones. Se leen valores numéricos originales y se conserva su escala/unidad fuente; no se asegura haber “desnormalizado” la fuente ni convertido percepciones a RPE 0-10. El `-0.01` subjetivo de descanso pasa a `null`, no a “buena recuperación”. No se inventan sueño, HRV, hipertrofia o etiquetas de mejora.

**4. Transformación estadística para entrenar:** primero se separan participantes. Cada modelo aprende solo con train la mediana por feature, rellena faltantes y aprende media y SD poblacional del entrenamiento imputado; aplica `z = (valor - media_train) / SD_train` a train/validación/test. Columnas constantes usan divisor 1; una columna enteramente ausente en train permanece no disponible. Se anexan indicadores de ausencia: PAMAP2 **120 + 120 = 240** entradas y corredores **70 + 70 = 140**. Validación elige configuración; el modelo se congela antes del test separado, sin reajustar con test.

En PAMAP2 hubo **cero features agregadas nulas**: la imputación estaba disponible, pero no hizo falta rellenarlas. FC llega aproximadamente a 9 Hz sobre una rejilla IMU de 100 Hz; fracción observada cercana a 0.09 **no significa 91% de pérdida fisiológica**. En corredores sí hubo faltantes subjetivos: 134,505 celdas, 8.02% de las 70 columnas de train principal. No se transforma ausencia en salud.

Los entrenadores leen las features originales canónicas de `records.jsonl`, no vuelven a escalar el CSV `.features.csv` ya estandarizado de preparación: **no hay doble normalización**. Ejemplo exclusivamente **SINTÉTICO**: si train tiene media 10 y SD 2, un valor 14 se convierte en z=2; si faltaba y la mediana de train era 10, queda z=0 más máscara=1. No es una fila ni un resultado de un atleta real.

## Resultados de entrenamiento y sustento científico

| Modelo / evaluación principal | Resultado real frente al comparador | Interpretación y errores |
|---|---|---|
| Gaussian Naive Bayes, PAMAP2; 504 ventanas | Accuracy 58.13% vs 9.33%; macro-F1 0.528234 vs 0.014217; balanced accuracy 58.44% vs 8.33%. | 293/504 aciertos vs 47/504. Sitting: 0/46; Nordic walking: 2/40; rope jumping: 11/37. Señal útil para un baseline de actividad, aún con fallos materiales. |
| Logística L2, corredores; 10,546 ventanas de 15 personas no vistas | AP 0.017603849 vs 0.014223402; ROC-AUC 0.584473 vs 0.5. Umbral 0.02 elegido en validación. | TN 7,631; FP 2,765; FN 98; TP 52. Precisión 1.85%, recall 34.67%, F1 0.035052. Ranking apenas superior al trivial; no utilidad clínica demostrada. |

AP resume precisión-recall con empates agrupados, no área trapezoidal; el fuerte desequilibrio exige compararla con prevalencia, no destacar accuracy. En corredores, 52 de 2,817 alertas son positivas y se omiten 98/150; al umbral 0.5 solo se detecta 1/150. El comparador siempre negativo logra 98.58% de accuracy sin detectar ninguna. El umbral ilustra un costo real de falsas alertas; los scores no están calibrados como riesgo clínico.

Estos resultados muestran **capacidad técnica ejecutada y señal descriptiva limitada bajo el protocolo**, no significación estadística, causalidad ni prevención. El benchmark temporal de corredores se reporta aparte en E5; permite personas recurrentes y no se mezcla con el principal. El modelo se congeló el 10 de noviembre a las 19:34:46 UTC-6, equivalente al 11 de noviembre a las 01:34:46 UTC.

### De la publicación científica a la variable: qué se respalda

| Fuente consultada | Uso metodológico en el proyecto | Lo que no permite concluir |
|---|---|---|
| Haddad et al., texto y tabla de validación: https://pmc.ncbi.nlm.nih.gov/articles/PMC5673663/ | sRPE como minutos × RPE; cuantificación contextual de carga. | No valida un corte universal de lesión ni el score del coach. |
| Buchheit, secciones de seguimiento: https://pmc.ncbi.nlm.nih.gov/articles/PMC3936188/ | Baselines intraindividuales, variabilidad y comparabilidad de protocolo. | HRV/FC no tienen interpretación universal ni acreditan mejora por sí solas. |
| Saw et al., revisión consultada: https://pmc.ncbi.nlm.nih.gov/articles/PMC4789708/ | Seguimiento subjetivo repetido y límites de las medidas. | No valida nuestras escalas propias, cortes o reparación muscular. |
| Impellizzeri et al., registro/abstract, no texto completo: https://europepmc.org/article/MED/32502973 | Advertencia sobre ratios de carga e inferencia causal. | No demuestra que manipular carga/ACWR reduzca lesiones ni valida nuestro +30%. |
| Baz-Valle et al., revisión consultada: https://pmc.ncbi.nlm.nih.gov/articles/PMC8884877/ | Contexto de volumen e hipertrofia; separar estímulo de respuesta medida. | No aporta aquí filas individuales ni demuestra crecimiento con el demo. |

Los artículos justifican observar variables y diseñar métodos; **los datasets suministran las filas y etiquetas reales**. No se extraen etiquetas ficticias de conclusiones de papers. Alcance completo de lectura y límites en E1/E3; fuentes de datos: https://doi.org/10.24432/C5NW2H y https://doi.org/10.34894/UWU9PV ; corrección temporal de corredores: https://dataverse.nl/api/access/datafile/422690 .

## Conclusión para presentar y siguiente experimento

**Conclusión defendible:** “Implementé un MVP conectado y una cadena reproducible de preparación, entrenamiento e inferencia con dos datasets reales. Superé comparadores triviales en tareas específicas y cuantifiqué errores, sin fuga entre participantes. Esta contribución establece una base experimental para investigar carga y respuesta; todavía no demuestra mejora del atleta ni prevención de lesiones”.

El siguiente experimento debe atacar errores medidos: revisar discriminación/robustez de las clases PAMAP2 fallidas y, para corredores, definir mejor el evento/horizonte y comparar modelos/umbrales solo en train/validación con un **nuevo test independiente**, evaluando AP, calibración y costo de falsas alertas. No se optimizará sobre los tests ya observados.

Para estudiar mejora deportiva hace falta un outcome longitudinal comparable de prueba/competición y después evaluar prospectivamente la intervención frente a un comparador. Recuperación requiere medición de función/retorno al baseline; hipertrofia, mediciones musculares longitudinales protocolizadas: no son equivalentes a dolor, HRV, series o e1RM. Privacidad, consentimiento e integración segura se resuelven antes de un piloto autorizado.

Se conservan sin cambios los porcentajes propuestos: rendimiento 20%, investigación lesión/sobrecarga 40%, recuperación 20%, masa muscular 20%; **global de esas cuatro líneas 25%** y **base habilitadora 80% aparte**. Reescribir la presentación no completa hitos. El anexo contiene íntegra la evaluación y sus evidencias para reproducir los cálculos; no son porcentajes de efecto ni un alcance aprobado.

## Anexo: rúbrica propuesta v1.0 y evaluación auditable

**Corte: 10 de noviembre de 2026, hora local UTC-6. Rúbrica propuesta v1.0; no es un alcance aprobado.**

**Estimación de cumplimiento de hitos: 25% para las cuatro capacidades objetivo, y 80% para la base habilitadora evaluada por separado.** El proyecto ya puede entrenar, guardar y evaluar modelos de investigación; todavía no ha demostrado mejorar rendimiento, prevenir lesiones, acelerar recuperación muscular ni aumentar masa muscular en atletas.

### 1. Qué proyecto estamos construyendo

AthleteOS Daily Coach busca reunir entrenamiento, metas, bienestar y decisiones diarias explicables. Existe un MVP frontend/backend conectado con registros demo o CSV, persistencia local, métricas, plan adaptable, Micro Wins y coach determinista. Su recomendación sigue siendo `demo-heuristic-v2`: un cálculo provisional, no un modelo fisiológico validado.

La ambición final exige algo distinto de producir una predicción: datos longitudinales adecuados, resultados verificables y evaluación de si actuar sobre las recomendaciones ayuda realmente al atleta. Clasificar actividades, detectar una etiqueta retrospectiva o calcular series de fuerza son pasos útiles, pero no prueban esos beneficios.

### 2. Resumen de porcentajes y cómo leerlos

| Línea evaluada | Hitos cumplidos / propuestos | Avance estimado |
|---|---:|---:|
| Mejora del rendimiento deportivo | 2 / 10 | 20% |
| Prevención de lesiones: investigación de riesgo/sobrecarga, sin beneficio preventivo demostrado | 4 / 10 | 40% |
| Recuperación muscular | 2 / 10 | 20% |
| Aumento de masa muscular | 2 / 10 | 20% |
| Global limitado a esas cuatro capacidades | 10 / 40 | 25% |
| Base habilitadora local de producto y ML, excluida del global anterior | 8 / 10 | 80% |

Son **estimaciones de cumplimiento técnico/de investigación**, no porcentajes medidos de esfuerzo, tiempo, presupuesto o madurez productiva. Tampoco son accuracy, probabilidad de lesión, confianza ni magnitud de mejora. No significa que se prevenga el 40% de lesiones o que se haya ganado el 20% de masa muscular.

**Beneficio real demostrado por el proyecto: no establecido para ninguna de las cuatro capacidades.** No se ha estimado un porcentaje de efecto; ausencia de demostración no equivale a demostrar un efecto de cero.

Cada hito vale un punto, sin crédito parcial. Se usa 1 solo si existe evidencia del criterio exacto; pendiente, no verificado o bloqueado vale 0. Por línea: `100 × cumplidos / 10`. El global es la media no ponderada de las cuatro líneas: `(20 + 40 + 20 + 20) / 4 = 25`, equivalente a `100 × 10 / 40`. La plataforma no entra en ese cálculo: no se suma 80% ni se cuenta dos veces su contribución.

La rúbrica es una propuesta auditable hecha para responder esta pregunta, no una planificación acordada. Los hitos tienen el mismo peso convencional, aunque su costo y dificultad sean muy diferentes. Si se acuerdan otros objetivos o criterios, habrá que versionarla y recalcular; los porcentajes no son una medida universal de “todo el proyecto”.

### 3. Rúbrica de las cuatro capacidades

Se proponen diez hitos por línea. H1-H4 acreditan preparación exploratoria; H5-H10 exigen desarrollo y evidencia específicos del uso final. Una prueba retrospectiva débil puede cumplir H4 sin cumplir H5 o H6. Esta escala no autoriza uso clínico ni comercial.

**H1. Contexto y límites revisados.** Existe revisión focalizada de variables/métodos relevantes y se documenta por qué no basta para afirmar beneficio. No exige ni acredita una revisión sistemática completa.

**H2. Observaciones precursoras implementadas.** El demo registra y calcula al menos una familia de variables relevante para la línea, con unidades y ausencias explícitas. Se acredita instrumentación, no medición del resultado fisiológico.

**H3. Datos reales para un benchmark pertinente.** Hay datos locales preparados con outcome de esa línea para una tarea acotada, diccionario, procedencia, timing y particiones auditados; los límites de la etiqueta se declaran. Una etiqueta fuente de evento permite un benchmark retrospectivo, no una definición clínica validada.

**H4. Baseline pertinente ejecutado.** Se ha ajustado y guardado un modelo para ese outcome acotado, con transformaciones solo en train, selección en validación, test separado, comparador y errores reportados. No exige que el resultado sea útil; exige mostrarlo honestamente.

**H5. Objetivo de uso y medición aceptados.** Se acuerdan población, outcome verificable, horizonte, protocolo de medición, decisiones permitidas, manejo de episodios/censura y métricas/criterios de aceptación antes de una nueva evaluación. Debe resolver las ambigüedades relevantes de la exploración.

**H6. Validez predictiva independiente.** Una evaluación externa o prospectiva apropiada cumple criterios preespecificados frente a baselines, con errores/subgrupos, dependencia por atleta y calibración cuando corresponda. No equivale aún a beneficio causal.

**H7. Integración de un modelo pertinente.** Un adapter versionado usa datos compatibles y la misma fuente en API, interfaz y snapshots, con manejo explícito de ausencias/fallos y límites de decisión. No cuenta conectar cualquier clasificador a readiness.

**H8. Piloto de uso real documentado.** Un piloto consentido bajo condiciones autorizadas verifica calidad, factibilidad, adherencia y uso de recomendaciones de esa línea, sin presentar usabilidad como eficacia.

**H9. Beneficio evaluado mediante intervención.** Un estudio prospectivo con comparación y mediciones adecuadas demuestra el beneficio definido de actuar sobre el sistema, considerando exposición, daños y factores de confusión. Una asociación retrospectiva no cierra este hito.

**H10. Replicación y límites de aplicación.** El resultado relevante se confirma en otra cohorte/contexto mediante protocolo predefinido y se documentan límites, seguimiento y condiciones para mantener o retirar el uso.

#### Checklist reproducible

P = rendimiento; L = lesión/sobrecarga; R = recuperación; M = masa muscular. Los códigos entre paréntesis enlazan con la evidencia descrita después. 0 significa criterio no cumplido, no un resultado fisiológico nulo.

| Hito | P | L | R | M |
|---|---|---|---|---|
| H1 | 1 (P1) | 1 (L1) | 1 (R1) | 1 (M1) |
| H2 | 1 (P2) | 1 (L2) | 1 (R2) | 1 (M2) |
| H3 | 0 | 1 (L3) | 0 | 0 |
| H4 | 0 | 1 (L4) | 0 | 0 |
| H5 | 0 | 0 | 0 | 0 |
| H6 | 0 | 0 | 0 | 0 |
| H7 | 0 | 0 | 0 | 0 |
| H8 | 0 | 0 | 0 | 0 |
| H9 | 0 | 0 | 0 | 0 |
| H10 | 0 | 0 | 0 | 0 |
| Total de puntos | 2 | 4 | 2 | 2 |

#### Evidencia de cada punto acreditado

**P1:** E1 revisa carga/seguimiento y limita el ritmo a comparación descriptiva; E2 explicita que no existe pronóstico deportivo validado. Es contexto y delimitación, no evidencia de mejora.

**P2:** `athleteos/domain.py`, función `calculate_features`, calcula carga sRPE, ritmo min/km y cambio descriptivo, con historia mínima y advertencias de terreno/clima/dispositivo; documentado en E1 y E6.

**L1:** E1 diferencia cuantificación de carga, crítica de inferencia causal y cortes provisionales; E5 documenta las limitaciones de la etiqueta de evento. No afirma que bajar una señal prevenga una lesión.

**L2:** `athleteos/domain.py`, funciones `predict_demo` y `recommend`, implementa señales de carga/bienestar y reducciones de dosis demo; E1 distingue observación, corte y recomendación. No es un score entrenado de riesgo.

**L3:** E3 y E5 registran el dataset de corredores CC0: 74 personas y 42,766 ventanas diarias, 583 positivas, antecedentes t-7 a t-1; partición por personas y temporal con purga. Sigue siendo etiqueta fuente retrospectiva con definición clínica incompleta.

**L4:** E5 y `research_data/runners_training.py` acreditan logística ajustada, JSON congelado, evaluación separada, comparador e inferencia local. Sus resultados débiles se muestran en la sección 5; no cierran validación independiente ni prevención.

**R1:** E1 revisa seguimiento subjetivo, sueño y medidas cardiacas con límites de protocolo; E3 explica que “perceived recovery” no se convierte automáticamente en una etiqueta de recuperación muscular.

**R2:** `athleteos/domain.py` y E1/E6 documentan check-ins, sueño, fatiga/dolor declarados, HRV/FC de reposo y baselines comparables cuando es posible. El score heurístico no mide reparación muscular ni tiempo hasta recuperar función.

**M1:** E1 y E3 revisan fuerza/volumen e hipertrofia y distinguen estímulo, fuerza y tamaño muscular. La revisión de hipertrofia no aporta filas individuales ni demuestra las dosis del producto.

**M2:** `athleteos/domain.py`, `calculate_features`, calcula series directas, volumen en kg-repeticiones y e1RM estimada por ejercicio; E1/E6 explican sus límites. Ninguna de esas variables mide masa o crecimiento muscular.

#### Por qué los demás puntos siguen en cero

Para rendimiento, recuperación y masa muscular no hay un dataset preparado con el outcome específico ni un baseline entrenado para él: H3-H4 siguen pendientes. PAMAP2 clasifica actividad y los datos de corredores no se han convertido en etiquetas de esos tres resultados.

Para las cuatro líneas faltan acuerdos y resultados que cierren H5-H10: definición de uso final y medición, validación independiente, integración del modelo pertinente, piloto real y evidencia de intervención/replicación. En lesión, los vacíos de adjudicación, episodios, demora de registro y retorno al entrenamiento impiden acreditar H5. La capacidad del demo para guardar metas o adaptar un plan no sustituye ninguno de esos criterios.

### 4. Base habilitadora: 80%, sin confundirla con eficacia

Esta segunda lista evalúa únicamente diez hitos propuestos de infraestructura local. Da crédito a lo que sí funciona, incluido PAMAP2, sin inflar los cuatro outcomes. No representa 80% de producción ni que el 20% restante sea poco trabajo.

| ID / criterio binario | Estado | Evidencia o brecha |
|---|---:|---|
| B1. Frontend/API demo conectados | 1 | E2/E6; superficies y acciones del MVP local. |
| B2. Validación y persistencia local de registros | 1 | E1/E6; CSV, check-ins, planes y errores explícitos. |
| B3. Reglas, procedencia y snapshots versionados | 1 | E1; entradas, reglas y resultados de dosis enlazados. |
| B4. Fuentes reales obtenidas con licencia/procedencia | 1 | E3; corredores y PAMAP2, sin incluir FitRec. |
| B5. Preparación y control de fuga documentados | 1 | E3/E4/E5; participantes separados y purga pertinente. |
| B6. Ajustes y evaluación reales ejecutados | 1 | E4/E5; dos tareas distintas, sin utilidad clínica asumida. |
| B7. Artefactos guardados, recarga e inferencia local | 1 | E4/E5; JSON y manifiestos locales verificables. |
| B8. Pruebas enfocadas y comandos reproducibles | 1 | E4/E5; pruebas sintéticas y ejecución registradas, no suite integral aprobada. |
| B9. Adapter de outcome pertinente integrado | 0 | La app usa heurística; modelos separados y contratos incompatibles. |
| B10. Entrega operativa protegida y reproducible desde repositorio | 0 | Falta consolidación/publicación autorizada, validación integral y requisitos productivos de acceso, protección, respaldo y operación. |

Los artefactos/datasets están en almacenamiento local ignorado. Los avances posteriores al MVP publicado no se presentan aquí como sincronizados con GitHub; no se reconsultó ni reintentó Git. Esta evaluación no modifica modelos, reglas ni el estado de usuario.

### 5. Qué datos y modelos tenemos realmente

| Fuente o componente | Estado y resultado | Relación con los cuatro objetivos |
|---|---|---|
| PAMAP2 | 3,833 ventanas de nueve personas; split 5/2/2; Gaussian Naive Bayes real. Test: accuracy 58.13%, macro-F1 0.528234. | Clasifica actividades, no mejora rendimiento ni estima recuperación/masa. Sitting 0/46 y Nordic walking 2/40 muestran errores materiales. |
| Corredores competitivos | 74 personas; modelo logístico diario real; split 44/15/15 por personas. Diario y semanal se solapan y no se suman como cohortes. | Investigación retrospectiva de etiqueta fuente de evento; no prevención demostrada ni una definición clínica resuelta. |
| FitRec | Documentación revisada; datos no adquiridos, pendiente finalidad/licencia académica no comercial y transferencia autorizada. | Potencial contexto para tareas FC/velocidad, no sustituto de outcomes longitudinales ni autorización de uso. |
| Garmin | Sin conexión, aprobación ni datos obtenidos. | Futura vía oficial consentida; no garantiza disponibilidad o validez de todos los campos. |
| Publicaciones científicas | Referencias para métodos, población y límites; revisión focalizada. | No son muestras de entrenamiento ni etiquetas individuales. No validan automáticamente pesos/cortes/dosis del demo. |

**Actualización frente al overview anterior:** el modelo de corredores ya está entrenado y evaluado. El artefacto se congeló el 11 de noviembre a las 01:34:46 UTC, equivalente al **10 de noviembre a las 19:34:46 UTC-6**; no hay contradicción con la fecha local de este informe. El overview previo queda como fotografía histórica, sin reescribirlo.

En su test principal hubo **15 personas retenidas, 10,546 ventanas y 150 etiquetas positivas**. AP = **0.017603849**, frente a **0.014223402** del comparador constante; ROC-AUC = **0.584473**. El umbral 0.02 se seleccionó solo en validación. Matriz: **TN 7,631; FP 2,765; FN 98; TP 52**. Precisión **1.85%** y recall **34.67%**. Es una mejora descriptiva pequeña de ranking y una carga alta de falsos positivos, no evidencia de prevención ni un resultado listo para intervención.

El benchmark temporal con purga es secundario y permite personas recurrentes; no reemplaza el test por personas nuevas. Ambos modelos de investigación están guardados localmente y **ninguno alimenta la recomendación de AthleteOS**.

### 6. Qué puede y qué no puede hacer hoy

Puede registrar datos demo/CSV y check-ins, calcular métricas descriptivas, mostrar calidad/ausencias, explicar reglas provisionales y conservar decisiones. Puede entrenar, guardar, recargar y evaluar dos tareas de investigación acotadas con separación de datos.

No puede afirmar que un atleta mejorará su marca, que una alerta evite una lesión, que un score mida reparación muscular o que cierta cantidad de series produzca crecimiento medido. No dispone de una evaluación prospectiva de esas intervenciones ni de un modelo integrado para ellas.

Para rendimiento faltan resultados comparables de pruebas o competición y su evolución tras decisiones, con contexto de carga, entorno y adherencia. Tener kilómetros o actividad reconocida no equivale a medir mejora atribuible.

Para recuperación faltan un outcome y un protocolo explícitos: por ejemplo, retorno de función medido de forma repetible a un nivel de referencia, si ese fuera el objetivo acordado. Dolor declarado, HRV y “perceived recovery” no son intercambiables con recuperación muscular medida.

Para hipertrofia faltan mediciones longitudinales pertinentes, como grosor/área muscular bajo protocolo de ecografía o resonancia, si ese fuera el resultado elegido, y registro de exposición/adherencia y factores relevantes. Series, kg-repeticiones, e1RM o cambios de peso corporal no se convierten en medidas directas de tejido muscular ganado.

### 7. Próximos hitos y qué elevaría los porcentajes

| Orden propuesto | Entrega y aceptación verificable | Efecto en esta rúbrica |
|---|---|---|
| 1. Acordar uso y medición por línea | Protocolo aceptado con población, outcome, horizonte, decisiones y métricas; para lesión resolver adjudicación, episodios/censura y timing. | Cerrar H5 añade 10 puntos porcentuales a la línea correspondiente; un plan no cierra datos o validación. |
| 2. Conseguir y preparar datos pertinentes | Acceso/licencia/consentimiento, etiquetas longitudinales, calidad y particiones auditadas para el outcome elegido. No crear etiquetas de masa/recuperación desde proxies. | Cerrar H3 añade 10 puntos a P, R o M. L3 ya está acreditado solo como benchmark fuente. |
| 3. Ajustar y evaluar baseline del outcome | Receta preespecificada, train/validación separados, nuevo test independiente y errores/comparador reportados; no optimizar sobre tests ya observados. | Cerrar H4 añade 10 puntos a P, R o M. Mejorar un score no da puntos adicionales a L4 ya cumplido. |
| 4. Validar fuera del benchmark | Datos externos/prospectivos y criterios previos cumplidos; análisis por atleta, errores y calibración pertinente. | H6 añade 10 puntos por línea que lo cumpla; no acredita beneficio causal. |
| 5. Integrar y pilotar con protección | Adapter compatible y versionado; después piloto consentido con calidad/factibilidad documentadas y operación autorizada. | H7 y H8 añaden 10 puntos cada uno al cerrarse; B9 se evalúa aparte, sin sumarlo al global. |
| 6. Demostrar beneficio y replicarlo | Comparación prospectiva de intervenciones con resultados/daños pertinentes y confirmación independiente. | H9 y H10 añaden 10 puntos cada uno; solo entonces podrá formularse el beneficio dentro de los límites estudiados. |

No se prometen fechas, tamaños de efecto ni presupuestos. Cada cierre exige evidencia, no solo implementar una pantalla. Si solo se cierra un hito de una línea, el global de 40 hitos aumenta **2.5 puntos porcentuales**.

La preparación de producción es una línea operativa separada: autenticación/autorización, protección de datos, consentimiento/retención, respaldo/restauración, observabilidad y consolidación reproducible del repositorio. Debe resolverse antes de datos personales en un servicio, pero **no demuestra eficacia científica**. La app actual sigue siendo una demostración local sin autenticación ni almacenamiento cifrado para producción.

### 8. Referencias y alcance documental

E1: [Evidencia, reglas y límites](avances-evidencia-cientifica.md). Código relacionado: `athleteos/domain.py`, `athleteos/evidence.py` y `athleteos/server.py`.

E2: [Overview anterior, fechado](overview-y-avance-del-proyecto.md). Sus afirmaciones anteriores al nuevo entrenamiento de corredores no sustituyen E5.

E3: [Datos reales y preparación](datos-reales-y-preparacion.md). Conserva la distinción de tareas, licencias y fuentes no adquiridas.

E4: [Modelo PAMAP2](primer-modelo-pamap2.md). Entrenamiento, evaluación, contrato, errores y artefacto local.

E5: [Modelo experimental de corredores](primer-modelo-corredores.md). Evidencia actualizada del ajuste real y sus límites.

E6: [README de ejecución y contratos](../README.md). Documento para ejecutar el demo y los comandos de investigación, no acreditación de eficacia.

Fuentes públicas ya revisadas en esos informes: PAMAP2, https://doi.org/10.24432/C5NW2H ; corredores, https://doi.org/10.34894/UWU9PV ; README corregido de corredores, https://dataverse.nl/api/access/datafile/422690 ; seguimiento con medidas cardiacas, https://pmc.ncbi.nlm.nih.gov/articles/PMC3936188/ ; seguimiento subjetivo, https://pmc.ncbi.nlm.nih.gov/articles/PMC4789708/ ; revisión volumen/hipertrofia, https://pmc.ncbi.nlm.nih.gov/articles/PMC8884877/ . No se realizó nueva revisión bibliográfica exhaustiva para asignar estos porcentajes.

Este documento es una evaluación documental, no un nuevo experimento: no se entrenó, descargó, cambió la aplicación, publicó código ni reintentó una operación Git bloqueada. Solo contiene agregados. La primera entrega conservó el mismo texto y destinos de referencia en Markdown y Word; las rutas y URLs de Word se presentaron como texto legible. La equivalencia de una revisión posterior requiere verificar nuevamente su conversión.
