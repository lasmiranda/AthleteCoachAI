# AthleteOS Daily Coach

A responsive, local full-stack MVP: **Today / Daily Mission, Dashboard, Goal, Adaptive Plan, Micro Wins and AI Coach**. The Python backend serves the actual frontend, validates normalized data, calculates features and saves changes. Daily readiness/dose remains heuristic; a separate, strictly gated **experimental5000m race predictor** can load actual local research artifacts. There is **no connected LLM or Garmin account**, nor four validated physiological predictors.

## Interfaz en español

### Sueño Garmin: carga explícita y asociación por fecha

En **Mi objetivo → Subir sueño Garmin y vincular por fecha**, selecciona
`Sleep.csv`, valida/previsualiza y confirma el guardado bajo el perfil elegido.
No se importa el adjunto automáticamente. Declara formato `hmin` (p. ej.
`7h 12min`), pulso en reposo `bpm`, calendario/zona verificados, procedencia,
significado de la fecha (despertar o etiqueta de noche) y día asociado
(misma fecha, anterior o siguiente). Ninguna convención viene preseleccionada.

Primera columna `Date` o `Sleep Score N Weeks/Months`, con fechas ISO
`AAAA-MM-DD`; `Score`, `Duration` y `Resting Heart Rate` son obligatorias.
UTF-8/BOM, hasta 1,5 MB y 5.000 filas. Vacíos/`--` son `null`, no cero.
`Duration` no se calcula desde Bedtime/Wake Time; esas horas locales no
generan timestamps UTC. Se conservan campos fuente pertinentes, incluido
Skin Temp Change con signo/apóstrofo/grados sin asumir escala térmica.

La previsualización muestra noches, duración, pulso y número de actividades
registradas en cada fecha asociada: conserva sesiones múltiples, solo enlaza
procedencia/calendario declarados idénticos y avisa otros calendarios sin
convertirlos. Cero coincidencias no demuestra descanso ni export completo.
Reimportar filas equivalentes no duplica noches. Filas distintas para una
misma noche dentro del archivo se rechazan; conflictos con sueño ya guardado
requieren confirmar conservar o reemplazar, con versión previa archivada.
Cambiar una declaración de una noche ya guardada se rechaza, no reinterpreta
datos. El token caduca en 15 minutos y se invalida al cambiar archivo,
declaraciones, perfil o datos de sueño/actividades asociados.

`garmin_sleep_data` permanece privado, separado de diarios/check-ins,
actividades, modelos, planes y snapshots; solo el guardado confirmado escribe
ese bloque. La API de vista devuelve cobertura y contexto de hasta las últimas
31 noches por calendario/procedencia, no CSV, horas de acostarse/despertar,
metadatos HRV, campos fuente adicionales o archivo de versiones.
HRV Status no se interpreta como RMSSD/ms/valor nocturno o promedio de siete
días: metadatos opcionales se dejan todos vacíos si son desconocidos; aportarlos
no activa baseline ni inferencia. Sueño/reposo son contexto, no inputs diarios
completos. Score, Sleep Need y Body Battery no miden recuperación funcional,
ni este archivo estima eficacia o retorno del plan.

Validación focalizada: `python -m unittest tests.test_garmin_sleep
tests.test_garmin_activities -q` y
`node --test tests\sleep-upload.test.cjs tests\personal-evidence.test.cjs`.

### Archivo de actividades Garmin en Mi objetivo

En **Mi objetivo** (`#goal`), selecciona el CSV Activities, declara las unidades
Distance (km/millas en carrera/caminata), Time (h:mm:ss o m:ss, con fracciones
de segundo opcionales), HR (bpm), zona de las fechas y procedencia. Valida y
previsualiza; después confirma el guardado bajo el perfil seleccionado. No se
importan adjuntos automáticamente ni se conecta una cuenta Garmin.

Cabeceras únicas obligatorias: `Activity Type,Date,Time`; Date debe ser
`AAAA-MM-DD HH:MM:SS`. Se admiten UTF-8/BOM, hasta 1,5 MB y 10.000 filas,
comas de miles entre comillas, faltantes vacíos/`--` y el signo/apóstrofo
de `Body Battery Drain`. Los títulos con comillas propias del exportador
no se utilizan ni guardan; se validan el número de columnas y los campos
analizados. UTC, offsets verificados ±HH:MM o zonas IANA disponibles localmente;
no se infieren unidades, ubicación ni cambios de horario.

Las sesiones quedan separadas en `garmin_data`, dentro del estado local privado.
No reemplazan registros diarios, planes, check-ins o predicciones. La huella de
todos los campos de cada fila, normalizados solo en espacios externos, evita
reimportaciones idénticas; sin ID Garmin no puede distinguir dos sesiones
idénticas ni reconocer una fila editada como la misma actividad. Declaraciones
diferentes para una huella ya guardada se rechazan, nunca se sobrescriben.

Los cuatro resultados son **descriptivos**: ritmo de Running con tiempo/distancia
positivos, constancia/series/repeticiones de fuerza, frecuencia cardíaca media
por sesión como contexto y minutos registrados como volumen. No representan
mejora comprobada en 5000 m, kg/% de músculo, recuperación IMVC ni lesiones
evitadas. Los gráficos son semanas registradas (hasta las últimas 52); las
ventanas comparadas terminan en la última fecha del archivo. No se mezclan
procedencias o calendarios; huecos y datos faltantes no son descanso.
La API devuelve agregados del perfil, no CSV, títulos o sesiones individuales;
no hay envío externo. No alimenta modelos o recomendaciones de dosis.

Validación: `python -m unittest discover -s tests -p test_garmin_activities.py`
y `node --test tests\garmin-upload.test.cjs`.

### Mi objetivo: datos, resultados, plan y proyección

**HRV CSV** admite `Date,Overnight HRV,Baseline,7d Avg`, con fechas inglesas
como `Nov 20` y celdas en `ms`. Se declara un año para todas las filas y el
calendario del export; archivos que crucen años deben separarse por año.
Se guardan la HRV nocturna, media móvil 7d y rango propietario por separado.
`ms` no identifica RMSSD, dispositivo o protocolo. La fecha se conserva como
etiqueta Garmin, sin desplazarla ni crear un instante UTC. Ninguna de estas
series activa un baseline, readiness, entrada normalizada o modelo.

**Ritmo CSV** admite el export de dos cabeceras: `Average Pace`, luego
`,Value,Pace`, y filas `YYYY-MM-01,6.10,6:06 /km`. Son períodos mensuales,
no sesiones del día 1. `Value` decimal y `Pace` redondeado deben concordar
con tolerancia de redondeo de 0,8 s/km; se muestra la precisión del texto,
sin transformarla en una marca de carrera. El gráfico usa meses disponibles
(máximo 60 en la vista), separado de la ventana diaria de 30 días;
el mes actual puede ser parcial y la cobertura/ponderación Garmin es desconocida.

Ambos usan selección → validación/previsualización → confirmación privada
por perfil. Token de 15 minutos ligado a archivo/declaraciones/perfil/estado
Garmin asociado; reimportaciones equivalentes deduplican. Conflictos necesitan
confirmación para conservar o reemplazar con historial privado. Actividades,
sueño, check-ins, planes y capturas de modelos no se reescriben.

Los botones **Cargar datos demo** y **Cargar datos del dataset** cambian sólo
la fuente de visualización en Mi objetivo, Panel y Plan adaptativo.
Demo es un ejemplo ficticio y de sólo lectura, con valores/dosis supuestos;
no usa modelos para pronosticar beneficios. Dataset abre agregados congelados
reservados de los estudios usados al desarrollar los modelos, con observado/
estimado, errores y comparadores; no carga individuos ni filas de entrenamiento
en el perfil. **Mis datos** vuelve al almacenamiento privado del atleta.

