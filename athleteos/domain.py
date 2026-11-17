"""Normalized inputs, transparent features and replaceable demo inference."""

import csv
import io
import math
import statistics
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from athleteos.evidence import PREDICTION_SOURCE, RULES, RULE_VERSION, trace


class ValidationError(ValueError):
    """An actionable invalid-input error, safe to display to the user."""


FIELDS = [
    "athlete_id", "timestamp", "timezone", "sport_type", "duration_min",
    "distance_km", "session_rpe", "avg_hr_bpm", "max_hr_bpm", "resting_hr_bpm",
    "hrv_ms", "sleep_hours", "fatigue", "soreness", "stress", "elevation_m",
    "exercise", "muscle_group", "sets", "reps", "load_kg", "rir",
]
METADATA_FIELDS = ["hrv_device", "hrv_protocol", "resting_hr_device", "resting_hr_protocol"]
SPORTS = {"run", "cycle", "strength", "walk", "rest"}
MUSCLES = {"legs", "push", "pull", "core"}
RECOVERY_FIELDS = ("sleep_hours", "fatigue", "soreness", "stress", "hrv_ms", "resting_hr_bpm")
LIMITS = {
    "duration_min": (0, 1440), "distance_km": (0, 500), "session_rpe": (0, 10),
    "avg_hr_bpm": (20, 240), "max_hr_bpm": (20, 240),
    "resting_hr_bpm": (20, 200), "hrv_ms": (0, 500), "sleep_hours": (0, 24),
    "fatigue": (0, 10), "soreness": (0, 10), "stress": (0, 10),
    "elevation_m": (0, 20000), "sets": (1, 100), "reps": (1, 100),
    "load_kg": (0, 1000), "rir": (0, 10),
}


def zone(name):
    # Windows does not ship the IANA database; UTC needs no third-party package.
    if name == "UTC":
        return timezone.utc
    if not isinstance(name, str):
        raise ValidationError("timezone is required.")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError("Unknown/unavailable IANA timezone. This demo uses UTC.") from None


def number(value, field, required=False):
    if value is None or value == "":
        if required:
            raise ValidationError(f"{field} is required.")
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValidationError(f"{field} must be a number, not a boolean or object.")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be numeric.") from None
    low, high = LIMITS[field]
    if not math.isfinite(result) or not low <= result <= high:
        raise ValidationError(f"{field} must be between {low} and {high}.")
    if field in {"sets", "reps"}:
        if not result.is_integer():
            raise ValidationError(f"{field} must be an integer.")
        return int(result)
    return result


