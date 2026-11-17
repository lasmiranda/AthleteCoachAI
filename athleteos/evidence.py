"""Versioned product rules, scoped evidence and reproducible source provenance."""

import copy
import hashlib
import json

RULE_VERSION = "demo-rules-v3"
PREDICTION_SOURCE = "demo-heuristic-v3"
REVIEW_DATE = "2026-11-15"

SOURCES = {
    "foster-2001": {
        "id": "foster-2001", "citation": "Foster et al. (2001)",
        "title": "A New Approach to Monitoring Exercise Training",
        "url": "https://doi.org/10.1519/00124278-200102000-00019",
        "type": "primary-method-study",
        "population": "Cycle exercise participants and basketball players; Haddad's review reports 12 cycle participants and 14 male basketball players.",
        "protocol": "Steady-state/interval cycling and basketball; whole-session RPE compared with an HR-derived load method.",
        "supports": "Quantifying internal session load, not an individual injury-risk threshold.",
        "limitations": "Absolute RPE-derived and HR-derived scores differed despite consistent relationships. No validation of this app's readiness or dose reductions.",
        "verification": "Publisher abstract read; sample details cross-checked in Haddad review table 2.",
    },
    "haddad-2017": {
        "id": "haddad-2017", "citation": "Haddad et al. (2017)",
        "title": "Session-RPE Method for Training Load Monitoring: Validity, Ecological Usefulness, and Influencing Factors",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5673663/",
        "type": "method-review",
        "population": "36 validity/reliability studies across sports, ages, genders and training levels.",
        "protocol": "Familiarized whole-session modified CR-10 ratings multiplied by minutes; review also describes monotony and strain.",
        "supports": "sRPE calculation and descriptive derived load methods.",
        "limitations": "RPE depends on collection protocol and other influences. Correlation/reliability do not establish causal injury prevention or universal load-change cuts.",
        "verification": "Full-text rationale, derived calculations, validation discussion and table 2 read.",
    },
    "walsh-2021": {
        "id": "walsh-2021", "citation": "Walsh et al. (2021)",
        "title": "Sleep and the athlete: narrative review and 2021 expert consensus recommendations",
        "url": "https://bjsm.bmj.com/content/55/7/356",
        "accessible_url": "https://researchonline.ljmu.ac.uk/id/eprint/16297/",
        "type": "expert-consensus-review",
        "population": "Athlete literature, especially elite athletes; underrepresentation of females noted.",
        "protocol": "Narrative synthesis and expert sleep toolbox; emphasizes individual perceived sleep needs and assessment validity.",
        "supports": "Considering sleep in athlete monitoring and individualizing interpretation.",
        "limitations": "Effects of partial restriction over 1-3 nights remain unclear; experimental control and measurement limitations. Does not validate <6 h, an 8 h score denominator or an automatic dose reduction.",
        "verification": "Institutional repository abstract read; publisher page returned 403. No claim of full-text review.",
    },
    "buchheit-2014": {
        "id": "buchheit-2014", "citation": "Buchheit (2014)",
        "title": "Monitoring training status with HR measures: do all roads lead to Rome?",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3936188/",
        "type": "methodological-review",
        "population": "Aerobic-oriented athlete examples across recreational and elite settings; not a universal population calibration.",
        "protocol": "Repeated standardized resting HR/HRV recordings; considers position, timing, HRV index, measurement error and training context.",
        "supports": "Within-athlete monitoring with measurement comparability, variability and contextual interpretation.",
        "limitations": "HRV can increase with worse wellness or decrease while performance improves. Raw unspecified HRV ms is not interchangeable with lnRMSSD. Descriptive SD is not measurement error or a clinically meaningful change.",
        "verification": "Full-text abstract, recording conditions, table 1 and contradictory acute/chronic response sections read.",
    },
    "saw-2016": {
        "id": "saw-2016", "citation": "Saw, Main & Gastin (2016)",
        "title": "Monitoring the athlete training response: subjective self-reported measures trump commonly used objective measures: a systematic review",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4789708/",
        "type": "systematic-review",
        "population": "56 original studies of athletes in training.",
        "protocol": "Concurrent repeated subjective and objective well-being measures; established questionnaires with published validity/reliability, not arbitrary new scales.",
        "supports": "Including repeated subjective well-being observations in monitoring.",
        "limitations": "Subjective and objective measures generally did not correlate; heterogeneity precluded meta-analysis. Does not validate this app's custom 0-10 cuts or composite score.",
        "verification": "Full-text abstract, selection criteria, synthesis and results read.",
    },
    "impellizzeri-2020": {
        "id": "impellizzeri-2020", "citation": "Impellizzeri et al. (2020)",
        "title": "Acute:Chronic Workload Ratio: Conceptual Issues and Fundamental Pitfalls",
        "url": "https://doi.org/10.1123/ijspp.2019-0864",
        "accessible_url": "https://europepmc.org/article/MED/32502973",
        "type": "methodological-critique",
        "population": "Critique of ACWR literature, not a trial of this app or its uncoupled weekly comparison.",
        "protocol": "Examines ratio construction, statistical artifacts and the causal inference needed to prescribe load for injury reduction.",
        "supports": "Caution against converting load associations into causal injury-prevention claims.",
        "limitations": "No established causal injury-reduction effect of manipulating ACWR. This app's weekly-change formula is not the same metric; the critique does not itself validate or directly test its +30% cut.",
        "verification": "Indexed abstract verified through Europe PMC API, PMID 32502973; publisher access returned 403.",
    },
    "impellizzeri-load-2020": {
        "id": "impellizzeri-load-2020", "citation": "Impellizzeri, McCall, Ward, Bornn & Coutts (2020)",
        "title": "Training Load and Its Role in Injury Prevention, Part 2: Conceptual and Methodologic Pitfalls",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7534938/",
        "published_on": "2020-09-19", "reviewed_on": REVIEW_DATE,
        "doi": "10.4085/1062-6050-501-19",
        "correction_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8130765/",
        "type": "clinical-commentary-methodological-critique",
        "population": "Critical discussion of heterogeneous training-load/injury studies; not a validation cohort or an intervention trial.",
        "protocol": "Examines exposure measures, ratios, time windows, categorization, injury definitions, analyses, generalizability and missing data.",
        "supports": "Contextual review of load together with athlete responses; avoid treating associations, load changes or thresholds as causal injury evidence.",
        "limitations": "Does not validate this app's weekly comparison, coincident-signal criterion, readiness, or 40%/60% dose factors. No injury probability or prevention benefit follows.",
        "verification": "Full-text abstract, introductory practical scope, reference conceptual framework, and methodological sections on exposures, ratios, load measures, time windows, discretization, injury definitions, analyses, sample size, missing data and reporting read on 2026-11-15. Corrigendum (2021-05-17) read: acknowledges complementary overlapping commentary and omitted citation, not new threshold validation.",
    },
    "lesuer-1997": {
        "id": "lesuer-1997", "citation": "LeSuer et al. (1997)",
        "title": "The Accuracy of Prediction Equations for Estimating 1-RM Performance in the Bench Press, Squat, and Deadlift",
        "url": "https://doi.org/10.1519/00124278-199711000-00001",
        "type": "primary-validation-study",
        "population": "67 untrained college students (40 men, 27 women).",
        "protocol": "Four technique practice sessions, tested 1RM and repetitions to fatigue for bench press, squat and deadlift; seven equations compared.",
        "supports": "Studying repetition-based estimated 1RM under a specified protocol, not universal accuracy.",
        "limitations": "High correlations coexisted with biased estimates; all equations underestimated deadlift. Sets with RIR >0, arbitrary exercises and trained populations are not established by this study.",
        "verification": "Publisher abstract read; equation identity/context cross-checked in indexed paper text. No claim that every Epley output here was validated.",
    },
    "iusca-2021": {
        "id": "iusca-2021", "citation": "Schoenfeld et al., IUSCA (2021)",
        "title": "Resistance Training Recommendations to Maximize Muscle Hypertrophy in an Athletic Population: Position Stand of the IUSCA",
        "url": "https://journal.iusca.org/index.php/Journal/article/view/81",
        "type": "position-stand",
        "population": "Athletic resistance-training context, synthesized by an expert consortium.",
        "protocol": "Distinguishes constructs of hypertrophy, acute versus longitudinal evidence and strength versus hypertrophy.",
        "supports": "Separating a training stimulus/log from actual longitudinal muscle-size change.",
        "limitations": "Recorded kg-repetitions and direct sets do not measure muscle cross-sectional area. No support here for the demo's 3/12-set reward cuts.",
        "verification": "Publisher abstract and publication metadata read; no claim of full-text dose review.",
    },
}