**Mi objetivo** reúne una sola pantalla Precision Blue, en este orden:
**Tus datos** (CSV Activities/Sleep/HRV/ritmo, otros formatos y objetivo en detalles),
**Evaluación de los resultados** (cuatro tarjetas), **Propuesta · próximos
7 días**, **Entrenamiento previsto** y **Proyección de resultados**. El Panel muestra los mismos valores en gráficos
explicativos, con fechas, fuente y unidades. Formularios, metodología y fuentes
permanecen plegados; la conexión oficial Garmin está inactiva y marcada futura.
Las tarjetas muestran **Ritmo registrado** (promedios mensuales disponibles),
**Entrenamiento de fuerza** (sesiones/series exportadas), **Sueño y HRV**
(duración y HRV nocturna, en escalas separadas) y **Seguimiento de carga**
(minutos/actividades/km registrados, no carga sRPE sin RPE).
Son mediciones/contexto exportados, no resultados musculares, riesgo de lesión
ni beneficios atribuidos al entrenamiento. No se rellena un campo ausente con
cero ni se grafica una noche faltante como observada.
Garmin ofrece contexto de ritmo/constancia/HR/volumen, no resultados oficiales
de5000m, biopsias, IMVC o las escalas originales del clasificador. Cuando esos
inputs no existen, se explica el requisito concreto; nunca se interpreta su
ausencia como «no hubo mejora».

La ventana de actividades/sueño/HRV incluye `hoy − 29 días` hasta `hoy`, sobre las fechas
personales, sin usar como ancla la última actividad Garmin. Un par comparado debe
tener ambas mediciones dentro de la ventana; se muestran fechas disponibles si
hay menos historia. Una sola medida se conserva sin gráfico de evolución ni
conclusión de mejora. Las fechas futuras y resultados anteriores a la ventana
no se desplazan para llenar tarjetas.

La dirección favorable/desfavorable/sin cambio se aplica solo a mediciones
propias comparables bajo contratos existentes. Los pares de pruebas
estandarizadas conservan las fechas de las dos mediciones elegibles y la
comparabilidad declarada de distancia/protocolo/dispositivo/terreno/esfuerzo;
no se convierten en carreras NRCD. Las capturas anteriores usan sus entradas
inmutables, contrato/unidad/horizonte fuente y primera observación emparejada,
no reconstrucciones del CSV actual. Direcciones numéricas no implican
significación, relevancia clínica ni causalidad.

**Laboratorio / investigación** conserva cambios observados y
estimados, soporte por personas/pares, errores, comparadores y hallazgos
desfavorables congelados. Los gráficos de cohortes no son tu serie temporal.
No se entrena ni se adquieren datos al abrir estas vistas.

El área **Fuerza y progreso muscular** separa actividad registrada, fuerza
medida y medición muscular. Los CSV Garmin actuales muestran sesiones/series,
no un porcentaje de fuerza ganada: falta un par de pruebas con el mismo
ejercicio, repeticiones, técnica y protocolo. Epley y cambios de volumen no
sustituyen esas pruebas. El dataset conserva el porcentaje auditado de
**cambio del área de fibras** en30personas a6semanas: media de los cambios
relativos de cada persona, con disminuciones incluidas, observado/estimado
y comparadores visibles; no progreso personal ni fuerza ganada. El modelo
DXA sigue experimental/no promovido y estima masa libre de grasa, no fuerza.
Constancia/cumplimiento requiere un plan previo versionado y sesiones vinculadas;
una ausencia en el CSV no equivale a incumplimiento.

Las cuatro tarjetas diferencian título, icono, color y unidades. La comparación
anterior → actual usa los dos meses de ritmo exportados, dos ventanas explícitas
de7d para sesiones de fuerza/minutos registrados y las dos últimas noches con
valores de sueño/HRV (en escalas separadas). Son diferencias descriptivas,
con fechas y soporte, no efectos del plan; las ventanas de actividades pueden
ser parciales. Si falta una ventana, hay calendarios de sueño ambiguos o falta
duración de una actividad, no se reemplaza por cero ni se calcula su diferencia.
No se combinan las cuatro áreas en un porcentaje global.

La sección **Entrenamiento previsto** muestra sólo
la ejecución computable: bloques, límite de minutos y gráfico por fecha.
La organización CSV no inventa UA porque no dispone de RPE. Son metas de
ejecución, no pronósticos fisiológicos: **el beneficio de
adherirse al plan no es estimable con los modelos actuales**. Pronósticos
experimentales compatibles ya guardados se conservan únicamente en detalles,
con fecha/captura, sin presentarlos como efecto de ejecutar el plan ni metas
como resultado futuro. Un punto a seis semanas no se interpola a una semana/mes.
La propuesta CSV se calcula automáticamente, sin entrada manual de sesiones,
con `athleteos/weekly_organization.py`, versión `garmin-week-organization-v1`.
Es organización conservadora provisional, no una política aprendida o
clínicamente validada. Usa exclusivamente sesiones reales declaradas del
calendario del perfil y tipos con duración conocida, nunca HR/TE como RPE.

Requiere última sesión a máximo3d, al menos8 sesiones/6 fechas y14d de extensión
en21d: cortes operativos locales, no umbrales científicos validados.
Por tipo, frecuencia máxima = mínimo entre conteo7d y mediana de3 ventanas7d;
minutos máximos por bloque = mediana21d redondeada hacia abajo y limitada por
minutos registrados7d/frecuencia. La suma nunca supera minutos registrados7d.
Se organizan bloques de fuerza en fechas no consecutivas, sin asumir músculos,
ejercicios/kg/series/RIR o48h exactas entre sesiones. No se aumenta intensidad.
Sueño reciente ausente o bajo el corte existente provisional6h reserva primero
una revisión; los huecos restantes son revisión sin dosis, no descanso observado.
HRV nocturna/media7d/rango propietario se mantienen contextuales: no ajustan
dosis sin protocolo verificado. Walsh, Foster, Buchheit, Saw, IUSCA e
Impellizzeri orientan registro/cautela; **no validan estas fórmulas/cortes**.
Datos antiguos/insuficientes producen abstención explícita, no fechas movidas.

La aceptación guarda una versión privada separada en `garmin_week_plans`,
ligada a perfil/fecha/digest de los registros. No sobrescribe `athlete.plan`,
check-ins, CSV ni capturas; cambios reales posteriores requieren revisar la
nueva propuesta. Reimportar valores equivalentes no cambia ese digest.
Sin RPE, la organización no se transforma en una sesión del motor diario con
RPE ficticio: intensidad y adaptación interna diaria siguen no estimables.

### Medición elegida y proyección de resultados

El propósito es utilizar IA y evidencia científica para estimar resultados,
apoyar decisiones de entrenamiento y evaluar su beneficio prospectivamente:
**Estimar → Apoyar decisiones → Medir resultados**. Es el objetivo del proyecto,
combinando evidencia científica y modelos entrenados con datos deportivos,
no una afirmación de beneficio personal ya demostrado. En la pantalla se distingue la
organización actual por reglas del registro de predicciones compatibles anteriores
al outcome y su comparación posterior; registrar el circuito no lo valida
prospectivamente ni convierte al modelo en selector del plan.

La página de Pequeños logros está oculta temporalmente: `#wins` redirige a
Hoy, conservando perfil y datos. Sus registros, reglas y APIs siguen intactos.
**Laboratorio** muestra evaluación de modelos con datos de estudios y errores;
**Demostración** usa escenarios ficticios para explorar la interfaz, no resultados
personales ni prueba de eficacia. Las cifras no disponibles permanecen sin curva,
con una nota breve de validación pendiente; la orientación científica del plan
no se presenta como garantía individual.

