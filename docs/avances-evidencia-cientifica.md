# AthleteOS: avances de evidencia, trazabilidad y límites

**Revisión de fuentes: 3 de noviembre de 2026.** Esta entrega mejora la transparencia de la demostración. No constituye una revisión sistemática, validación clínica, prevención demostrada de lesiones, entrenamiento de un modelo ni calibración de predicciones.

## Actualización: decisiones informadas por evidencia, 15 de noviembre de 2026

La entrega original v2 descrita abajo ya disponía de reglas, observaciones y snapshots. **La adición v3 reutiliza esa infraestructura**, no un predictor nuevo entrenado: una lectura conjunta y compartida en Today, Dashboard, Adaptive Plan y Coach. Separamos cuatro capas: **hechos observados**, **contexto de fuentes**, **criterio provisional** y **revisión/acción sugerida**.

`prediction.monitoring_review` distingue: cruce del corte existente de cambio semanal **junto con** al menos un corte existente de recuperación; cambio de carga aislado; señales de recuperación sin incremento demostrado; observaciones incompletas; o ausencia de cruces. El criterio conjunto es explicativo, provisional y **no modifica ningún valor del score, modo o dosis**. Una carga absoluta alta, o un cambio aislado, no se presenta como sobrecarga dañina confirmada. El entrenamiento puede producir adaptación; la coincidencia no demuestra lesión, causalidad ni prevención.

Se muestran AU actuales/baseline, cobertura 7/28 fechas, valores y unidades de las seis señales, procedencia de recuperación y comparabilidad. Las fuentes se enlazan por variable/regla concreta. Sueño/fatiga/dolor son observaciones actuales, **no cambios longitudinales medidos**; solo HRV/FC y carga tienen aquí comparación con baseline. Datos ausentes o baseline cero/incompleto no se reemplazan; incompatibilidades declaradas excluidas no producen un cambio. Comparabilidad desconocida se conserva como desconocida, aun cuando se mantiene el cálculo demo legado. Falta de cruce no prueba seguridad ni adaptación.