def iso_date(value):
    if not isinstance(value, str):
        raise ValidationError("Date must be YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValidationError("Date must be YYYY-MM-DD.") from None
    if parsed.isoformat() != value:
        raise ValidationError("Date must be YYYY-MM-DD.")
    return parsed


def normalized_record(raw, athlete_id, today):
    if not isinstance(raw, dict):
        raise ValidationError("Each record must be an object.")
    if raw.get("athlete_id") != athlete_id:
        raise ValidationError(f"athlete_id must match selected athlete '{athlete_id}'.")
    timestamp = raw.get("timestamp")
    if not isinstance(timestamp, str):
        raise ValidationError("timestamp must be offset-aware ISO 8601.")
    try:
        stamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise ValidationError("timestamp must be offset-aware ISO 8601.") from None
    if stamp.tzinfo is None:
        raise ValidationError("timestamp must include an explicit UTC offset.")
    local = stamp.astimezone(zone(raw.get("timezone")))
    if stamp.utcoffset() != local.utcoffset():
        raise ValidationError("timestamp offset must match timezone at this instant.")
    day = local.date()
    if day > today:
        raise ValidationError("Observed records cannot be in the future.")
    sport = raw.get("sport_type")
    if not isinstance(sport, str) or sport not in SPORTS:
        raise ValidationError("sport_type must be run, cycle, strength, walk or rest.")
    result = {field: number(raw.get(field), field, field in {
        "duration_min", "session_rpe"
    }) for field in LIMITS}
    if sport == "rest" and (result["duration_min"] != 0 or result["session_rpe"] != 0
                            or result["distance_km"] not in (None, 0)):
        raise ValidationError("Explicit rest days require zero duration, RPE and distance.")
    if sport != "rest" and result["duration_min"] <= 0:
        raise ValidationError("Active sessions require positive duration.")
    if sport not in {"run", "cycle", "walk"} and result["distance_km"] not in (None, 0):
        raise ValidationError("Only run, cycle and walk observations can contain distance.")
    for field in ("exercise", "muscle_group"):
        value = raw.get(field)
        if value == "":
            value = None
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 80):
            raise ValidationError(f"{field} must be text up to 80 characters.")
        result[field] = value
    strength_fields = ("exercise", "muscle_group", "sets", "reps", "load_kg")
    present = [result[field] is not None for field in strength_fields]
    if any(present) and not all(present):
        raise ValidationError("Strength requires exercise, muscle_group, sets, reps and load_kg together.")
    if all(present) and result["muscle_group"] not in MUSCLES:
        raise ValidationError("muscle_group must be legs, push, pull or core.")
    if sport == "strength" and not all(present):
        raise ValidationError("Strength sessions require complete strength fields.")
    if sport != "strength" and (any(present) or result["rir"] is not None):
        raise ValidationError("Strength fields belong only to strength sessions.")
    if result["avg_hr_bpm"] is not None and result["max_hr_bpm"] is not None:
        if result["avg_hr_bpm"] > result["max_hr_bpm"]:
            raise ValidationError("avg_hr_bpm cannot exceed max_hr_bpm.")
    if result["max_hr_bpm"] is not None and result["resting_hr_bpm"] is not None:
        if result["max_hr_bpm"] <= result["resting_hr_bpm"]:
            raise ValidationError("max_hr_bpm must exceed resting_hr_bpm.")
    result.update(athlete_id=athlete_id, timestamp=timestamp, timezone=raw["timezone"],
                  sport_type=sport, date=day.isoformat())
    result.update(measurement_metadata(raw, result))
    return result


def measurement_metadata(raw, measurements):
    result = {}
    for prefix, measurement in (("hrv", "hrv_ms"), ("resting_hr", "resting_hr_bpm")):
        for suffix in ("device", "protocol"):
            field = f"{prefix}_{suffix}"
            value = raw.get(field)
            if value == "":
                value = None
            if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 160):
                raise ValidationError(f"{field} must be text up to 160 characters or blank.")
            result[field] = value.strip() if value is not None else None
        device, protocol = result[f"{prefix}_device"], result[f"{prefix}_protocol"]
        if (device is None) != (protocol is None):
            raise ValidationError(f"{prefix}_device and {prefix}_protocol must be supplied together.")
        if device is not None and measurements.get(measurement) is None:
            raise ValidationError(f"{measurement} is required when its measurement metadata is supplied.")
    return result


def parse_csv(text, athlete_id, today):
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("CSV is empty.")
    try:
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), strict=True)
        if reader.fieldnames not in (FIELDS, FIELDS + METADATA_FIELDS):
            raise ValidationError("CSV header must exactly match the documented legacy or metadata-extended normalized schema.")
        records, days = [], set()
        for line, raw in enumerate(reader, 2):
            if line > 3661:
                raise ValidationError("Maximum 3660 daily rows per import.")
            if None in raw or any(value is None for value in raw.values()):
                raise ValidationError(f"Row {line}: wrong column count.")
            try:
                record = normalized_record(raw, athlete_id, today)
            except ValidationError as error:
                raise ValidationError(f"Row {line}: {error}") from error
            if record["date"] in days:
                raise ValidationError(f"Row {line}: duplicate local date; one daily session per date.")
            days.add(record["date"])
            record["source"] = "CSV import"
            record["recovery_source"] = "CSV import"
            records.append(record)
    except csv.Error as error:
        raise ValidationError(f"Malformed CSV: {error}") from error
    if not records:
        raise ValidationError("CSV contains no data rows.")
    return records