Mi objetivo sigue tres bloques: **01 · Tus resultados**, con cuatro indicadores
registrados y comparaciones fechadas; **02 · Tu entrenamiento**, con los siete
días de la versión vigente; **03 · Tu proyección**, separando la meta guardada
de las salidas compatibles del modelo. La ilustración del objetivo no es una
curva de mejora ni fija ocho semanas cuando el modelo no admite ese horizonte.
03 muestra únicamente pronósticos personales compatibles, con Actual → Estimado,
cambio, unidad, fecha y horizonte. No se muestran tarjetas vacías; los requisitos
por área quedan en «Datos para una estimación personal». Los beneficios
esperados cualitativos no se convierten en porcentajes ni resultados calculados.
En **Mi objetivo → Mis datos**, directamente debajo de 03 se muestran
**Resultados de referencia: modelos y estudios**, con cuatro tarjetas cuantificadas
cargadas automáticamente, sin cambiar la fuente ni sustituir los datos personales.
El selector **Dataset** conserva la vista independiente de esas mismas tarjetas.
La vista muestra ambas categorías F/M de 5000 m, área de fibras a seis semanas,
IMVC relativa de 24 a 48 horas y conteos de detección de etiquetas de lesión.
Las fuentes, unidades y errores frente a comparadores permanecen visibles;
esas referencias no se presentan como respuesta personal a cumplir un plan.
Los archivos y el editor siguen disponibles en «Datos, archivos y objetivo».

«Ver día» y «¡Empieza hoy!» abren **Plan adaptativo** sobre la misma fuente,
fecha y versión, sin aceptar ni guardar sesiones. Cada día detalla su dosis
original, el motivo de inclusión, un beneficio esperado **cualitativo** y cómo
seguir la respuesta. La política CSV organiza tiempo y tipos, no ejercicios ni
intensidades desconocidas; los días de revisión y los huecos permanecen distintos
del descanso explícito. La aceptación por versión y el editor opcional se
conservan en el resumen plegado. Los colores identifican áreas de seguimiento,
no porcentajes de eficacia.

`GET /api/athletes/{id}` incluye `outcome_forecasts` (`outcome-selection-v1`),
sin escribir plan, CSV ni snapshots. Separa `observed`, pronóstico factual
`forecast` y `planned_exposure`; este último sólo contiene fechas/límites
de tiempo de la versión aceptada o propuesta existente.

Se elige tiempo de **5000 m comparable** para rendimiento; **cambio de fuerza
en la misma prueba** con baseline positivo para fuerza; **duración de sueño**
como indicador autónomo (HRV nocturna separado, no función muscular) para
seguimiento; y **probabilidad de un evento de lesión definido** únicamente
si existe modelo compatible/calibrado. Fuerza admite ahora pruebas comparables
reales, pero no tiene modelo validado: sesiones, Epley, DXA y área de fibras no
sustituyen ese outcome.

La organización `garmin-week-organization-v1` usa tipo/fecha/frecuencia/duración
de actividades y sueño reciente para revisar el día inicial. No usa ritmo
mensual, resultados previstos, HRV/7d Avg/rango Garmin o clasificación Runners
para decidir dosis. El corte de sueño y minutos de bloque son reglas operativas,
no dosis/umbrales validados por los papers. Las fuentes y entradas por área
son visibles en los detalles de **Proyección de resultados**.

Los cinco meses de ritmo no son pruebas de5000m; las sesiones no son cambios
de fuerza. Hay sueño registrado, pero no modelo autónomo validado temporalmente:
27 noches de un atleta no se convierten en27 personas ni se usan promedios móviles
futuros como entradas. Haun3RM no resuelve unidad/protocolo/outcome posterior
compatibles, y DXA/fibras permanecen investigación de sus targets originales.
Runners no aporta probabilidad clínica personal calibrada. No se hacen nuevos
fits sólo para llenar curvas.

Si el adaptador existente de5000m ya valida origen/población/protocolo,
fecha y rango, se conserva su salida factual experimental con baseline,
horizonte, fuente y errores/comparador. No controla entrenamiento, no tiene
intervalo individual validado y **no estima el efecto de cumplir el plan**.
Si su error no mejora repetir el resultado previo, la salida queda en detalles
de investigación y no se promueve a una gráfica principal.
Entradas fuera de rango, sintéticas o sin baseline mantienen abstención;
un contrato inconsistente produce error explícito, no un simulador sustituto.

### Registro de fuerza comparable y revisión prospectiva

En **Centro de datos**, la sección plegada de pruebas de fuerza importa
mediciones ya realizadas de carga 3RM (kg) o fuerza isométrica instrumental (N).
Exige ejercicio/equipo/procedimiento/calendario explícitos y procedencia por fila.
No indica realizar pruebas máximas ni calcula fuerza a partir de Garmin.
La misma tarjeta de fuerza muestra el par comparable, unidad, fechas y cambio
con signo; sin ese par conserva sólo la actividad disponible. No añade paneles
técnicos a la portada ni produce pronósticos.

`strength-tests-import` conserva datos privados por protocolo, con guardado
atómico, duplicados exactos y conflictos rechazados sin sobreescribir.
`strength-assessment` conserva baseline/corte antes de una revisión futura
ya planificada y vincula el primer resultado importado del mismo protocolo/fecha.
Una copia de la organización aceptada conserva límites/versión/cobertura,
no dosis realizadas ni adherencia; no se repite una semana para llenar el horizonte.
Todos los campos de pronóstico/error siguen `null`. Esta ruta cierra la brecha
de adquisición y temporalidad personal, **no valida un modelo de respuesta**.

Contrato y límites: [pruebas de fuerza](docs/strength-observations-schema.md);
API `GET /api/athletes/{id}` devuelve `strength_observations` sin CSV/source_ref.
`/strength-template.csv` descarga sólo la cabecera, sin registros fabricados.

El editor original permanece opcional, plegado, no como requisito de generación.
No se repite, aumenta ni guarda una semana automáticamente. **El beneficio
no es estimable con los modelos actuales**: falta un modelo de intervención–
respuesta validado y compatible con estas entradas, no una fórmula extra de presentación. Las sugerencias mantienen
las reglas provisionales actuales y sus fuentes; no usan Garmin como RPE
ni recomiendan biopsias/inmersión, zonas por HR medio o +10% automático.

### Modelo experimental de respuesta a seis semanas

Se entrenó `haun-dxa-dose-response-v1` con **31 pares reales PRE/W6**:
masa libre de grasa/hueso por DXA (kg) y seis volúmenes semanales realizados.
Los suplementos SDC1/SDC2 de Haun2018 se adquirieron explícitamente bajo
CC BY4.0 (28.962/11.438 bytes), con SHA256/MD5 verificados. Son la misma
cohorte de la investigación anterior:30 participantes compartidos, no otra
validación externa. Los originales y pesos permanecen en `.research-data`.

El protocolo `research_data\training_response_protocol_v1.json` y la
partición por personas se congelaron **antes de ajustar**:21 development,
10 reservados; selección de alpha sólo por LOO development. Se comparan
ridge baseline-only y baseline+dosis con persistencia, constante y cambio
medio del development. Error reservado MAE: **1,2085kg con dosis vs1,2317kg
sin dosis**, frente a2,723kg de persistencia y1,2684kg de cambio constante.
La diferencia de0,0232kg es error predictivo, **no23g de músculo ganado**;
no establece importancia clínica, causalidad ni un intervalo personal.

La evaluación utiliza volumen **realizado después de PRE**. Usarlo como
plan futuro supone igual cumplimiento, ejercicios/pesos/repeticiones y
protocolo; eso no se validó prospectivamente. La unidad física del volumen
distribuido aún requiere confirmación: se retienen unidades nativas sin
inventar kg/lb. Tampoco DXA equivale a músculo puro: incluye efectos del agua.
No se promueve sobre Garmin ni se convierte de seis semanas a siete días.
Tus CSV no proporcionan baseline DXA o dosis ejercicio×reps×peso compatible.

`GET /api/training-response-capability` verifica artefactos y separa
pronóstico factual experimental, pronóstico personal del plan **no disponible**
y efecto causal **no identificado**, con brechas concretas para las cuatro
áreas. Si falta/cambia el artefacto devuelve503, nunca una curva sustituta.
No hay endpoint personal de inferencia ni autoguardado de planes/snapshots.
Resultados agregados: `docs\training-response-model-v1.json` y
`docs\training-response-capability-v1.json`. Replay sin fits:

```powershell
python -m research_data.training_response replay
```

El flujo inicial fue `acquire` → `declare` → `train`; se rechaza repetir o
sobrescribir una declaración/fit existente. No se modifican modelos,
métricas reservadas ni datos personales previos.

