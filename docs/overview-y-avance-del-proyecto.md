# AthleteOS AI: overview, avances y próximos pasos

**Fecha de corte: 10 de noviembre de 2026.** Documento para personas que se incorporan al proyecto, con perspectiva de producto y técnica. Resume el código local y los informes existentes; no incorpora nuevos entrenamientos, descargas ni validaciones clínicas.

## 1. Qué es el proyecto y qué valor busca aportar

**AthleteOS Daily Coach** busca ayudar a un deportista a entender su entrenamiento, registrar cómo se siente y decidir una misión diaria coherente con su plan. Reúne metas, actividad, recuperación y pequeños logros verificables en una experiencia conectada, explicando **qué datos se observaron, qué se calculó y por qué se propone una acción**.

El recorrido hasta ahora tiene cuatro entregas: un MVP funcional con datos demo; trazabilidad científica de sus reglas; adquisición y preparación de datasets reales para investigación; y un primer modelo entrenado de clasificación de actividades. **Estos avances son complementarios, pero no equivalentes:** haber entrenado un clasificador de sensores no significa haber entrenado el coach de recuperación.

Hoy existen dos líneas separadas:

- **Producto demo:** frontend y backend conectados, persistencia local y recomendaciones mediante reglas heurísticas explícitas.
- **Investigación con datos reales:** pipeline reproducible y un clasificador PAMAP2 entrenado y evaluado, independiente del producto.

El alcance es responsable y exploratorio: **no hay diagnóstico, prevención demostrada de lesiones, medición de crecimiento muscular ni pronósticos deportivos validados**. Tampoco hay un LLM, un modelo de readiness o una cuenta Garmin conectados a la app. El coach explica resultados determinísticamente; no simula una integración de IA generativa.

## 2. Estado por componente

“Completado” significa implementado o ejecutado en el alcance local descrito, **no listo para producción**. “Parcial” identifica una base existente con requisitos abiertos.

| Componente | Estado | Avance real y límite principal |
|---|---|---|
| Experiencia frontend/backend | **Completado: MVP local** | Interfaz responsive con Goal, Today/Daily Mission, Dashboard, Adaptive Plan, Micro Wins y AI Coach; acciones conectadas a la API. |
| Registro y persistencia | **Completado: demo** | Selección de atleta demo, metas, plan, check-ins, sesiones e importación/exportación CSV validada; guardado local y errores explícitos. Sin cuentas ni almacenamiento productivo. |
| Métricas y adaptación | **Completado: heurística** | Carga, baselines, calidad de datos y recomendaciones explicables. Cortes y puntuaciones todavía provisionales. No se genera un plan deportivo periodizado completo. |
| Evidencia y trazabilidad | **Completado: primera revisión** | Reglas/fuentes versionadas, población/protocolo/límites, snapshots históricos y resultados de dosis/adherencia. No es validación científica integral. |
| Datos reales de investigación | **Completado: dos fuentes** | Corredores competitivos y PAMAP2 descargados y preparados localmente, con procedencia y controles de integridad/fuga. |
| Primer modelo PAMAP2 | **Completado: baseline técnico** | Gaussian Naive Bayes entrenado, artefacto guardado, prueba separada e inferencia real. Rendimiento insuficiente en varias clases. |
| Mejora y generalización del modelo | **Parcial** | Hay baseline y protocolo reproducible; faltan comparaciones, evaluación más amplia y robustez ante otros sujetos/sensores. |
| Readiness, rendimiento o lesión mediante ML | **Pendiente** | No existe predictor entrenado para estas tareas. Faltan outcome, población, datos pertinentes y evaluación apropiada. |
| FitRec y Garmin | **Pendiente** | FitRec requiere decisión de uso/licencia y transferencia; Garmin requiere acceso oficial autorizado y consentimiento. |
| Publicación y preparación productiva | **Parcial / pendiente** | MVP publicado previamente; avances posteriores presentes localmente. Falta reconciliar Git, cerrar validación del estado completo y abordar seguridad/operación de producción. |

## 3. Cómo está construido

La arquitectura evita mezclar señales, reglas y modelos de tareas diferentes:

| Capa | Implementación | Responsabilidad |
|---|---|---|
| Interfaz | `web`: JavaScript, HTML y CSS, con contratos tipados | Presentar metas, métricas, plan, explicaciones y estados de carga/error/ausencia. |
| API y estado | `athleteos/server.py`: servidor HTTP Python y JSON local | Servir frontend/API, validar escrituras y persistir cambios; migración de estado y snapshots. |
| Dominio y evidencia | `athleteos/domain.py`, `athleteos/evidence.py` | Normalizar observaciones, calcular features y aplicar `demo-rules-v2` / `demo-heuristic-v2`. |
| Investigación | `research_data`: adquisición, preparación y verificación | Mantener esquemas específicos por fuente, particiones y transformaciones reproducibles. |
| Modelo separado | `research_data/training.py` | Entrenar, congelar, evaluar y ejecutar inferencia PAMAP2 mediante comandos locales. |

**Flujo del demo:** observación sintética/CSV/check-in → validación → métricas → señales observadas → heurística → recomendación y explicación → snapshot y resultado registrado. La carga sRPE usa minutos × RPE, en unidades arbitrarias; las otras métricas conservan sus unidades y requisitos.

**Flujo de investigación:** fuente oficial → archivos locales con procedencia/hashes → ventanas o tablas específicas → particiones → ajuste solo en entrenamiento → selección en validación → modelo congelado → prueba reservada. Los sujetos de fuentes distintas no se unen.

El CSV de la app representa **una actividad o descanso por día y un ejercicio de fuerza por sesión**; no puede representar fielmente sensores a 100 Hz. Por eso las tablas de investigación no se fuerzan dentro de ese contrato.

La app conserva ediciones en `.athleteos`, y los datasets, tablas y modelos permanecen en `.research-data`; ambas ubicaciones están excluidas de Git. El servidor demo es local, sin autenticación, y su JSON no está cifrado: **no debe exponerse en red ni utilizarse como repositorio de salud de producción**.

## 4. Qué significa “basado en evidencia”

Se separan tres niveles: **métrica calculada**, **señal observada** y **recomendación de producto**. Las fuentes permiten contextualizar variables o métodos; no convierten automáticamente una recomendación en científicamente validada.

Por ejemplo, la literatura respalda estudiar carga sRPE, sueño y seguimiento intraindividual bajo protocolos adecuados. **No valida nuestra combinación de readiness**, sus pesos implícitos o sus decisiones automáticas. Siguen siendo provisionales los cortes de sueño `<6 h`, HRV `<−20%`, FC de reposo `≥+7 bpm`, carga semanal `>+30%`, los modos y las reducciones al 40%/60% de duración.

Los baselines incluyen conteos, variabilidad y comparabilidad declarada de dispositivo/protocolo. Datos ausentes no equivalen a valores saludables; baselines cero, historia insuficiente y cargas constantes se manejan explícitamente. La SD/CV descriptiva **no demuestra significación clínica ni confianza predictiva**.

Los snapshots preservan entradas, reglas y recomendaciones históricas; los resultados posteriores registran dosis/adherencia, **no resultados fisiológicos inventados**. Las publicaciones científicas son fuentes para métodos, explicaciones y límites: **no se usan como si fueran filas individuales de entrenamiento**.

Detalle, alcance de lectura de cada artículo y matriz de reglas: [Avances de evidencia científica](avances-evidencia-cientifica.md).

## 5. Datos reales y primer modelo

### Fuentes: obtenido frente a investigado

| Fuente | Situación real | Utilidad y restricciones |
|---|---|---|
| **PAMAP2, UCI** | Archivo oficial obtenido; nueve registros Protocol procesados: **2,872,533 muestras → 3,833 ventanas de 12 actividades**. | CC BY 4.0. Clasificación de actividad con sensores; Optional excluido del benchmark. No aporta readiness longitudinal. |
| **Competitive Runners, DataverseNL** | Dos CSV completos preparados: **42,766 filas diarias y 42,798 semanales**, 74 participantes. | CC0. Etiqueta fuente de evento de lesión para investigación; sin modelo entrenado aquí. Son representaciones solapadas, **no dos cohortes independientes**. |
| **FitRec / Endomondo** | Documentación, tamaños y metodología revisados; **registros no descargados**. | Uso académico no comercial, sin redistribución según fuente consultada; archivos de aproximadamente 1–8 GB. Requiere decisión de finalidad, licencia y transferencia. Su código es referencia, no otro dataset. |
| **Garmin Developer Program** | Opciones oficiales investigadas; **sin acceso ni integración implementados**. | API autenticada, no dataset público. Modalidad Personal/Business, disponibilidad y autorizaciones deben verificarse para el caso elegido. |
| **Revisión de volumen e hipertrofia** | Artículo PMC8884877 revisado como evidencia. | No proporciona aquí una tabla individual para entrenar ni etiquetas de crecimiento muscular. |