def training_load(record):
    return record["duration_min"] * record["session_rpe"]


def percentage(current, baseline):
    return None if current is None or baseline is None or baseline == 0 else (
        (current - baseline) / baseline * 100)


def baseline_quality(records, field, current, today):
    prefix = "hrv" if field == "hrv_ms" else "resting_hr"
    measured = [r for r in records if r.get(field) is not None]

    def context(record):
        device, protocol = record.get(f"{prefix}_device"), record.get(f"{prefix}_protocol")
        return (device, protocol) if device and protocol else None

    current_context = context(current or {})
    declared = {context(r) for r in measured if context(r) is not None}
    unknown = sum(context(r) is None for r in measured)
    if current_context is not None:
        used = [r for r in measured if context(r) == current_context]
        mismatches = sum(context(r) is not None and context(r) != current_context for r in measured)
        comparability = "declared-match" if used else "declared-mismatch" if mismatches else "unknown"
    elif len(declared) > 1:
        used, mismatches, comparability = [], len(measured) - unknown, "mixed-declared-protocols"
    else:
        used, mismatches, comparability = measured, 0, "unknown"
    values = [r[field] for r in used]
    minimum = RULES["baseline"]["parameters"]["minimum_observations"]
    mean = statistics.mean(values) if len(values) >= minimum else None
    sd = statistics.pstdev(values) if len(values) >= 2 else None
    status = "insufficient-history" if len(values) < minimum else "zero-baseline" if mean == 0 else "constant-history" if sd == 0 else "available"
    notes = ["Descriptive SD/CV is not measurement error, clinical significance or calibrated confidence."]
    if comparability != "declared-match":
        notes.append("Device/index/posture/timing comparability is unknown or mixed; no universal HRV significance is inferred.")
    else:
        notes.append("Only declared exact device/protocol matches are used; declarations do not independently verify measurement validity.")
    if unknown and current_context:
        notes.append("Measurements without metadata are excluded from this declared-protocol comparison.")
    window_days = RULES["baseline"]["parameters"]["days"]
    return {"unit": "ms" if field == "hrv_ms" else "bpm", "window_days": window_days,
            "window_start": str(today - timedelta(days=window_days)), "window_end": str(today - timedelta(days=1)),
            "observation_count": len(measured), "used_count": len(values), "required_count": minimum,
            "mean": mean, "population_sd": sd,
            "coefficient_of_variation_pct": sd / mean * 100 if sd is not None and mean is not None and mean > 0 else None,
            "status": status, "comparability": comparability, "unknown_metadata_count": unknown,
            "excluded_mismatch_count": mismatches, "current_device": (current or {}).get(f"{prefix}_device"),
            "current_protocol": (current or {}).get(f"{prefix}_protocol"),
            "notes": notes, "rule_id": "baseline"}