def rule(rule_id, title, kind, parameters, source_ids, variable, method, protocol, limitations):
    return {"id": rule_id, "title": title, "version": RULE_VERSION, "kind": kind,
            "parameters": parameters, "source_ids": source_ids,
            "evidence": {"variable": variable, "method": method,
                         "exact_threshold": "provisional" if kind in {"signal", "product", "reward"} else "not-applicable"},
            "population": "No calibrated AthleteOS population. Source-specific populations must not be generalized automatically.",
            "protocol": protocol, "limitations": limitations}


RULES = {
    "monitoring-review": rule("monitoring-review", "Load and response review, not injury prediction", "product",
                              {"criterion": "existing weekly-load flag AND at least one existing recovery flag; explanatory only"},
                              ["impellizzeri-load-2020"],
                              "contextual-monitoring-supported", "provisional",
                              "Read recent change against the available individual baseline together with current recovery observations; disclose unknown collection comparability.",
                              "Training load can support adaptation. Coincidence does not establish harmful overload, injury, causality or prevention; numeric mode/dose rules are unchanged."),
    "srpe": rule("srpe", "Session load, monotony and strain", "metric",
                 {"formula": "minutes * whole-session RPE; mean daily load / population SD; weekly load * monotony"},
                 ["foster-2001", "haddad-2017"], "supported-in-studied-contexts", "supported-with-limitations",
                 "Whole-session RPE after familiarization; the app does not know rating timing or scale familiarity. Seven explicit days for weekly metrics.",
                 "AU are internal-load bookkeeping, not injury probability. Constant loads leave monotony/strain undefined."),
    "baseline": rule("baseline", "Individual descriptive baselines", "metric",
                     {"days": 28, "minimum_observations": 7, "variability": "population SD; CV only for positive mean"},
                     ["buchheit-2014"], "supported-in-studied-contexts", "descriptive-arithmetic",
                     "Preceding measurements, excluding today; device/protocol metadata used when declared. The 28-day/7-measurement choices are provisional product windows.",
                     "Day-to-day SD/CV is not measurement error, a significance test, smallest worthwhile change or validated confidence."),
    "sleep": rule("sleep", "Sleep observation flag", "signal", {"threshold": 6, "operator": "<", "unit": "h"},
                  ["walsh-2021"], "supported-in-studied-contexts", "provisional",
                  "Recorded sleep hours; assessment instrument and individual sleep needs are unknown.",
                  "The <6 h cut is a demo choice, not validated by the consensus. Do not infer a performance loss from one value."),
    "fatigue": rule("fatigue", "Self-reported fatigue flag", "signal", {"threshold": 7, "operator": ">=", "unit": "/10"},
                    ["saw-2016"], "supported-in-studied-contexts", "provisional",
                    "Custom current-day self-report, not a validated questionnaire score.",
                    "The exact 7/10 cut is provisional; cannot substitute for measured physiology."),
    "soreness": rule("soreness", "Self-reported soreness flag", "signal", {"threshold": 7, "operator": ">=", "unit": "/10"},
                     ["saw-2016"], "context-supported", "provisional",
                     "Custom current-day self-report, not a diagnostic assessment.",
                     "The exact 7/10 cut is provisional; soreness is not an injury diagnosis."),
    "hrv": rule("hrv", "HRV percentage-change flag", "signal", {"threshold": -20, "operator": "<", "unit": "%"},
                ["buchheit-2014"], "supported-in-studied-contexts", "provisional",
                "Raw HRV ms with declared index/device/recording protocol when available; never relabel as lnRMSSD.",
                "Unknown comparability stays unknown. A <-20% change is not a universal meaningful or adverse HRV change."),
    "resting-hr": rule("resting-hr", "Resting-HR change flag", "signal", {"threshold": 7, "operator": ">=", "unit": "bpm"},
                       ["buchheit-2014"], "supported-in-studied-contexts", "provisional",
                       "Recorded resting HR; compare declared matching device/protocol where available.",
                       "The +7 bpm cut is provisional. Hydration, environment, position and training context may confound interpretation."),
    "weekly-load": rule("weekly-load", "Weekly-load change flag", "signal", {"threshold": 30, "operator": ">", "unit": "%"},
                        ["haddad-2017", "impellizzeri-2020"], "load-method-supported", "provisional",
                        "Seven complete daily loads versus the preceding 28-day weekly average; zero/missing baseline gives no change.",
                        "The +30% flag is uncalibrated and not a causal injury predictor. This is not ACWR."),
    "readiness": rule("readiness", "Composite demo readiness and modes", "product",
                      {"sleep_reference_hours": 8, "hrv_offset": 80, "resting_hr_offset": 85,
                       "subjective_multiplier": 10,
                       "resting_hr_penalty": 5, "minimum_components": 3, "recover_score_below": 50,
                       "build_score_at_least": 75, "recover_signals": 2, "protect_signals": 3},
                      ["walsh-2021", "buchheit-2014", "saw-2016"], "monitoring-variables-supported", "provisional",
                      "Unweighted average of available component scores, without fitted outcome labels or calibrated weights.",
                      "Every score transform and mode cut is a product heuristic. Readiness is not a probability or a performance forecast."),
    "dose": rule("dose", "Product dose recommendation", "product",
                 {"protect_factor": 0.4, "recover_factor": 0.6, "protect_rpe_cap": 2, "recover_rpe_cap": 3},
                 ["walsh-2021", "buchheit-2014"], "recovery-context-only", "provisional",
                 "Preserve original plan; use a gentle walk on a demo reduction; planned rest stays rest.",
                 "No reviewed source establishes these exact 40%/60% reductions or guarantees injury prevention."),
    "strength-volume": rule("strength-volume", "Recorded strength stimulus", "metric",
                            {"formula": "sum(sets * reps * kg); sum direct sets by declared muscle"},
                            ["iusca-2021"], "training-stimulus-context", "descriptive-arithmetic",
                            "One recorded exercise per daily workout; only direct sets, no inferred indirect stimulus.",
                            "Volume and sets do not measure hypertrophy or equal optimal individual training dose."),
    "epley": rule("epley", "Epley formula estimate", "metric",
                  {"formula": "kg * (1 + reps / 30)", "repetition_divisor": 30, "maximum_reps": 10},
                  ["lesuer-1997"], "repetition-estimation-studied", "protocol-dependent-estimate",
                  "Repetitions-to-fatigue validation context; annotate non-failure, unknown RIR and unstudied exercises. The app's <=10-repetition filter is a provisional product restriction, not an established accuracy boundary.",
                  "A formula output for RIR >0 or an arbitrary exercise is not a validated tested max. High correlation does not eliminate bias."),
    "pace": rule("pace", "Observed pace comparison", "metric",
                 {"minimum_distance_km": 3, "rpe_low": 3, "rpe_high": 5, "recent_runs": 2, "baseline_runs": 3},
                 [], "recorded-observation", "descriptive-arithmetic",
                 "Minutes/km; group by demo RPE 3-5; terrain/weather and measurement devices unknown.",
                 "The comparability filters are product choices. No performance forecast or physiological adaptation follows from this trend."),
    "wins": rule("wins", "Micro Win product rules", "reward",
                 {"minimum_adherence": 0.8, "key_sessions": 3, "milestone_days": 5,
                  "minimum_direct_sets": 3, "maximum_direct_sets": 12, "muscle_groups": 2,
                  "pace_improvement": 0.02, "distance_tolerance": 0.1, "comparable_runs": 3,
                  "rest_days": 2},
                 ["iusca-2021", "saw-2016"], "context-only", "provisional",
                 "Explicit acceptance and actual session logs; dose ceilings prevent rewarding overload.",
                 "All reward cuts are motivation rules, not validated medical or adaptation outcomes."),
}


def manifest():
    return copy.deepcopy({"rule_version": RULE_VERSION, "reviewed_on": REVIEW_DATE,
                          "rules": list(RULES.values()), "sources": list(SOURCES.values()),
                          "scope": "Scoped evidence review, not systematic clinical validation or calibrated model inference."})


def digest(value):
    encoded = json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def trace(rule_ids):
    """Same rule/source payload for dashboard, plan, coach and historical snapshots."""
    rules = [copy.deepcopy(RULES[rule_id]) for rule_id in rule_ids]
    source_ids = sorted({source for item in rules for source in item["source_ids"]})
    return {"rule_version": RULE_VERSION, "rules": rules,
            "sources": [copy.deepcopy(SOURCES[source]) for source in source_ids],
            "threshold_status": "provisional", "confidence": None,
            "message": "Evidence may support a variable or method without validating this exact threshold or product decision."}