**Nueva fuente consultada:** Franco M. Impellizzeri, Alan McCall, Patrick Ward, Luke Bornn y Aaron J. Coutts, *Training Load and Its Role in Injury Prevention, Part 2: Conceptual and Methodologic Pitfalls*. Journal of Athletic Training, 19 septiembre 2020;55(9):893–901. DOI [10.4085/1062-6050-501-19](https://doi.org/10.4085/1062-6050-501-19); [texto completo PMC7534938](https://pmc.ncbi.nlm.nih.gov/articles/PMC7534938/). Se leyeron abstract, introducción práctica, marco conceptual y secciones metodológicas: exposiciones, ratios, medidas de carga, ventanas temporales, discretización, definiciones de lesión, análisis, generalización, ausencias y reporting. No se trata de un consenso de enfermedad ni de una cohorte de validación.

Su alcance respalda **cautela de interpretación y contextualización de carga con respuesta del atleta**, no nuestro criterio conjunto, +30%, <6 h, <-20%, +7 bpm, puntuación o reducción 40%/60%. La crítica de ACWR no es un estudio directo de nuestro cambio semanal. Los papers contextualizan métodos; no son filas de entrenamiento ni etiquetas. Se consultó también el [corrigendum de 17 mayo 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8130765/): reconoce comentario complementario con contenido solapado y cita omitida, sin validar umbrales. No se atribuye acceso completo a Walsh ni a la otra crítica de Impellizzeri de la entrega previa.

**Versiones y persistencia:** nuevas decisiones usan `demo-rules-v3` / `demo-heuristic-v3`; el estado permanece schema v2. Todos los parámetros numéricos v2 se conservan. Los snapshots antiguos guardan sus manifiestos, features, recomendaciones y hashes originales: no se reescriben con la nueva fuente ni se invalidan al leer. Nuevos snapshots añaden la explicación actual. Un ajuste previamente aceptado conserva la decisión/dosis originales. No se conectan runners/PAMAP2 al coach, ni se presentan probabilidades de lesión o eficacia de prevención. La validación enfocada cubre casos conjuntos/aislados, ausencias/comparabilidad, coherencia de explicaciones y convivencia v2/v3; los bloqueos de ejecución se deben reportar separadamente, no declararse aprobados.

## 1. Qué se implementó

El frontend y el backend siguen funcionando juntos, con datos sintéticos o CSV normalizado y almacenamiento local. Las reglas ahora están identificadas como **`demo-rules-v2`**, con predictor **`demo-heuristic-v2`**.

| Avance | Implementación y efecto |
|---|---|
| Reglas y referencias versionadas | `athleteos/evidence.py` concentra los parámetros de señales, puntuación, reducción de dosis y Micro Wins, junto con fuentes, población, protocolo, alcance y límites. Distingue respaldo de la variable, del método y del corte exacto. |
| Separación de capas | Dashboard muestra métricas calculadas y una tabla de observaciones/cambios, cortes provisionales y cruces. Un cruce es una bandera de producto, no un estado clínico. La recomendación es otra capa, no una medición. |
| Baselines individuales | HRV y frecuencia cardiaca en reposo incluyen ventana, observaciones disponibles/utilizadas, mínimo requerido, media, desviación estándar poblacional y CV descriptivo cuando la media permite calcularlo. |
| Comparabilidad explícita | CSV y check-in aceptan dispositivo/protocolo opcionales. Los pares declarados se comparan exactamente; las diferencias conocidas se excluyen. Sin metadatos no se inventan equivalencias. |
| Explicaciones coherentes | Dashboard, Adaptive Plan y AI Coach presentan por qué, datos, calidad, versión y referencias del mismo registro. Los detalles de cada fuente muestran población, protocolo, limitaciones y contenido realmente revisado. |
| Historial reproducible | Se guardan snapshots independientes de entradas, features, predicción, recomendación y manifiesto de evidencia. Los resultados posteriores se registran por separado y enlazan la decisión cuando existe. |
| Compatibilidad | El almacenamiento v1 migra a v2 sin reiniciar atletas ni borrar registros. Se preserva una copia v1; no se reconstruyen decisiones antiguas que nunca se registraron. |

Los archivos principales son `athleteos/evidence.py`, `athleteos/domain.py`, `athleteos/server.py`, `web/contracts.d.ts` y `web/app.js`. Las comprobaciones específicas están en `tests/test_evidence.py`, además de las pruebas HTTP y de navegador.

## 2. Cómo interpretar el respaldo

**Variable respaldada en un contexto estudiado** significa que una fuente justifica considerar esa observación; no implica que cualquier dispositivo, población o escala sea equivalente.

**Método respaldado con límites** significa que una operación o protocolo fue estudiado. Una correlación alta no demuestra precisión individual, causalidad, una dosis óptima ni prevención de lesiones.

**Corte provisional** significa una decisión de esta demostración sin calibración suficiente. Todas las señales, transformaciones de readiness, modos, reducciones de dosis y recompensas siguen en esta categoría.

Las operaciones descriptivas sin corte científico aparecen como `not-applicable` para el corte exacto. Eso **no valida sus filtros de producto**: las ventanas de 28 días, el mínimo de 7 mediciones, el filtro de hasta 10 repeticiones y los filtros de ritmo siguen siendo elecciones provisionales.

No se presenta un porcentaje de confianza inventado. `trace.confidence` es `null`. La puntuación de readiness y el CV, aunque numéricos, **no son probabilidades ni confianza calibrada**.

## 3. Matriz de evidencia por familia de reglas

Los identificadores corresponden al registro que entrega `GET /api/evidence`. La columna de limitaciones debe leerse junto con población/protocolo de la sección siguiente.

| Familia / ID | Variable y método: alcance del respaldo | Corte/filtro del producto | Limitaciones y decisiones de esta entrega |
|---|---|---|---|
| Carga sRPE, monotonía y strain (`srpe`) | Foster [1] y Haddad [2]: RPE global de sesión × minutos; revisión de métodos de carga y derivados. | Siete fechas explícitas para totales semanales; sin umbral de lesión. | RPE requiere familiarización y protocolo de recogida. AU no son probabilidad de lesión. Cargas constantes dejan monotonía/strain indefinidos. |
| Baselines (`baseline`) | Buchheit [4]: seguimiento intraindividual, variabilidad y condiciones estandarizadas. Media, SD poblacional y CV son descriptivos. | 28 días anteriores, mínimo 7 mediciones: **provisional**, no requisito científico universal. | Se excluye hoy. SD entre días no equivale a error de medida, cambio clínicamente importante o significación. |
| Sueño (`sleep`) | Walsh [3]: considerar necesidades individuales y calidad de evaluación del sueño. | `<6 h`, referencia de `8 h` en el score: **provisionales**. | El consenso no valida esos cortes ni una reducción automática de entrenamiento. Efectos de restricción parcial breve son inciertos. |
| Fatiga y dolor muscular (`fatigue`, `soreness`) | Saw [5]: utilidad del seguimiento subjetivo repetido con cuestionarios establecidos. | `>=7/10` en escalas propias: **provisional**. | No trasladar validez de cuestionarios estudiados a estas escalas nuevas. Dolor muscular no diagnostica lesión. |
| HRV (`hrv`) | Buchheit [4]: utilidad contextual de mediciones repetidas y comparables; respuestas pueden ser contradictorias. | Cambio `<-20%`: **provisional**. | HRV genérica en ms no es lnRMSSD. Una subida no siempre implica mejor estado, ni una bajada peor rendimiento. Dispositivo, índice, postura y horario importan. |
| FC en reposo (`resting-hr`) | Buchheit [4]: seguimiento individual con protocolo y contexto. | Cambio `>=+7 bpm`: **provisional**. | Hidratación, entorno, postura y fase de entrenamiento pueden confundir la comparación. No hay interpretación universal de +7 bpm. |
| Cambio de carga semanal (`weekly-load`) | Haddad [2] respalda el contexto de cuantificación. Impellizzeri [6] aporta una crítica de inferencia causal y construcción de ratios. | `>+30%` frente al promedio de cuatro semanas anteriores: **provisional**. | Esta fórmula no es ACWR. La crítica de ACWR no prueba ni valida nuestro corte; se incluye como advertencia, no como justificación retroactiva. Baseline cero/incompleto produce `null`. |
| Readiness y modos (`readiness`) | [3–5] respaldan observar variables, **no esta agregación**. | Media no ponderada de ≥3 componentes; cortes 50/75 y 2/3 señales: **todos provisionales**. | No hay pesos ajustados, etiquetas de respuesta o calibración. `100-readiness` tampoco es fatiga fisiológica medida. |
| Recomendación de dosis (`dose`) | [3–4] aportan contexto de recuperación, **no una prescripción exacta**. | PROTECT: 40% de duración/RPE≤2; RECOVER: 60%/RPE≤3; paseo: **provisional**. | No se garantiza seguridad ni prevención de lesiones. Se conserva el plan original y los descansos; BUILD nunca aumenta automáticamente la carga. |
| Volumen y series de fuerza (`strength-volume`) | Aritmética del registro; IUSCA [8] distingue estímulo, fuerza e hipertrofia y evidencia aguda/longitudinal. | Series directas y kg-repeticiones, sin dosis óptima inferida. | Un ejercicio por sesión diaria; no se adivina estímulo indirecto ni crecimiento muscular. |
| Estimación Epley (`epley`) | LeSuer [7]: comparación de ecuaciones bajo un protocolo específico de repeticiones hasta fatiga y 1RM probado. | `kg × (1 + reps/30)`; filtro ≤10 reps: restricción **provisional** de la app. | Se etiqueta RIR>0 como `non-failure-set`, RIR ausente como `effort-unknown` y RIR=0 como declaración, no verificación. Poblaciones entrenadas y ejercicios arbitrarios no quedan validados por ese estudio. |
| Ritmo descriptivo (`pace`) | Minutos/km y comparación aritmética de registros; no se invoca validación predictiva. | ≥3 km, RPE 3–5, ≥2 carreras recientes y ≥3 previas: filtros **provisionales**. | Terreno, clima y dispositivos no están controlados. Menor ritmo registrado no demuestra adaptación fisiológica ni predice una marca. |
| Micro Wins (`wins`) | Verificación de acciones y registros. [5,8] aportan contexto subjetivo/estímulo, no validación de recompensas. | 80% de adherencia; 3 sesiones clave; ≥5 días; 3–12 series en ≥2 grupos; mejora de ritmo ≥2% con distancia ±10%; 2 descansos: **provisionales**. | Importar o visualizar datos no otorga sesiones realizadas. “Adaptation Win” es un nombre de producto, no prueba de adaptación. No se premia sobrecarga con una recompensa de recuperación. |

La reserva cardiaca `(FC media−FC reposo)/(FC máxima−FC reposo)` conserva su tratamiento aritmético y sus requisitos de datos. No se usa como pronóstico ni se declara que una FC máxima registrada sea una FC máxima fisiológica validada.

## 4. Fuentes, población, protocolo y contenido verificado

La revisión fue focalizada, no exhaustiva. Se registran resultados negativos e incertidumbre; no se eligieron artículos para convertir retrospectivamente los cortes existentes en “científicos”.

### [1] Foster et al. (2001)

**A New Approach to Monitoring Exercise Training.**  
Enlace exacto: https://doi.org/10.1519/00124278-200102000-00019

Se leyó el abstract del editor. El contexto fue ciclismo continuo/interválico y baloncesto, comparando RPE global con carga derivada de FC. La tabla 2 de Haddad informa 12 participantes de ciclismo y 14 jugadores masculinos de baloncesto. Las puntuaciones absolutas difirieron pese a relaciones consistentes. Esto respalda cuantificar carga en contextos estudiados, no readiness, lesión o reducciones 40%/60%.

### [2] Haddad et al. (2017)

**Session-RPE Method for Training Load Monitoring: Validity, Ecological Usefulness, and Influencing Factors.**  
Enlace exacto: https://pmc.ncbi.nlm.nih.gov/articles/PMC5673663/

Se revisaron texto completo de la fundamentación, cálculos, discusión de validación y tabla 2: 36 estudios de validez/fiabilidad, con deportes, edades y niveles distintos. El método utiliza RPE de sesión con escala modificada CR-10 y familiarización, multiplicado por minutos. También describe monotonía/strain. La recogida de RPE y otros factores condicionan su interpretación; no demuestra un corte causal universal de carga.

### [3] Walsh et al. (2021)

**Sleep and the athlete: narrative review and 2021 expert consensus recommendations.**  
Editor: https://bjsm.bmj.com/content/55/7/356  
Abstract institucional consultado: https://researchonline.ljmu.ac.uk/id/eprint/16297/  
DOI: https://doi.org/10.1136/bjsports-2020-102025

El editor devolvió HTTP 403; se verificó el abstract institucional, **no se afirma revisión del texto completo**. El consenso destaca necesidades individuales: un enfoque universal de 7–9 horas puede no ser ideal. Señala incertidumbre sobre restricción parcial durante 1–3 noches, representación limitada de mujeres y limitaciones de control/evaluación. No valida `<6 h`, el denominador de 8 h ni nuestra reducción de dosis.

### [4] Buchheit (2014)

**Monitoring training status with HR measures: do all roads lead to Rome?**  
Enlace exacto: https://pmc.ncbi.nlm.nih.gov/articles/PMC3936188/

Se revisaron abstract, condiciones de registro, tabla 1 y secciones de respuestas agudas/crónicas contradictorias. Ejemplos orientados al entrenamiento aeróbico, de recreativo a élite. Importan índice de HRV, dispositivo, postura, horario, ambiente, error de medición y contexto. HRV puede subir con peor bienestar o bajar mientras mejora el rendimiento. El SD/CV descriptivo que calcula AthleteOS no estima automáticamente error de medición o cambio significativo.

### [5] Saw, Main y Gastin (2016)

**Monitoring the athlete training response: subjective self-reported measures trump commonly used objective measures: a systematic review.**  
Enlace exacto: https://pmc.ncbi.nlm.nih.gov/articles/PMC4789708/

Se revisaron abstract, selección, síntesis y resultados: 56 estudios originales, mediciones repetidas subjetivas/objetivas y cuestionarios establecidos con validez/fiabilidad publicada. Las medidas subjetivas y objetivas generalmente no se correlacionaron; la heterogeneidad impidió un metaanálisis. No valida nuestra escala propia 0–10, un corte de 7 o la media compuesta. La revisión de bienestar no incluye RPE como cuestionario de bienestar.

### [6] Impellizzeri et al. (2020)

**Acute:Chronic Workload Ratio: Conceptual Issues and Fundamental Pitfalls.**  
DOI: https://doi.org/10.1123/ijspp.2019-0864  
Registro público: https://europepmc.org/article/MED/32502973  
Abstract indexado verificado: https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID%3A32502973%20AND%20SRC%3AMED&format=json&resultType=core

El editor devolvió 403; se leyó el abstract indexado de PMID 32502973, no el texto completo. La crítica aborda artefactos de ratios e inferencia causal: no está establecido que manipular ACWR reduzca lesiones. No es un ensayo de nuestra comparación semanal desacoplada y no prueba directamente nuestro +30%. Es evidencia de una limitación metodológica, no respaldo de ese corte.

### [7] LeSuer et al. (1997)

**The Accuracy of Prediction Equations for Estimating 1-RM Performance in the Bench Press, Squat, and Deadlift.**  
Enlace exacto: https://doi.org/10.1519/00124278-199711000-00001

Se leyó el abstract del editor; identidad/contexto de las ecuaciones se contrastó en texto indexado. Participaron 67 universitarios no entrenados (40 hombres, 27 mujeres), con cuatro sesiones de práctica técnica, 1RM probado y repeticiones hasta fatiga en press banca, sentadilla y peso muerto. Se compararon siete ecuaciones. Correlaciones altas coexistieron con sesgo; todas subestimaron peso muerto. No valida automáticamente RIR>0, remo u otros ejercicios ni atletas entrenados.

### [8] Schoenfeld et al., IUSCA (2021)

**Resistance Training Recommendations to Maximize Muscle Hypertrophy in an Athletic Population: Position Stand of the IUSCA.**  
Editor: https://journal.iusca.org/index.php/Journal/article/view/81  
DOI: https://doi.org/10.47206/ijsc.v1i1.81

Se leyeron abstract y metadatos del editor; no se afirma revisión completa de dosis. El consenso distingue constructos de hipertrofia, evidencia aguda/longitudinal y fuerza/hipertrofia. Registrar series o kg-repeticiones no mide área muscular. Esta revisión focalizada no establece nuestros cortes de recompensa de 3/12 series.

## 5. Comportamiento conservado y cambios intencionales

Se conservan las fórmulas, unidades, prioridad de modos y cortes del demo original. Con datos antiguos sin metadatos, las comparaciones numéricas se mantienen, pero se etiquetan como **comparabilidad desconocida**. No se agregan umbrales “científicos” nuevos.

Cambios justificados:

1. Si hoy declara dispositivo y protocolo, solo se usan mediciones anteriores que declaran ese mismo par. Las desconocidas se excluyen de esa comparación y las diferencias conocidas se cuentan. Puede desaparecer un baseline que antes existía numéricamente; la app muestra observaciones utilizadas e insuficiencia, no rellena valores.
2. Si hoy no tiene contexto declarado y el historial tiene más de un contexto conocido, no se combina todo en una media falsa: se indica `mixed-declared-protocols` y el baseline queda insuficiente.
3. Con menos de 7 mediciones utilizables, la media de referencia queda `null`; baseline HRV cero no admite delta porcentual. Una serie constante presenta SD=0 sin significación clínica; las cargas constantes no generan monotonía infinita.
4. Epley conserva la aritmética, pero ahora explicita si el set no fue al fallo, el esfuerzo es desconocido o el fallo solo fue declarado.
5. Cambiar la meta también invalida una aceptación pendiente de hoy, para no vincular una decisión aceptada a un contexto de meta editado. El snapshot anterior permanece intacto; check-ins, importaciones y cambios del plan mantienen la invalidación ya existente.
6. Las acciones válidas pueden añadir un snapshot; navegar/leer no crea historial. Una escritura fallida revierte también las nuevas entradas de historial.
7. La adherencia registrada comprueba también el techo de RPE elegido. Se corrige el caso en que una sesión más corta, pero más intensa, podía pasar solo por igualar la carga AU. No se añade un corte científico: se aplica literalmente el RPE ya recomendado. El exceso se guarda honestamente y no otorga Recovery Win.

## 6. Contrato de metadatos y calidad

Se acepta el header CSV v1 original o el mismo header con **estos cuatro campos al final, en este orden**:

```text
hrv_device,hrv_protocol,resting_hr_device,resting_hr_protocol
```

Cada pareja se proporciona completa y con su medición correspondiente, o se deja vacía. Texto de hasta 160 caracteres, sin cadenas vacías de espacios. Ejemplo de pareja: dispositivo `demo-device-A`, protocolo `RMSSD; morning; seated; 5 min`. Es una declaración manual, no una conexión o verificación de un wearable.

Los pares se comparan con igualdad de texto después de quitar espacios exteriores: un cambio de descripción cuenta como diferente. La declaración debe describir índice, postura, momento/duración y demás condiciones relevantes; la app no interpreta equivalencia semántica ni certifica precisión.

El export CSV incluye los cuatro campos, y el check-in permite editarlos. Los CSV antiguos siguen siendo válidos. Un check-in con campos opcionales vacíos borra la medición/metadatos previos de hoy; registrar una sesión conserva los metadatos de recuperación vigentes.

`features.baseline_quality` contiene HRV, FC reposo y calidad de carga. La calidad de carga incluye fechas observadas/esperadas y variabilidad diaria, pero el protocolo de recogida de RPE sigue desconocido. Terreno/clima/dispositivo del ritmo tampoco se inventan.

## 7. Historial para evaluación futura, sin falsos resultados

El almacenamiento es local en `.athleteos\state.json`, excluido de Git. Al migrar v1 se guarda `.athleteos\state.v1-backup.json` antes de reemplazar el estado; una copia ya existente no se sobrescribe. Si esa copia es diferente, se crea otro backup con sufijo único, preservando también el original actual. Otra ruta `--data` produce su backup v1 equivalente. Los registros/ediciones antiguos se conservan; completados/aceptaciones/recompensas sin trazabilidad original quedan `legacy-unrecorded`.

Se registra una decisión al guardar meta, plan o check-in, importar, aceptar una reducción, guardar explícitamente un snapshot, y antes de registrar una sesión sin aceptación previa. Cada snapshot conserva:

- ID, fecha de referencia, hora de captura y acción que lo originó.
- Entradas normalizadas de los 35 días relevantes, check-in, meta y sesión original; `scheduled_today` distingue una sesión programada del placeholder “No session scheduled”, que no es un descanso observado.
- Features, predicción, recomendación, versión de reglas/predictor y manifiesto completo de fuentes/parámetros.
- SHA-256 determinista de entradas y manifiesto; son identificadores de integridad/reproducibilidad, **no confianza estadística**.

Una sesión real registrada enlaza la decisión aceptada o la calculada antes de escribir el resultado. El resultado guarda duración, RPE, carga AU, distancia/volumen de fuerza cuando fueron registrados y adherencia a la dosis elegida. No contiene masa muscular ganada, diagnóstico, probabilidad de lesión o rendimiento futuro.

Una aceptación v1 sin snapshot no recibe retrospectivamente una decisión inventada: su resultado posterior puede tener `decision_id: null`. Cambiar registros, meta o reglas actuales no reescribe snapshots previos. Un historial antiguo sin inputs no se vuelve reproducible por migrarlo.

Dashboard y Adaptive Plan muestran un resumen de las últimas 12 decisiones; **Export replayable JSON** descarga el historial completo de ese atleta:

```text
GET /api/athletes/demo-alex/decisions
```

Para reproducir una decisión de la versión actual, usar su `as_of`, `inputs.records`, `inputs.checkin` con `calculate_features`, luego `predict_demo` y `recommend(inputs.session, prediction)`. Comparar con los outputs almacenados y verificar hashes. Una versión histórica distinta requiere su implementación correspondiente; un manifiesto no sustituye el código ejecutable. Esto prepara registros para evaluar reglas/modelos, pero **no ejecuta entrenamiento ni valida un modelo**.

## 8. Cómo ejecutar e inspeccionar

Desde la raíz, Python 3.11+:

```powershell
python -m athleteos.server
```

Abrir http://127.0.0.1:8000. El backend sirve el frontend y todas las interacciones son locales. Sam demuestra reducción de dosis; Alex, mantenimiento/construcción; el perfil vacío demuestra falta de datos. Los datos no se rellenan automáticamente al cambiar de fecha.

En Dashboard revisar “Observed data” e “Individual baseline quality”. En Adaptive Plan revisar la comparación original/adaptada, reglas y snapshots. En AI Coach elegir una de las cinco preguntas: la respuesta es determinista y acotada a los resultados actuales; no hay LLM conectado.

Para inspeccionar el manifiesto completo:

```text
GET /api/evidence
GET /api/health
```

Comprobaciones de código, contratos, API, persistencia e interfaz:

```powershell
python -m unittest discover -s tests -p "test_*.py" -q
npm run build
$env:ATHLETEOS_BROWSER_CHANNEL = "msedge"
npm run test:browser
```

Las dependencias de desarrollo se instalan con `npm ci` si no están disponibles. Las pruebas del navegador usan su propio estado temporal, no el archivo de demostración del usuario. Pasar estas pruebas comprueba software y contratos, **no eficacia deportiva o clínica**.

## 9. Pendiente antes de datos reales, modelos o producción

Definir población, consentimiento y protocolo de medida; recoger repetición y error instrumental real; estudiar variación individual y comparabilidad; revisar literatura adicional y actualizar las reglas con control de versión. Antes de decidir umbrales, evaluar aplicabilidad y resultados negativos, no solo asociaciones favorables.

Definir outcomes observables y horizontes de evaluación. La adherencia local no es un outcome de prevención de lesión ni de mejora fisiológica. Separar atletas y tiempo en evaluación, prevenir fuga de datos, preservar transformaciones entrenadas e informar incertidumbre/calibración cuando puedan medirse de verdad. Comparar reglas, modelo y baselines sin atribuir causalidad a registros observacionales.

La frontera de inferencia sigue en `predict_demo(features)` de `athleteos/domain.py`, usada por las vistas, aceptación/completado y captura de decisiones del servidor. Un futuro adapter real deberá conservar el contrato normalizado, calidad/missingness, versión/fuente y explicaciones honestas. No puede dejar snapshots funcionando con una heurística mientras la pantalla afirma usar un modelo.

Producción requiere autenticación, autorización, cifrado, políticas de conservación, backup/rotación, aislamiento y revisión de seguridad/privacidad. El JSON actual es local y no cifrado; no exponer el servidor ni introducir datos reales de salud en esta demostración. Garmin permanece como integración oficial futura sujeta a aprobación del programa y consentimiento. No se ha desplegado nube, conectado Garmin ni descargado datasets de investigación.