def calculate_features(records, today, checkin=None):
    """Explicit local daily observations, including recorded rest; no imputation."""
    available = {r["date"]: r for r in records if iso_date(r["date"]) <= today}
    week_days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    week = [available[d] for d in week_days if d in available]
    before = [r for r in records if today - timedelta(days=RULES["baseline"]["parameters"]["days"]) <= iso_date(r["date"]) < today]
    prior_days = [(today - timedelta(days=i)).isoformat() for i in range(7, 35)]
    prior = [available[d] for d in prior_days if d in available]
    current = dict(available[today.isoformat()]) if today.isoformat() in available else None
    if checkin is not None:
        current = dict(current or {})
        current.update(checkin)
        current["recovery_source"] = "App check-in"
    complete_week = len(week) == 7
    daily = [training_load(r) for r in week]
    weekly_load = sum(daily) if complete_week else None
    sd = statistics.pstdev(daily) if complete_week else None
    monotony = statistics.mean(daily) / sd if sd is not None and sd > 0 else None
    prior_weekly = sum(training_load(r) for r in prior) / 4 if len(prior) == 28 else None
    hrv_quality = baseline_quality(before, "hrv_ms", current, today)
    hr_quality = baseline_quality(before, "resting_hr_bpm", current, today)
    hrv_baseline, hr_baseline = hrv_quality["mean"], hr_quality["mean"]
    strength_week = [r for r in week if r.get("sets") is not None]
    prior_strength = [r for r in prior if r.get("sets") is not None]
    strength_volume = sum(r["sets"] * r["reps"] * r["load_kg"] for r in strength_week)
    prior_volume = sum(r["sets"] * r["reps"] * r["load_kg"] for r in prior_strength) / 4
    sets = {muscle: sum(r["sets"] for r in strength_week if r["muscle_group"] == muscle)
            for muscle in sorted(MUSCLES)}
    reserve = None
    if current and all(current.get(f) is not None for f in ("avg_hr_bpm", "resting_hr_bpm", "max_hr_bpm")):
        denominator = current["max_hr_bpm"] - current["resting_hr_bpm"]
        if denominator > 0 and current["avg_hr_bpm"] >= current["resting_hr_bpm"]:
            reserve = (current["avg_hr_bpm"] - current["resting_hr_bpm"]) / denominator
    pace_rules = RULES["pace"]["parameters"]
    runs = [r for r in week if r["sport_type"] == "run" and (r["distance_km"] or 0) >= pace_rules["minimum_distance_km"]
            and pace_rules["rpe_low"] <= r["session_rpe"] <= pace_rules["rpe_high"]]
    baseline_runs = [r for r in prior if r["sport_type"] == "run"
                     and (r["distance_km"] or 0) >= pace_rules["minimum_distance_km"]
                     and pace_rules["rpe_low"] <= r["session_rpe"] <= pace_rules["rpe_high"]]
    pace = statistics.mean(r["duration_min"] / r["distance_km"] for r in runs) if len(runs) >= pace_rules["recent_runs"] else None
    baseline_pace = statistics.mean(r["duration_min"] / r["distance_km"] for r in baseline_runs) if len(baseline_runs) >= pace_rules["baseline_runs"] else None
    warnings = []
    if not complete_week:
        warnings.append("Incomplete 7-day activity history: weekly totals, monotony, strain and muscle totals are unavailable. Missing dates are not rest days.")
    elif sd == 0:
        warnings.append("Constant daily loads: monotony and strain are undefined (zero standard deviation).")
    if len(prior) != 28:
        warnings.append("Load/strength change needs all 28 explicit days before the current week.")
    if prior_weekly == 0:
        warnings.append("Prior load baseline is zero: percentage change is undefined.")
    if hrv_baseline in (None, 0):
        warnings.append("HRV comparison needs at least 7 preceding measurements and a positive baseline.")
    if hr_baseline is None:
        warnings.append("Resting HR baseline needs at least 7 preceding measurements.")
    if current is None:
        warnings.append("No recovery observation for today. Record a check-in; missing recovery is not inferred.")
    if pace is None or baseline_pace is None:
        warnings.append("Pace trend needs 2 recent and 3 prior runs >=3 km at RPE 3-5. It is descriptive, not a performance prediction.")
    if prior_volume == 0:
        warnings.append("Prior strength volume is zero: strength percentage change is undefined.")
    for label, quality in (("HRV", hrv_quality), ("Resting HR", hr_quality)):
        if quality["comparability"] != "declared-match":
            warnings.append(f"{label}: measurement comparability {quality['comparability']}; numeric changes are descriptive, not significance tests.")
        if quality["excluded_mismatch_count"]:
            warnings.append(f"{label}: {quality['excluded_mismatch_count']} declared device/protocol mismatches excluded.")
        if quality["status"] == "constant-history":
            warnings.append(f"{label}: constant measured baseline; zero SD is not evidence of clinical stability.")
    prior_daily = [training_load(r) for r in prior]
    prior_sd = statistics.pstdev(prior_daily) if len(prior_daily) >= 2 else None
    prior_daily_mean = statistics.mean(prior_daily) if len(prior) == 28 else None
    estimates = []
    for r in strength_week:
        if r["load_kg"] <= 0 or r["reps"] > RULES["epley"]["parameters"]["maximum_reps"]:
            continue
        protocol_status = "non-failure-set" if (r.get("rir") or 0) > 0 else "effort-unknown" if r.get("rir") is None else "declared-to-failure"
        estimates.append({"exercise": r["exercise"], "date": r["date"],
                          "e1rm_kg": r["load_kg"] * (1 + r["reps"] / RULES["epley"]["parameters"]["repetition_divisor"]),
                          "protocol_status": protocol_status,
                          "evidence_status": "protocol-dependent-formula",
                          "limitations": "Not a tested max; cited repetition-to-fatigue validation does not establish accuracy for this athlete or arbitrary exercise."})
    return {
        "contract_version": 1, "as_of": today.isoformat(), "current": current,
        "weekly_load_au": weekly_load, "observed_week_load_au": sum(daily),
        "week_days_observed": len(week), "baseline_weekly_load_au": prior_weekly,
        "load_change_pct": percentage(weekly_load, prior_weekly),
        "monotony_ratio": monotony, "strain_au": weekly_load * monotony if monotony is not None else None,
        "hrv_baseline_ms": hrv_baseline, "resting_hr_baseline_bpm": hr_baseline,
        "hrv_change_pct": percentage(current.get("hrv_ms") if current else None, hrv_baseline),
        "hr_reserve_ratio": reserve,
        "strength_volume_kg": strength_volume if complete_week else None,
        "strength_change_pct": percentage(strength_volume, prior_volume) if complete_week and len(prior) == 28 else None,
        "direct_sets_by_muscle": sets if complete_week else None,
        "e1rm_estimates": estimates,
        "pace_min_per_km": pace, "pace_change_pct": percentage(pace, baseline_pace),
        "pace_quality": {"recent_run_count": len(runs), "baseline_run_count": len(baseline_runs),
                         "comparability": "unknown-terrain-weather-device", "status": "descriptive-only"},
        "baseline_quality": {"hrv": hrv_quality, "resting_hr": hr_quality,
                             "weekly_load": {"observation_count": len(prior), "required_count": 28,
                                             "mean_daily_load_au": prior_daily_mean, "population_sd_daily_au": prior_sd,
                                             "weekly_average_au": prior_weekly,
                                             "coefficient_of_variation_pct": prior_sd / prior_daily_mean * 100 if prior_sd is not None and prior_daily_mean not in (None, 0) else None,
                                             "status": "insufficient-history" if len(prior) != 28 else "zero-baseline" if prior_weekly == 0 else "constant-history" if prior_sd == 0 else "available",
                                             "comparability": "unknown-RPE-collection-protocol"}},
        "history": [{"date": d, "load_au": training_load(available[d]) if d in available else None,
                     "source": available[d]["source"] if d in available else "Missing"} for d in week_days],
        "warnings": warnings,
    }