**Qué datos necesito aportar** distingue Garmin (sueño diario, índice/dispositivo/
protocolo de VFC nocturna, pulso en reposo, vueltas), registros manuales
(RPE/fatiga/recuperación con escala; ejercicio/series/reps/kg/RIR) y mediciones
externas comparables (5000m, músculo, función, historial de lesión). Declara el
estado del registro diario propio y la falta de validación intervención–respuesta.
No se pide obtener biopsias. **No hay parser directo FIT/TCX ni vueltas**;
Sleep.csv tiene el importador contextual separado
descrito arriba. Activities conserva todas las sesiones; no se suman RPE
para rellenar el contrato diario de una observación/día.

Las tarjetas identifican **propuesta automática/organización aceptada**; los iconos indican
objetivos, no beneficios. Las sugerencias existentes siguen siendo reglas
provisionales y la orientación de papers no es una política
aprendida por los modelos. Sin evidencia diaria compatible no se prescribe una
semana; fechas sin sesión permanecen pendientes, y planes anteriores no se
reubican. Ver plan completo abre el editor existente con confirmación/versionado.

Validación focalizada: `node --test tests\personal-evidence.test.cjs` y
`python -m unittest discover -s tests -p test_task_models.py`.
Pruebas de navegación y layout con servidor/store desechables:
`npm run test:browser -- tests\personal-layout.spec.cjs`.
El fixture de interfaz sólo comprueba renderizado; no ejecuta inferencia ni
persiste mediciones o planes en el perfil del usuario.

La experiencia diaria abre en **Hoy**, con actividad realmente registrada, y el
Panel reúne los cuatro resultados con requisitos desplegables y proyección
preevento frente a resultado posterior. **Mi atleta** está separado del
**Laboratorio**, cuyo botón ejecuta un ajuste local real con partición fija70/15/15
por personas, sin promover pesos ni reutilizar tests históricos para tuning.
Diseño, contratos causales, resultados agregados y límites:
[experiencia diaria y proyecciones](docs/experiencia-diaria-y-proyecciones.md).

**Resultados con datos reservados**, accesible desde Panel/Laboratorio (`#results`),
compara predicción real, observación y persistencia del ensayo ya entrenado
70/15/15 por personas. Incluye porcentajes efectivos, errores y gráficos agregados
con al menos cinco atletas por grupo, sin exponer observaciones individuales.
Recuperación conserva su evaluación leave-one-person-out; lesiones su resumen
histórico congelado; hipertrofia sigue sin modelo. No se repitió el ajuste:
[informe y límites](docs/resultados-reservados.md).

**Hipertrofia de fibras y plan futuro:** se adquirió una única alternativa
original CC BY4.0 (Haun2019,30personas) y se entrenó un ridge PRE→W6 por persona.
Es área de fibras por **biopsia**, no ecografía ni kilos de músculo:
MAE579,642µm² frente a676,677 de persistencia y532,213 de constante; no supera
la constante. Plan adaptativo conecta metas con sesiones futuras revisables,
sin optimizar dosis a partir de este modelo. [Resultados y decisiones](docs/hipertrofia-y-plan-futuro.md),
[contrato CSV especializado](docs/hipertrofia-fibras-schema.md).

La aplicación existente está en español: navegación, formularios, centro de datos, entrenador determinista, módulos especializados, inventario y los dos escenarios de presentación. Las fechas y números usan `es-ES`; el perfil diario sigue en UTC, mientras las actividades Garmin conservan el calendario declarado y separado de su archivo. `web/es.js` traduce textos completos y plantillas explícitas de presentación, incluidos los mensajes dinámicos del servidor, sin modificar datos guardados, capturas históricas, cálculos ni contratos. Los títulos bibliográficos originales, IDs/versiones de modelos, nombres de campos y cabeceras CSV se conservan; los valores de las opciones enviadas al backend tampoco se traducen.

La interfaz distingue modelos no disponibles, datos insuficientes y entradas incompatibles: traducirla no añade predicciones ni habilita Garmin. Validación focalizada del catálogo, respuestas reales del backend y preservación de contratos: `node --test tests\localization.test.cjs`; comprobación de tipos: `.\node_modules\.bin\tsc.cmd -p jsconfig.json`.

## Real research data (separate from the demo)

The standard-library-only [`research_data`](research_data) CLI acquires reviewed official **CC0 competitive-runner CSVs** and, with explicit `--allow-large`, **CC BY 4.0 PAMAP2**. It prepares source-specific X/y/index tables, subject-disjoint splits, purged temporal runner benchmarks, nullable data and train-only transforms. It never imports sensor streams into the demo CSV or replaces readiness inference.

```powershell
python -m research_data acquire runners
python -m research_data prepare-runners --approach day
python -m research_data prepare-runners --approach week
python -m research_data acquire pamap2 --allow-large
python -m research_data prepare-pamap2
python -m research_data verify .research-data\prepared\runners-day-v1
python -m research_data verify .research-data\prepared\pamap2-protocol-v1
```

