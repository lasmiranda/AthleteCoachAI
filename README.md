# AthleteOS Daily Coach

A responsive, local full-stack MVP: **Today / Daily Mission, Dashboard, Goal, Adaptive Plan, Micro Wins and AI Coach**. The Python backend serves the actual frontend, validates normalized data, calculates features and saves changes. There is **no connected trained model, LLM or Garmin account**.

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

## Run

Requires **Python 3.11+**. No Python dependencies or cloud credentials.

```powershell
python -m athleteos.server
```

Open **http://127.0.0.1:8000**. Run from the repository root. Alternate port/store:

```powershell
python -m athleteos.server --port 8001 --data .athleteos\another-demo.json
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