def monitoring_review(features, observations):
    """Interpret existing flags without changing readiness, modes or dose arithmetic."""
    load = next(item for item in observations if item["rule_id"] == "weekly-load")
    recovery = [item for item in observations if item["rule_id"] != "weekly-load"]
    crossed = [item["rule_id"] for item in recovery if item["crossed"] is True]
    unknown = [item["rule_id"] for item in observations if item["crossed"] is None]
    combined = load["crossed"] is True and bool(crossed)
    if combined:
        status, summary = "combined-signals", "Load change and recovery flags coincide: review possible overload, not confirmed harmful overload."
    elif load["crossed"] is True:
        status, summary = "load-change-only", "Load change alone: not evidence of harmful overload."
    elif crossed:
        status, summary = "recovery-signals-only", "Recovery flags warrant review; a concurrent load increase is not established."
    elif unknown:
        status, summary = "incomplete-observations", "The monitoring picture is incomplete; missing observations are not reassuring evidence."
    else:
        status, summary = "no-crossings", "No existing demo cuts crossed; this does not establish safety or adaptation."
    return {
        "rule_id": "monitoring-review", "status": status, "summary": summary,
        "combined_signal_rule_ids": ["weekly-load", *crossed] if combined else [],
        "missing_rule_ids": unknown,
        "facts": {"weekly_load_au": features["weekly_load_au"],
                  "baseline_weekly_load_au": features["baseline_weekly_load_au"],
                  "week_days_observed": features["week_days_observed"],
                  "baseline_days_observed": features["baseline_quality"]["weekly_load"]["observation_count"],
                  "recovery_source": (features["current"] or {}).get("recovery_source", "Missing recovery")},
        "contexts": [{"rule_id": item["rule_id"], "source_ids": list(RULES[item["rule_id"]]["source_ids"]),
                      "support": RULES[item["rule_id"]]["evidence"]["variable"],
                      "comparability": item["comparability"]} for item in observations],
        "criterion": "Explanatory review only: the existing weekly-load cut and at least one existing recovery cut coincide. All cuts are provisional; this adds no score or dose rule.",
        "review_action": "Review recording quality, the planned progression and current recovery with your coach before accepting a provisional adjustment." if combined or crossed else
                         "Review progression and collect missing recovery observations; do not assume a load increase is harmful." if load["crossed"] is True else
                         "Complete missing observations and check baseline comparability before drawing conclusions." if unknown else
                         "Continue monitoring the planned progression and response; no automatic increase is justified.",
        "limitations": "Training can produce adaptation. These observations and concurrent flags do not establish injury, harmful overload, causality or a prevention benefit. Unknown assessment/device/protocol comparability remains unknown.",
    }