All real records, archives and individual outputs stay in ignored **`.research-data\`** (approximately 2.05 GB for the original obtained sources and prepared tables, plus replay runs); do not commit or publish them. Existing prepared runs are never overwritten: choose a new `--output .research-data\prepared\...` to repeat. Acquisition/preparation needs no external Python dependencies or training. Pipeline tests use **synthetic fixtures only**.

See the Spanish acquisition report/data dictionary, actual aggregate counts, licensing, citations, splits, hashes and limits in [`docs/datos-reales-y-preparacion.md`](docs/datos-reales-y-preparacion.md). Manifest: [`research_data/sources.json`](research_data/sources.json). **FitRec remains unacquired** pending academic/noncommercial-use and multi-GB transfer decisions; Garmin is an authorized API, not an open dataset; the hypertrophy review does not provide individual training labels. These disjoint datasets do not supply a validated Daily Coach readiness target.

### Nuevas fuentes compatibles y modelos experimentales

Se adquirieron fuentes originales **CC BY4.0**: NRCDv2.1.0(143.868resultados/31.786IDs;2003–2026), Bandiera(22personas/88visitas funcionales;pre/24/48/72h) y Baz-Valle/Balsalobre(8semanas;cohorte/columnas con discrepancias). El inventario pasa a **cinco fuentes**, conservando corredores diario/semanal como una sola cohorte.

Protocolo previo fijo, datos reales y particiones por persona: dos ridge5000m por categoría fuenteF/M y uno de función IMVC relativa a48h. MAE modelo/persistencia: **44,718/35,394sF;27,992/26,369sM;5,207/5,148ppIMVC**. Ninguno supera la última medición. Los tres se guardaron/recargaron y su replay es idéntico; no se siguió afinando ni se volvió a puntuar el test antiguo.

La app española incorpora un **CSV específico de carreras de5000m**, separado de actividades y pruebas estandarizadas, con origen, autorización, protocolo/población, fechas y rango observados. Solo produce estimación experimental cuando cumple el contrato y el artefacto íntegro existe; muestra también persistencia y limitaciones. Sintéticos nunca ejecutan el modelo. Recuperación personal sigue bloqueada hasta verificar métodos/unidades; hipertrofia no se entrena con su diccionario/cohorte ambiguos; lesión mantiene el gate de escala. No modifica recomendaciones de dosis.

Informe: [modelos y datos compatibles](docs/modelos-y-datos-compatibles.md). [Inventario agregado actual](docs/inventario-datos-compatibles.json), [contrato personal5000m](docs/carreras-5000m-schema.md), [protocolo previo](research_data/compatible_protocol_v1.json). Pesos/originales/OOF individuales privados en `.research-data\models\compatible-outcomes-v1\` y `.research-data\raw\`; no se sirven ni publican.

```powershell
python -m research_data.compatible_training replay
$env:PYTHONPATH='tests'
python -m unittest test_compatible_sources test_compatible_training test_race_models -q
```

### First local activity-classification model

The separate [`research_data.training`](research_data/training.py) CLI genuinely fits a **Gaussian Naive Bayes** baseline to the existing PAMAP2 Protocol windows. It uses **Python 3.11+ standard library only**, so there is no research dependency installation or impact on demo setup. The user selected this baseline after official scikit-learn package downloads failed TLS verification/negotiation; no TLS or sandbox workaround was used.

```powershell
python -m research_data.training train
python -m research_data.training evaluate
python -m research_data.training sample-input --output .research-data\models\pamap2-gnb-v1\example-input.json
python -m research_data.training infer --input .research-data\models\pamap2-gnb-v1\example-input.json --output .research-data\models\pamap2-gnb-v1\example-prediction.json
python -m unittest discover -s tests -p test_training.py -v
```

Model/manifest/evaluation are retained in ignored **`.research-data\models\pamap2-gnb-v1\`**; the commands have already run locally. Training and inference refuse to overwrite existing outputs: use a new training `--output` and matching `--model` for evaluation/inference, or new example/prediction filenames. The artifact is validated JSON, **not executable pickle/joblib**; only use your own local model and manifest. Input requires the exact 120 raw window features with explicit coverage/units, not demo CSV or Garmin summaries.

Median imputation, scaling, class statistics and priors use training only; two smoothing candidates are compared on validation. The 5/2/2 participant split is unchanged and the model is frozen before separate held-out evaluation. Actual test result: **accuracy 0.581349, macro-F1 0.528234, balanced accuracy 0.584406** on 504 windows, versus most-frequent accuracy 0.093254. **Sitting is never predicted and Nordic walking recall is only 0.05**: this is an exploratory baseline, not a production or readiness model. Full Spanish results, per-class support, confusion matrix, hashes, reproduction commands and limitations: [`docs/primer-modelo-pamap2.md`](docs/primer-modelo-pamap2.md).

### Experimental runner source-label model

[`research_data.runners_training`](research_data/runners_training.py) fits a separate **L2 logistic regression**, implemented with the Python standard library: no new package installation, GPU or cloud. Its task is a **retrospective benchmark of the dataset's binary `injury` event-day label**, not a clinical injury forecast. The corrected official README defines daily predictors as **t-7 through t-1** (base column is oldest, `.6` is the preceding day). The exact clinical definition, onset/recording delay, censoring and return-to-training policy remain unknown. Weekly and daily files overlap and are **not combined**.

```powershell
python -m research_data.runners_training train
python -m research_data.runners_training evaluate
python -m research_data.runners_training sample-input --output .research-data\models\runners-day-logistic-v1\example-input.json
python -m research_data.runners_training infer --input .research-data\models\runners-day-logistic-v1\example-input.json --output .research-data\models\runners-day-logistic-v1\example-prediction.json
python -m unittest discover -s tests -p test_runners_training.py -v
```

Artifacts, frozen configuration and evaluation stay in ignored **`.research-data\models\runners-day-logistic-v1\`**. Existing outputs cannot be overwritten: repeat with a new `train --output`, then the corresponding `evaluate/infer --model`. Model JSON and its local manifest are integrity-checked; use only your own trusted artifacts. No pickle/joblib is loaded.

The exact **70 raw daily source features** become 140 inputs after train-only median imputation, scaling and explicit missing masks. IDs, labels, dates, split metadata and event-day values are excluded. The inherited 44/15/15-person grouped split and separate seven-day-purged temporal protocol remain unchanged; each has its own model. Two L2 settings are selected by validation average precision; the threshold grid is selected by validation F1, before the held-out test. Scores are **uncalibrated**. Rare-event results, all-negative comparator, confusion matrices, exact protocol and limitations are in [`docs/primer-modelo-corredores.md`](docs/primer-modelo-corredores.md). No model is connected to Daily Coach readiness; arbitrary demo/Garmin data do not satisfy this source-specific input contract.

The commands were actually executed locally. Held-out grouped test: **AP 0.017604 vs comparator 0.014223, ROC-AUC 0.584473**; at the frozen validation threshold 0.02, **52/150 positives detected with 2,765 false positives** (precision 1.85%). This weak result is not deployable clinical prediction. The secondary temporal test permits recurring people and is reported separately, including its zero alerts at threshold 0.5. Shareable aggregate figure: [`docs/resultados-corredores.svg`](docs/resultados-corredores.svg).

### Development-only comparisons v2 and measured performance outcomes

`python -m research_data.benchmark run` fits a predeclared, bounded **three-fold participant-grouped comparison using only original train + validation**. Existing outputs are protected: use a new `--output .research-data\models\...` to repeat. The historical tests have already been observed and are **not scored again**. `python -m research_data.benchmark replay` validates saved model/code/data hashes and reproduces development metrics; it is not fresh independent validation.

Actual development macro-F1: PAMAP2 base **0.655944**, dynamic/uniform **0.686645**; runner AP base **0.030716**, weekly-summary alternative **0.027924** (no improvement). All recipes, folds, participant variation, class failures and alert tradeoffs are reported, not just favorable results. See the [Spanish report](docs/mejora-modelos-y-rendimiento.md), [frozen protocol](research_data/benchmark_protocol_v2.json), [aggregate metrics](docs/resultados-desarrollo-v2.json), and [shareable aggregate figure](docs/resultados-desarrollo-v2.svg). New external confirmation remains pending; neither classifier establishes physiological improvement or prevention efficacy.

The independent `research_data.performance` CLI supports **measured time/pace in a standardized comparable run**, not injury or muscle forecasts. PAMAP2/runner-injury schemas do not supply this target. It imports an explicitly authorized real outcome CSV, validates causal timestamps/comparable prior tests, reports eligibility, and refuses synthetic/insufficient training. Fitting under this **standardized-test contract** has not occurred; the newly fitted NRCD race models above use a separate, explicit race contract and never fabricate standardized-test fields. Follow the [outcome schema/authorization contract](docs/performance-schema.md); [sample CSV](samples/performance-outcomes-synthetic.csv) is conspicuously synthetic and **never eligible for real training**. All real records, authorization manifests and fitted models must remain in ignored `.research-data`.

```powershell
python -m research_data.performance import --source .research-data\performance\incoming\outcomes.csv --manifest .research-data\performance\incoming\authorization.json --output .research-data\performance\authorized-v1
python -m research_data.performance train --imported .research-data\performance\authorized-v1 --output .research-data\models\performance-v1
python -m unittest discover -s tests -p test_benchmark.py -v
python -m unittest discover -s tests -p test_performance.py -v
```

These performance import/train commands do not implicitly download another dataset. **FitRec is still not downloaded**: its official metadata permits academic/noncommercial use only, prohibits redistribution, and describes multi-GB files; prospective test comparability still needs auditing. An optional isolated research dependency manifest is provided (`research_data\requirements.txt`), but normal package download failed TLS negotiation in this run. Both new CLIs run with the Python standard library; AthleteOS app setup and inference remain unchanged.

### Literature-informed real runner training

The separate [`research_data.literature_training`](research_data/literature_training.py) experiment connects the actual runner source columns to explicitly reviewed papers: raw70 logistic control versus raw70 plus21 predeclared exposure/variability/subjective-change descriptors. See the [Spanish evidence-to-feature/training report](docs/entrenamiento-informado-por-evidencia.md), [fixed protocol](research_data/literature_protocol_v1.json) and [bibliography/access scope](research_data/literature_sources_v1.json). Papers inform feature hypotheses and methodological safeguards; they are not labels, fixed physiological coefficients or proof of clinical benefit. No missing duration, sRPE/ACWR, HRV, sleep or measured muscle outcome is fabricated.

```powershell
python -m research_data.literature_training replay
# Existing artifacts are protected; repetition needs a new ignored directory:
python -m research_data.literature_training run --model .research-data\models\runners-literature-repeat-01
python -m unittest tests.test_literature_training -q
```

This reuses the already observed v2 grouped **development** folds; no historical test rescoring or fresh independent validation. All six fitted models/transforms and frozen source/feature/code manifests stay private in `.research-data\models\runners-literature-v1\`. Its inference contract is an exact flat JSON dictionary of70 raw source columns, not demo CSV. It classifies the experimental source injury label, **not measured performance, muscle recovery or personal calibrated risk**, and does not change app recommendations or real-only performance eligibility.

Actually executed: **six real-data fits**, save/reload, source-contract inference and identical replay. Mean development AP: **raw control 0.030716; literature-informed 0.030141**; the variant does **not** improve the predeclared primary metric. At fold-specific calibrated thresholds, false-positive windows increase from3,113 to5,908 while source positives detected increase from85/433 to157/433. See [all aggregate metrics](docs/resultados-entrenamiento-evidencia.json) and [comparison figure](docs/resultados-entrenamiento-evidencia.svg); no clinical/physiological benefit or replacement of the baseline is claimed.

### Synthetic one-week CSV comparison (not model validation)

The downloadable [SYNTHETIC-DEMO week package](samples/demo-semana/README.md) contains **42 app-normalized daily rows** (35 prior + 7 follow-up), a **separate five-test performance CSV**, an explicitly synthetic inspection manifest and calculated comparison JSON. The prescribed 5 km example changes **25:00 → 24:30 (−2% elapsed time)**; subjective soreness/fatigue also change by design, not by learned prediction. HRV/HR remain missing. This tests schema/import/calculations, **not training accuracy, measured muscle recovery or efficacy**. Neither existing source-specific classifier accepts these CSVs, and real performance fitting still rejects synthetics.

```powershell
python -m research_data.demo_week compare --input samples\demo-semana
# Refresh only an isolated new package, using the actual completed UTC date:
python -m research_data.demo_week generate --output samples\demo-semana-new
python -m unittest discover -s tests -p test_demo_week.py -v
```

The generator never opens saved app state or trains/changes a model. Do not import over existing data: use a **new state file** and empty `demo-new` athlete as explained in the package. App CSV and research outcome CSV are different contracts; preserve their synthetic filenames/provenance, since the current app import label is only `CSV import`. Synthetic research inspection succeeds with **zero real eligible records**; training must remain blocked without a model artifact.

## Run

### Personal CSV and separate specialized task adapters

Dashboard now separates **running performance, experimental source injury label, functional recovery and hypertrophy**, including explicit missing-model/incompatible-input states, required contracts and the selected athlete's record counts/date coverage/origins. This does **not** invent four trained predictors: current readiness/dose heuristics are unchanged and never consume specialized scores. Garmin remains unconnected; CSV is the implemented input path.

Data studio retains validated daily CSV import and adds a **separate comparable-test CSV + authorization JSON** using the existing performance research validators. It preserves only the selected person's tests locally, rejects foreign subjects/future or invalid rows atomically, distinguishes synthetic from declared real data, and shows observed comparisons, not forecasts. The runner model's exact70 source scales have no verified mapping from personal RPE/recovery, so its score is **not** computed for app records even when declared real. No study identities are fused with the user.

Original two-cohort inventory (preserved within the new five-source snapshot): PAMAP2 Protocol **9 people /2,872,533 raw samples /3,833 five-second windows**, exact summed raw timestamp spans **7h58m45.24s**, useful prepared windows **5h19m25s**. Runners daily **42,766 event windows /74 people**, weekly **42,798 windows of the same cohort**; relative dates0..2673days, per-person span min/median/max42/800/2652days with gaps, not seven complete years each. Dataset/representation/split units must not be added as independent data.

See [architecture, workflow, full count/split/time table and limitations](docs/datos-personales-y-modelos.md), [current aggregate snapshot](docs/inventario-datos-compatibles.json), [new source/model audit](docs/modelos-y-datos-compatibles.md), and [standardized-test schema](docs/performance-schema.md). Recovery and hypertrophy files are now acquired and audited: recovery has a source-only relative-function baseline with a personal protocol gate; hypertrophy remains untrained pending dictionary/cohort reconciliation. Models and sensitive records remain server-side/local; the frontend receives no weights or performance authorization manifests.

Requires **Python 3.11+**. No Python dependencies or cloud credentials.

```powershell
python -m athleteos.server
```

Open **http://127.0.0.1:8000**. Run from the repository root. Alternate port/store:

```powershell
python -m athleteos.server --port 8001 --data .athleteos\another-demo.json
```

### Presentation demo: complete synthetic data without resetting your athlete

Choose **Presentation demo** in the header/navigation, or open **http://127.0.0.1:8000/?presentation=build#presentation**. Switch **Build scenario / Recovery scenario**, then **Exit presentation** to return to your selected saved athlete. The scenario query survives reload; these what-if interactions are **transient, read-only**, not saved check-ins or accepted adjustments.

**Proyecciones y plan de 7 días** remains the isolated presentation layout; personal Goal/Panel/Plan now use the measured CSV and automatic-organization workflow described above. The presentation retains four compact Precision Blue cards, real UTC date controls, seven original scheduled sessions, objective highlighting and a deterministic plan note. Missing dates say “Sin plan definido”, not rest; browsing or highlighting never accepts an adjusted dose. Personal model details use declared compatible observations and saved pre-outcome snapshots, not reserved study groups or demo values. Predictions are dated endpoints, not invented future trajectories; chosen goals remain distinct and no confidence bands are fabricated. Recovery has no personal IMVC inference contract, and load review never displays a clinical injury percentage. Synthetic mode instead shows explicitly assumed 5 km references, only the existing three readiness check-ins, planned strength volume in kg-repetitions and original planned load. The existing versioned editor remains optional; demonstrations retain read-only scenario details. Original evaluations, source inputs and comparators remain folded below.

`GET /api/presentation?scenario=build|recovery` generates a separate deterministic 35-day synthetic fixture and seven-day plan relative to **today in UTC**. It never reads/writes the saved athlete store, overwrites edits, extends normal plans or reseeds normal histories. Declared synthetic device/protocol metadata and complete baseline coverage allow existing features and `demo-rules-v3` / `demo-heuristic-v3` to be demonstrated honestly. Invalid scenarios fail explicitly; fixture athlete IDs cannot be used for saved-athlete mutations. UTC and local dates can differ.

The presentation shows goal/target, current calculated load and heuristic readiness, future planned dose, **assumed** pace/5 km time examples, hypothetical check-ins, planned direct sets/volume, and the existing evidence-informed overload review. Each future pace card/chart is labelled **“Simulated scenario — not a trained forecast”**. Pace = synthetic reference pace × stated scenario factor; illustrative time = pace × 5 km; assumed distance = planned duration / pace. These choices are assumptions, not learned coefficients or demonstrated improvement. Future recovery scores use only four explicitly assumed subjective inputs; no future HRV or measured recovery is fabricated. Strength volume is **kg-repetitions**, not kilograms of muscle gained; no mass-gain prediction or injury probability is supplied.

Separate **Evaluated** cards read a reviewed public aggregate contract (`athleteos/model_evaluations.json`), with actual frozen PAMAP2/runner tasks, dates, splits, metrics and material failures. These are not predictions for the synthetic athlete. The API exposes neither private datasets nor trained artifacts; local `/reports/pamap2` and `/reports/runners` serve only aggregate public reports. Actual model training is demonstrated by reproducible reports/evaluation, **not by the aesthetics or favorable assumptions of this demo**.

No trained model currently predicts the four physiological goals. Statistical activity/source-label classification does not establish performance improvement, injury prevention, muscle recovery or hypertrophy. Papers support monitoring/methods, not our exact provisional cuts, simulated trajectories or intervention efficacy.

Focused synthetic/isolation checks:

```powershell
python -m unittest discover -s tests -p test_presentation.py -v
```

The backend and frontend share one origin; no separate frontend development server is needed. The JavaScript/CSS are served directly without bundling. Ctrl+C stops the server.

### Try the connected demo

1. Select **Alex Rivera** for BUILD or **Sam Chen** for PROTECT. Their 35-day UTC synthetic datasets are created only on first startup.
2. Update Goal or edit a session in Adaptive plan. Submit a recovery check-in to recalculate readiness and the daily recommendation.
3. For Sam, accept the recovery adjustment. This earns a rule-verified Smart Training win. Log actual duration/RPE within the reduced dose to earn Recovery Win. Logging explicitly replaces today's uncompleted synthetic activity; no distance is inferred.
4. Visit Dashboard for calculations and data-quality notes, and AI Coach for bounded explanations of the current results.
5. Data studio can export the normalized dataset or validate/import CSV. **Your demo athlete** begins without observations to demonstrate honest missing-history behavior. To import an Alex export there, change every `athlete_id` to `demo-new`.

The selected athlete is preserved in the URL (`?athlete=demo-sam`) across reloads; no browser storage of health data is used.

Changes are stored in **`.athleteos\state.json`**, excluded from Git, using a lock, candidate-state validation, file flush/fsync and atomic replacement. A failed save is an error, not a success. Restarting does not reseed data or overwrite edits. Invalid/corrupt storage fails explicitly rather than resetting. Back up that file for a durable copy. A new `--data` path starts a separate demo. Plans are not silently extended as dates advance.

**Evidence and traceability:** [`docs/avances-evidencia-cientifica.md`](docs/avances-evidencia-cientifica.md) documents the implemented advances in Spanish, the evidence matrix, source populations/protocols and limitations. Dashboard, Adaptive Plan and Coach now share versioned explanations and explicitly provisional cuts. Sources justify monitoring contexts/methods, not every score or prescription.

**Evidence-informed review (15 November 2026):** Today, Dashboard, Adaptive Plan and Coach now share four explicit layers: observed facts with units/coverage/comparability, source-supported monitoring context, provisional criterion, and suggested review/action. The additive `prediction.monitoring_review` identifies coincidence of the **existing** weekly-load-change flag with at least one **existing** recovery flag, versus load-change-only, recovery-only, missing observations or no crossings. Absolute high load alone is not harmful overload; training can produce adaptation. Unknown collection comparability remains unknown, and missing/zero/mismatched baselines do not establish a change. This explanatory criterion does **not** modify readiness/mode/dose arithmetic or introduce injury probabilities. Coach's **Review load and recovery** question uses the same backend facts/criterion/action and scoped references.

The reviewed full-text commentary by Impellizzeri, McCall, Ward, Bornn and Coutts, [*Training Load and Its Role in Injury Prevention, Part 2: Conceptual and Methodologic Pitfalls*](https://pmc.ncbi.nlm.nih.gov/articles/PMC7534938/) (19 September 2020; DOI 10.4085/1062-6050-501-19), is monitoring/causal-inference context, **not validation of any cut or prevention efficacy**. Its [corrigendum](https://pmc.ncbi.nlm.nih.gov/articles/PMC8130765/) was also consulted; registry metadata states the actual sections reviewed. Existing sleep evidence remains abstract-only; no full-text access is fabricated.

Current new decisions use **`demo-rules-v3` / `demo-heuristic-v3`**, with identical numerical thresholds to v2. Existing v2 snapshots retain their embedded original manifests/predictions/recommendations/digests and are not recomputed, invalidated or amended on read. The store remains schema v2; only new snapshots contain the new review/source. Accepting an older saved adjustment still links its original decision. Research classifiers remain separate, not readiness or clinical-risk adapters.

Existing state v1 migrates to v2, first preserving `state.v1-backup.json` next to the original file (never overwriting an existing backup; a different existing backup causes a uniquely suffixed copy of the current v1 file). Legacy logs remain but are marked `legacy-unrecorded`; missing historical decisions are not invented. Valid goal/plan/check-in/import changes, accepted adjustments and actual session logs capture immutable decisions; there is also **Save current decision snapshot**. Dashboard/Plan show summaries and export full inputs, rules, references and linked actual dose outcomes from `/api/athletes/{id}/decisions`. Reading a page does not append history.

The app is an **unauthenticated, single-process local demonstration** bound to loopback. It rejects other Host headers and cross-origin writes. Do not expose it on a network or share real health data; the local JSON is unencrypted. Multi-process writes, accounts, authorization, encryption, production hosting and backup rotation are out of scope.

## Validation

Backend tests need only Python:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Frontend static type checking and browser integration tests require Node.js 20+ and the dev dependencies:

```powershell
npm ci
npm run build
npx playwright install chromium
npm run test:browser
```

An existing Chrome or Edge can be used instead of downloading a test browser:

```powershell
$env:ATHLETEOS_BROWSER_CHANNEL = "msedge" # or "chrome"
npm run test:browser
```

`build` checks the strict JavaScript/JSDoc contracts, Python compilation and JS syntax. There is no generated production bundle. Playwright starts a separate disposable local store/server, exercises the real API-backed browser, tests mobile layout/errors/import/persistence and stops its server. Browser artifacts are ignored. `npm test` runs the Python suite.

## Normalized CSV contract (v1-compatible, optional metadata extension)

Download **Data studio -> CSV sample**, see [`web/sample.csv`](web/sample.csv), or export the full normalized synthetic dataset. CSV must be UTF-8 (optional BOM), with this exact ordered header:

```text
athlete_id,timestamp,timezone,sport_type,duration_min,distance_km,session_rpe,avg_hr_bpm,max_hr_bpm,resting_hr_bpm,hrv_ms,sleep_hours,fatigue,soreness,stress,elevation_m,exercise,muscle_group,sets,reps,load_kg,rir
```

The original header/sample remains accepted. Exports append **`hrv_device,hrv_protocol,resting_hr_device,resting_hr_protocol`**, in that order. Each optional device/protocol pair must be supplied together with its measured value, or both blank; text up to 160 characters. For example `demo-device-A` / `RMSSD; morning; seated; 5 min`. These are manual declarations, not verified device accuracy or a wearable connection.

| Fields | Units / requirements |
|---|---|
| `athlete_id` | Selected ID: `demo-alex`, `demo-sam`, `demo-new`; no cross-athlete import |
| `timestamp`, `timezone` | Offset-aware ISO 8601; demo athletes use `UTC` and `+00:00` or `Z`. No future observation dates. IANA zones are validated when installed, but these profiles require UTC. |
| `sport_type` | `run`, `walk`, `cycle`, `strength`, `rest` |
| `duration_min`, `session_rpe` | Required; 0-1440 minutes, RPE 0-10. Active duration >0; rest has zero duration/RPE/distance. |
| `distance_km`, `elevation_m` | Optional; 0-500 km, 0-20000 m. Only endurance activities contain nonzero distance. |
| `avg_hr_bpm`, `max_hr_bpm`, `resting_hr_bpm` | Optional bpm; exercise 20-240, resting 20-200; avg <= max, max > resting when supplied together. |
| `hrv_ms`, `sleep_hours` | Optional; 0-500 ms, 0-24 hours. Zero HRV baseline does not permit percentage division. |
| `fatigue`, `soreness`, `stress` | Optional self-reported 0-10 scales; higher means more. |
| `exercise`, `muscle_group`, `sets`, `reps`, `load_kg`, `rir` | Strength only; complete exercise + group + sets + reps + kg required. Groups: `legs`, `push`, `pull`, `core`. Integer sets/reps 1-100; weight 0-1000 kg; optional RIR 0-10. |

Blank optional fields mean **missing**, not zero. Numeric strings must be finite and in range. Unknown/missing/reordered headers, duplicate daily dates, wrong column counts, invalid units/ranges, partial strength rows and mismatched athlete/timezone fail with a row-specific message. Entire import is atomic; matching **uncompleted** dates replace records and clear check-ins/pending adaptations for those dates; other dates remain. Completed app observations cannot be overwritten by import.

MVP granularity is **one workout or explicit rest observation per UTC day, and one strength exercise per workout**. Consolidate source exports to this contract first; do not sum RPE across sessions. Multiple workouts/exercises, raw Garmin exports, unit guessing, injury labels, GPS and research dataset downloads are not supported by this application CSV; research acquisition/training use the separate CLI above. The sample's seven dates are fixed in October 2026; use the exported live dataset for relative-to-today histories.

Check-ins alone never fabricate activity/rest dates. A new check-in overwrites today's recovery fields; optional blanks clear the previous value. Activity and recovery provenance are kept separately as Synthetic demo / CSV import / App session log / App check-in.

## Features and demo decision rules

Calculated in [`athleteos/domain.py`](athleteos/domain.py). The current week is today plus the six preceding UTC dates. **All seven explicit days** are required for weekly totals, monotony, strain and weekly muscle sets/volume. An observed partial load is returned separately and never labeled a full weekly load.

| Feature | Formula / units / prerequisites |
|---|---|
| Session sRPE / weekly load | `duration_min * session_rpe`, AU; sum 7 daily loads, AU |
| Monotony / strain | daily mean / **population** SD, dimensionless; weekly load * monotony, AU. Constant loads produce `null`, not infinity or an arbitrary ceiling. |
| Weekly-load change | `(current - baseline) / baseline * 100`, %; baseline is sum of **28 complete days preceding the current week / 4**. Missing/zero baseline -> null. |
| HRV / resting HR baseline | Mean of usable measurements in the 28 days **before today**, minimum 7; both windows are provisional product choices. Observation/used counts, population SD and descriptive CV are returned. HRV delta %, resting HR delta bpm; no current-day leakage. |
| HR reserve | `(avg HR - resting HR) / (max HR - resting HR)`, ratio; all measurements required, max > resting, avg >= resting. |
| Strength volume / direct sets | Sum sets * reps * kg, **kg-repetitions** (not lifted mass or growth); sum direct sets by muscle. No guessed indirect sets. Strength change uses the same preceding four-week window and nonzero baseline. |
| Epley e1RM | `kg * (1 + reps/30)`, estimated kg **per exercise/date**; positive weights and provisional 1-10 rep filter. Non-failure/unknown effort explicitly annotated; cited validation does not establish accuracy for this athlete/arbitrary exercise. Not a tested max. |
| Descriptive pace trend | Mean duration / distance, min/km; >=2 current-week and >=3 preceding-window runs >=3 km at RPE 3-5. Percent vs prior pace; lower is faster. Terrain, weather and HR are not controlled. Not a performance forecast. |

Readiness is an **uncalibrated heuristic**: arithmetic mean of at least three available recovery components, rounded to 0-100. Components: sleep `min(100, hours/8*100)`; fatigue/soreness/stress `100-10*value`; HRV `clamp(80 + percent_delta, 0, 100)`; resting HR `clamp(85 - 5*max(0, bpm_delta), 0, 100)`. Missing components are excluded, not replaced with healthy values. Fatigue index is `100 - readiness`, not a trained fatigue prediction.

**Measurement comparability:** unknown metadata preserves legacy numeric demo behavior, explicitly labeled unknown. If today's measurement declares a pair, only exact declared matching baseline pairs are used; unknown/mismatched baseline measurements are excluded. Mixed known historical contexts without current metadata suppress the baseline. This can intentionally produce insufficient history. Declarations do not independently establish accuracy, and SD/CV is not measurement error, HRV significance or calibrated confidence.

The parameter/source registry is [`athleteos/evidence.py`](athleteos/evidence.py), exposed at `/api/evidence`. Rule version is **`demo-rules-v3`**. Variable/method/exact-threshold evidence is distinguished; all signal/product/reward cuts are provisional. Source review levels include abstract-only where full text was unavailable. No universal adverse HRV interpretation or causal injury claim is made.

Threshold signals: **sleep <6 h; fatigue >=7/10; soreness >=7/10; HRV <-20%; resting HR >=+7 bpm; weekly load >+30%**. Applied in priority order:

| Mode | Trigger | Decision |
|---|---|---|
| PROTECT | >=3 coincident signals, even if no readiness score | 40% planned duration, RPE capped at 2, gentle walk |
| RECOVER | >=2 signals, or readiness <50 | 60% duration, RPE capped at 3, gentle walk |
| INSUFFICIENT | <3 recovery components and <2 signals | No score; keep plan visible without a claimed data-backed adjustment |
| MAINTAIN | Readiness 50-74 or one signal | Keep planned dose |
| BUILD | Readiness >=75 and no crossed signals | Keep planned dose; **never automatically add load** |

A scheduled rest day stays rest. Future sessions are not adapted using nonexistent future recovery. Goal, check-in, import and plan edits invalidate relevant pending accepted doses; users must accept the current recommendation before a protective-session log. Users may record an actual overrun honestly, but it never earns a recovery reward. Historical snapshots remain unchanged when an acceptance is invalidated.

These thresholds are **demo UX rules, not clinical states or validated injury predictors**. Changing the goal adds context to explanations; this MVP does not generate a periodized sport-specific plan or predicted finish time.

### Rule-based Micro Wins

Implemented in `Store.complete` / `Store.win` in [`athleteos/server.py`](athleteos/server.py), persisted and deduplicated. Demo/import history does not auto-award app completions.

| Win | Verifiable trigger |
|---|---|
| Smart Training | Accept a calculated reduced dose; at most once per date |
| Recovery Win | Log the accepted dose with actual duration, RPE and sRPE load all <= recommendation |
| Consistency Win | 3 actual key sessions within 80-100% of chosen duration and without excess load |
| Strength Balance | Complete an on-dose strength session in BUILD/MAINTAIN; complete week has >=3 direct sets in >=2 groups and none >12; actual sets and strength volume cannot exceed the planned values |
| Adaptation Win | BUILD/MAINTAIN on-dose run, >=3 km at RPE 3-5, pace >=2% faster than >=3 prior 28-day runs at identical RPE and distance within 10%; not proof of physiological adaptation |
| Comeback Win | BUILD/MAINTAIN on-dose activity after two explicit rest days; missing dates do not qualify |
| Goal Progress Win | >=80% actual on-plan adherence across >=5 elapsed scheduled days |

No punitive rest streak. No performance or strength reward in RECOVER/PROTECT. Milestones/adherence are observable plan participation, not a physiological claim.

Dose adherence now checks the chosen RPE ceiling as well as duration/load, so a shorter but more intense session cannot silently qualify as recovery. Actual overruns remain logged honestly; no new scientific threshold is implied.

## Later trained-model integration

**Extension point: `predict_demo(features)` in `athleteos/domain.py`.** Integrate a genuinely evaluated adapter consistently in all three paths (`Store.view`, `Store.mutate`, `Store.snapshot_current`), or replace this shared function implementation. Never let captured decisions use a different predictor from the UI. Keep normalized observations and feature calculations unchanged. The separate PAMAP2 activity classifier does not implement a readiness adapter or connect a model to the app.

Input: `calculate_features()` output with **`contract_version: 1`** (additive extensions), explicit units above, `as_of`, nullable values, current recovery/device/protocol observations, component baselines, observation counts/variability/comparability, 7-day history and quality warnings. Frontend DTOs live in [`web/contracts.d.ts`](web/contracts.d.ts). Train-time transforms must be fit only on the training split and reproduced in the model adapter; the demo performs no z-score fitting.

Output contract: `contract_version`, `prediction_source` (currently **`demo-heuristic-v2`**, later a real model/version ID), `rule_version`, nullable `readiness_score` / `fatigue_index`, `mode`, `overload_pattern`, `signals`, `observed_signals` (value/unit/operator/threshold/nullable crossing/comparability), `reasons`, `component_scores`, `evidence_status`, `trace` (scoped rules/sources, confidence `null`), `limitations`. Preserve bounded scores and explicit insufficient-history behavior. Validate adapter outputs and surface failures, never substitute a success-shaped estimate. `recommend()` remains the session decision boundary; `Store.coach()` explains actual calculated outputs using five supported topics, not an LLM.

Decision exports preserve the original 35-day normalized input window, goal/check-in/session, feature/prediction/recommendation outputs, rule/source manifest and SHA-256 input/evidence digests. Actual outcomes record submitted dose/adherence only. Replaying a historical rule version requires its corresponding executable implementation, not merely the current rules; legacy missing snapshots are not reconstructible. These logs enable future evaluation but do not supply physiological labels or a performance forecast.

Before production model adoption: define labeled outcomes, consent/provenance, athlete-separated time-aware evaluation, calibrated thresholds, reproducible transforms and model validation. Garmin is a **future official integration subject to program approval and consent**, not a working connection.