La preparación incluye checksums/procedencia, ausencias explícitas, diccionarios y particiones por sujeto; corredores añade evaluación temporal con purga. Los datos no se adjuntan a este overview. Esquemas, licencias y comandos: [Datos reales y preparación](datos-reales-y-preparacion.md).

### Modelo realmente entrenado: qué demuestra y qué no

Se entrenó **Gaussian Naive Bayes**, versión `pamap2-activity-gnb-v1`, con Python estándar. Fue la alternativa elegida por el usuario tras fallar la descarga oficial de dependencias de scikit-learn por negociación TLS; no se desactivó seguridad.

Utiliza 120 features por ventana: media, SD y fracción observada de 40 canales; añade máscaras de ausencia. Las medianas, escalado, estadísticas de clase y priors se ajustan solo con entrenamiento. Dos candidatos de suavizado se compararon únicamente en validación; el modelo quedó congelado antes de evaluar prueba.

| Partición por participantes distintos | Participantes | Ventanas |
|---|---:|---:|
| Entrenamiento | **5** | 2,352 |
| Validación | **2** | 977 |
| Prueba reservada | **2** | 504 |

Las 12 clases están presentes en cada partición. No se cambió la asignación para mejorar resultados ni se reajustó el modelo con validación/prueba.

| Métrica de prueba | Clasificador | Comparador: clase más frecuente de entrenamiento |
|---|---:|---:|
| Accuracy | **58.13%** | 9.33% |
| Macro-F1 | **0.528** | 0.014 |
| Balanced accuracy | **58.44%** | 8.33% |

Son **293 aciertos de 504**. Sin embargo, no predice ninguna ventana de *sitting* (sentado, 0/46); reconoce solo 2/40 de marcha nórdica y 11/37 de salto de cuerda. El resultado global no debe ocultar estos fallos. Nueve personas y ventanas correlacionadas no permiten afirmar generalización poblacional.

El artefacto local JSON, manifiesto, evaluación e inferencia se conservaron; una repetición de la misma receta produjo parámetros idénticos byte a byte. Al preparar este overview se confirmó que los hashes del modelo/manifiesto/código y las métricas guardadas siguen coincidiendo, sin reentrenar. **El clasificador sigue separado de la app y no reemplaza readiness, fatiga, rendimiento o lesión.**

Resultados por clase, matriz de confusión y reproducción: [Primer modelo PAMAP2](primer-modelo-pamap2.md).

## 6. Validación y estado local frente a GitHub

La evidencia de ejecución corresponde a entregas concretas, no a una aprobación universal del estado actual. La entrega de trazabilidad registró 55 pruebas backend, nueve de navegador y comprobaciones de build/tipos exitosas. Posteriormente, la suite ampliada de adquisición encontró restricciones de permisos en renombrado temporal y HTTP local; npm no llegó a iniciar navegador. **No se presenta esa suite completa como aprobada.**

La entrega del modelo sí registró **ocho pruebas nuevas y 33 regresiones de dominio/evidencia exitosas**, compilación, verificación de datos reales y entrenamiento/evaluación/inferencia reales. Este overview es documental: no volvió a ejecutar suites, no acredita eficacia deportiva y no supone que los bloqueos hayan desaparecido.

Hay que distinguir los siguientes estados:

| Ubicación | Último estado confirmado, no una sincronización nueva |
|---|---|
| GitHub: [repositorio AthleteAI](https://github.com/laurase_microsoft/AthleteAI) | El último `main` confirmado durante la publicación del MVP fue `9bf96dae2f7fb1f186f1dc52768027ee8d844268`. **No se reconsultó el remoto en esta entrega**; no se afirma que siga sin cambios. |
| Trabajo local | La trazabilidad quedó registrada previamente en el commit `1018e493394f118ae2868e01cadf7df0ee256e4c`. Adquisición, entrenamiento y documentos posteriores están presentes localmente; su estado Git actual no se revalidó. |
| Datos/modelos locales | Se confirmó presencia de fuentes y artefacto del modelo; están excluidos de Git. Un clon de GitHub no garantiza incluirlos. |

El último bloqueo documentado de Git fue una denegación de lectura de su configuración por el sandbox. No se reintentó ni se eludió en este trabajo. Tampoco se verificó aquí la resolución de permisos de HTTP/npm o de conectividad TLS. **No se hizo commit, push, merge ni PR de este overview.**

## 7. Qué falta: prioridades propuestas y criterios de cierre

Este orden es una **propuesta de trabajo**, no funcionalidades ya implementadas ni un compromiso de fechas. No se asigna un porcentaje de avance sin un alcance cerrado.

| Prioridad / dependencia | Próximo resultado tangible | Criterio de aceptación |
|---|---|---|
| **1. Consolidar entrega**, antes de compartir una versión reproducible | Resolver permisos por canales autorizados; reconciliar trabajo local, historial y remoto; establecer respaldo permitido de artefactos. | Estado Git comprobado, solo código/docs publicables incluidos y datos excluidos; suites relevantes ejecutadas con resultados registrados. Publicación solo con autorización. |
| **2. Definir la siguiente tarea**, antes de ampliar modelos | Acordar si se mejora clasificación de actividad o se investiga un outcome del coach; definir población, entradas, horizonte y uso permitido. | Protocolo escrito con etiquetas verificables, métricas/baselines, separación de sujetos/tiempo y límites de decisión. No llamar readiness a otra tarea. |
| **3. Mejorar PAMAP2**, si se elige esa línea | Comparar baselines y robustez por clase/sensores con protocolo agrupado predefinido. | Resultados reproducibles y errores/ausencias por clase reportados; sin seleccionar por el test ya observado ni tratar ventanas como sujetos independientes. |
| **4. Preparar datos adecuados al coach**, si se busca readiness/rendimiento | Recogida longitudinal consentida, protocolos comparables y outcomes reales; revisar licencias de fuentes adicionales. | Trazabilidad de consentimiento/retención, calidad y labels auditables; evaluación temporal/externa planificada. FitRec/Garmin solo con autorización aplicable. |
| **5. Evaluar reglas o un nuevo predictor**, depende de 2 y 4 | Comparar heurística y alternativas contra resultados pertinentes; estudiar incertidumbre y calibración cuando proceda. | Ganancia demostrada frente a baselines para el uso definido, fallos/subgrupos descritos y sin claims clínicos no demostrados. |
| **6. Integrar un modelo pertinente**, depende de 5 | Adapter versionado en la frontera `predict_demo` manteniendo contratos y explicaciones honestas. | UI, API y snapshots usan la misma fuente; unidades/ausencias/errores y compatibilidad probados. PAMAP2 no se enchufa como readiness. |
| **7. Preparar producción**, antes de datos personales en un servicio | Autenticación/autorización, cifrado, aislamiento, retención, backups, observabilidad y despliegue revisado. | Requisitos de privacidad/seguridad y operación verificados; recuperación probada y piloto acotado antes de ampliar acceso. |

Las revisiones científicas deben continuar junto a estas fases, incluyendo resultados negativos y aplicabilidad. Un incremento de accuracy no demuestra beneficio para el deportista ni prevención causal de lesiones.

## 8. Guía de lectura y fuentes

Para ejecutar el demo y entender sus contratos: [README](../README.md). Para profundizar sin duplicar este resumen: [evidencia y reglas](avances-evidencia-cientifica.md), [adquisición y preparación](datos-reales-y-preparacion.md) y [entrenamiento/evaluación PAMAP2](primer-modelo-pamap2.md). Esos informes conservan sus fechas y limitaciones de revisión; el presente documento resume el conjunto.

Fuentes públicas de referencia, ya revisadas en esas entregas, **no investigadas de nuevo para este overview**:

- [Haddad et al., método sRPE](https://pmc.ncbi.nlm.nih.gov/articles/PMC5673663/), [Buchheit, seguimiento con medidas cardiacas](https://pmc.ncbi.nlm.nih.gov/articles/PMC3936188/) y [Walsh et al., consenso de sueño](https://doi.org/10.1136/bjsports-2020-102025): métodos/contexto, no validación de nuestros cortes.
- [PAMAP2, UCI](https://doi.org/10.24432/C5NW2H) y [Competitive Runners, DataverseNL](https://doi.org/10.34894/UWU9PV): datasets usados con esquemas y tareas separados.
- [FitRec](https://cseweb.ucsd.edu/~jmcauley/datasets/fitrec.html) y [código metodológico](https://github.com/nijianmo/fit-rec): referencia pendiente de adquisición autorizada.
- [Garmin Developer Program, overview](https://developer.garmin.com/gc-developer-program/overview/): vía oficial de acceso, no conexión implementada.
- [Baz-Valle et al., revisión de volumen e hipertrofia](https://pmc.ncbi.nlm.nih.gov/articles/PMC8884877/): evidencia de grupo, no registros individuales de entrenamiento.