def predict_demo(features):
    """Inference boundary: a future model adapter must preserve this output contract."""
    current = features["current"] or {}
    components, reasons, signals = {}, [], []
    scoring = RULES["readiness"]["parameters"]
    for field in ("sleep_hours", "fatigue", "soreness", "stress"):
        value = current.get(field)
        if value is not None:
            components[field] = min(100, value / scoring["sleep_reference_hours"] * 100) if field == "sleep_hours" else 100 - value * scoring["subjective_multiplier"]
    hrv_change = features["hrv_change_pct"]
    if hrv_change is not None:
        components["hrv"] = max(0, min(100, scoring["hrv_offset"] + hrv_change))
        reasons.append(f"HRV is {hrv_change:+.1f}% vs your preceding measurement baseline; a descriptive change, not universal significance.")
        if hrv_change < RULES["hrv"]["parameters"]["threshold"]:
            signals.append(f"HRV more than {abs(RULES['hrv']['parameters']['threshold']):g}% below baseline")
    resting = current.get("resting_hr_bpm")
    baseline = features["resting_hr_baseline_bpm"]
    if resting is not None and baseline is not None:
        delta = resting - baseline
        components["resting_hr"] = max(0, min(100, scoring["resting_hr_offset"] - max(0, delta) * scoring["resting_hr_penalty"]))
        reasons.append(f"Resting HR is {delta:+.1f} bpm vs baseline.")
        if delta >= RULES["resting-hr"]["parameters"]["threshold"]:
            signals.append(f"resting HR at least {RULES['resting-hr']['parameters']['threshold']:g} bpm above baseline")
    for field, threshold, direction, label in (
        ("sleep_hours", RULES["sleep"]["parameters"]["threshold"], "below", f"sleep below {RULES['sleep']['parameters']['threshold']:g} h"),
        ("fatigue", RULES["fatigue"]["parameters"]["threshold"], "above", f"fatigue at least {RULES['fatigue']['parameters']['threshold']:g}/10"),
        ("soreness", RULES["soreness"]["parameters"]["threshold"], "above", f"soreness at least {RULES['soreness']['parameters']['threshold']:g}/10"),
    ):
        value = current.get(field)
        if value is not None:
            reasons.append(f"{field.replace('_', ' ')}: {value:g}{' h' if field == 'sleep_hours' else '/10'}.")
            if value < threshold if direction == "below" else value >= threshold:
                signals.append(label)
    change = features["load_change_pct"]
    if change is not None:
        reasons.append(f"7-day load is {change:+.1f}% vs preceding 4-week weekly average.")
        if change > RULES["weekly-load"]["parameters"]["threshold"]:
            signals.append(f"weekly load more than {RULES['weekly-load']['parameters']['threshold']:g}% above baseline")
    readiness = round(statistics.mean(components.values())) if len(components) >= scoring["minimum_components"] else None
    if len(signals) >= scoring["protect_signals"]:
        mode = "PROTECT"
    elif len(signals) >= scoring["recover_signals"] or (readiness is not None and readiness < scoring["recover_score_below"]):
        mode = "RECOVER"
    elif readiness is None:
        mode = "INSUFFICIENT"
    elif readiness < scoring["build_score_at_least"] or len(signals) == 1:
        mode = "MAINTAIN"
    else:
        mode = "BUILD"
    if readiness is None:
        reasons.append(f"At least {scoring['minimum_components']} available recovery components are needed for a demo readiness estimate.")
    observations = []
    resting_change = resting - baseline if resting is not None and baseline is not None else None
    for rule_id, value, quality_key in (
        ("sleep", current.get("sleep_hours"), None), ("fatigue", current.get("fatigue"), None),
        ("soreness", current.get("soreness"), None), ("hrv", hrv_change, "hrv"),
        ("resting-hr", resting_change, "resting_hr"), ("weekly-load", change, "weekly_load"),
    ):
        parameters = RULES[rule_id]["parameters"]
        operator, threshold = parameters["operator"], parameters["threshold"]
        crossed = None if value is None else value < threshold if operator == "<" else value > threshold if operator == ">" else value >= threshold
        observations.append({"rule_id": rule_id, "value": value, "unit": parameters["unit"],
                             "operator": operator, "threshold": threshold, "crossed": crossed,
                             "threshold_status": "provisional",
                             "comparability": features["baseline_quality"][quality_key]["comparability"] if quality_key else "unknown-assessment-protocol"})
    return {"contract_version": 1, "prediction_source": PREDICTION_SOURCE, "rule_version": RULE_VERSION,
            "readiness_score": readiness, "fatigue_index": 100 - readiness if readiness is not None else None,
            "mode": mode, "overload_pattern": "Multiple signals" if len(signals) >= 2 else "Single signal" if signals else
            "Insufficient recovery evidence" if readiness is None else "No observed threshold crossings",
            "signals": signals, "reasons": reasons, "component_scores": components,
            "observed_signals": observations, "evidence_status": "provisional-product-heuristic",
            "monitoring_review": monitoring_review(features, observations),
            "trace": trace(["sleep", "fatigue", "soreness", "hrv", "resting-hr", "weekly-load", "readiness", "dose", "monitoring-review"]),
            "limitations": "Uncalibrated demo heuristic; variable/method evidence does not validate these exact cuts. Not medical advice, injury prediction, a confidence probability or a trained model."}


def recommend(session, prediction):
    mode = prediction["mode"]
    dose = RULES["dose"]["parameters"]
    factor = {"PROTECT": dose["protect_factor"], "RECOVER": dose["recover_factor"], "MAINTAIN": 1, "BUILD": 1, "INSUFFICIENT": 1}[mode]
    duration = round(session["duration_min"] * factor, 1)
    rpe = min(session["session_rpe"], dose["protect_rpe_cap"] if mode == "PROTECT" else dose["recover_rpe_cap"]) if factor < 1 else session["session_rpe"]
    adjusted = factor < 1 and session["duration_min"] > 0
    return {"duration_min": duration, "session_rpe": rpe, "load_au": duration * rpe,
            "adjusted": adjusted, "rule_version": RULE_VERSION, "evidence_status": "provisional-product-heuristic",
            "title": "Gentle recovery walk" if adjusted else session["title"],
            "sport_type": "walk" if adjusted else session["sport_type"],
            "explanation": "Consider this provisional reduction and reassess your response with your coach; no prevention benefit is established." if adjusted else
            "No automatic adjustment: insufficient recovery evidence. Add a check-in first." if mode == "INSUFFICIENT" else
            "Keep the planned dose; rest remains part of your goal."}


def demo_state(today):
    athletes = []
    for athlete_id, name, focus, stressed in (
        ("demo-alex", "Alex Rivera", "Marathon build", False),
        ("demo-sam", "Sam Chen", "Recovery focus", True),
    ):
        records = []
        for i in range(35):
            day, pattern = today - timedelta(days=34 - i), i % 7
            sport = "rest" if pattern == 0 else "strength" if pattern in (2, 5) else "run"
            duration = 0 if sport == "rest" else 35 if sport == "strength" else 40 + pattern * 5
            raw = dict.fromkeys(FIELDS, "")
            raw.update(athlete_id=athlete_id, timestamp=f"{day}T08:00:00+00:00", timezone="UTC",
                       sport_type=sport, duration_min=duration, session_rpe=0 if sport == "rest" else 4,
                       distance_km=round(duration / (5.6 - i * 0.003), 3) if sport == "run" else 0,
                       resting_hr_bpm=54 + i % 3, hrv_ms=60 + i % 5,
                       sleep_hours=7.8, fatigue=2, soreness=2, stress=3)
            if sport == "run":
                raw.update(avg_hr_bpm=142, max_hr_bpm=190, elevation_m=35)
            if sport == "strength":
                raw.update(exercise="Squat" if pattern == 2 else "Row",
                           muscle_group="legs" if pattern == 2 else "pull",
                           sets=3, reps=8, load_kg=40 if pattern == 2 else 25, rir=3)
            if stressed and i >= 28:
                raw.update(sleep_hours=5.4, fatigue=8, soreness=7, hrv_ms=43, resting_hr_bpm=65)
            record = normalized_record(raw, athlete_id, today)
            record.update(source="Synthetic demo", recovery_source="Synthetic demo")
            records.append(record)
        plan = []
        for i in range(7):
            day, sport = today + timedelta(days=i), "rest" if i == 3 else "run"
            plan.append({"date": str(day), "title": "Rest & recharge" if sport == "rest" else
                         "Long aerobic run" if i == 6 else "Easy aerobic run",
                         "sport_type": sport, "duration_min": 0 if sport == "rest" else 80 if i == 6 else 45,
                         "session_rpe": 0 if sport == "rest" else 4, "key": i in (0, 2, 6)})
        athletes.append({"id": athlete_id, "name": name, "focus": focus, "timezone": "UTC",
                         "goal": {"goal_type": "Marathon", "goal_date": str(today + timedelta(days=112)),
                                  "target_time_min": 240, "secondary": "Consistent recovery and balanced strength"},
                         "records": records, "plan": plan, "wins": [], "completions": [],
                         "adjustments": {}, "checkins": {}})
    return {"version": 1, "athletes": athletes}
