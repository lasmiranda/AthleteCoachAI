"""Local-only HTTP API and atomic, durable JSON storage. No external services."""

import argparse
import copy
import csv
import io
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from athleteos.domain import (FIELDS, METADATA_FIELDS, RECOVERY_FIELDS, SPORTS, ValidationError,
                             calculate_features, demo_state, iso_date,
                             measurement_metadata, normalized_record, number, parse_csv, predict_demo,
                             recommend, zone)
from athleteos.evidence import PREDICTION_SOURCE, RULES, RULE_VERSION, digest, manifest, trace

ROOT = Path(__file__).resolve().parent.parent
LOG = logging.getLogger("athleteos")
STRENGTH_FIELDS = ("exercise", "muscle_group", "sets", "reps", "load_kg", "rir")


class Store:
    def __init__(self, path, today=None):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.clock = today
        if self.path.exists():
            original = self.path.read_bytes()
            self.state = json.loads(original.decode("utf-8"))
            if self.state.get("version") not in (1, 2) or not isinstance(self.state.get("athletes"), list):
                raise ValueError("Unsupported/corrupt store. Restore a backup; data was not reset.")
            if self.state["version"] == 1:
                backup = self.path.with_suffix(".v1-backup.json")
                if backup.exists() and backup.read_bytes() != original:
                    backup = self.path.with_suffix(f".v1-backup-{uuid.uuid4().hex}.json")
                if not backup.exists():
                    with backup.open("xb") as stream:
                        stream.write(original)
                        stream.flush()
                        os.fsync(stream.fileno())
                migrated = self.upgrade(self.state)
                self.save(migrated)
                self.state = migrated
        else:
            self.state = demo_state(self.day())
            blank = copy.deepcopy(self.state["athletes"][0])
            blank.update(id="demo-new", name="Your demo athlete", focus="Start with your own CSV",
                         records=[], wins=[], completions=[], adjustments={}, checkins={})
            self.state["athletes"].append(blank)
            self.state = self.upgrade(self.state)
            self.save(self.state)

    @staticmethod
    def upgrade(state):
        upgraded = copy.deepcopy(state)
        upgraded["version"] = 2
        for athlete in upgraded["athletes"]:
            athlete.setdefault("decision_snapshots", [])
            athlete.setdefault("decision_outcomes", [])
            for record in athlete["records"]:
                for field in METADATA_FIELDS:
                    record.setdefault(field, None)
            for item in athlete["completions"]:
                item.setdefault("decision_id", None)
                item.setdefault("trace_status", "legacy-unrecorded")
            for item in athlete["adjustments"].values():
                item.setdefault("decision_id", None)
                item.setdefault("trace_status", "legacy-unrecorded")
            for item in athlete["wins"]:
                item.setdefault("trace_status", "legacy-unrecorded")
        return upgraded

    def day(self, athlete=None):
        return self.clock or datetime.now(zone(athlete["timezone"] if athlete else "UTC")).date()

    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(state, stream, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    @staticmethod
    def athlete(state, athlete_id):
        for athlete in state["athletes"]:
            if athlete["id"] == athlete_id:
                return athlete
        raise ValidationError("Unknown athlete.")

    def summary(self):
        with self.lock:
            return [{"id": a["id"], "name": a["name"], "focus": a["focus"]}
                    for a in self.state["athletes"]]

    def view(self, athlete_id):
        with self.lock:
            athlete = copy.deepcopy(self.athlete(self.state, athlete_id))
        today = self.day(athlete)
        features = calculate_features(athlete["records"], today, athlete["checkins"].get(str(today)))
        prediction = predict_demo(features)
        session = next((s for s in athlete["plan"] if s["date"] == str(today)), None)
        if session is None:
            session = {"date": str(today), "title": "No session scheduled", "sport_type": "rest",
                       "duration_min": 0, "session_rpe": 0, "key": False}
        elapsed = [s for s in athlete["plan"] if s["date"] <= str(today)]
        on_plan = {c["date"] for c in athlete["completions"] if c["on_plan"]}
        adherence = round(sum(s["date"] in on_plan for s in elapsed) / len(elapsed) * 100) if elapsed else None
        athlete["decision_snapshots"] = [
            {"id": s["id"], "as_of": s["as_of"], "trigger": s["trigger"],
             "captured_at": s["captured_at"], "rule_version": s["rule_version"],
             "mode": s["prediction"]["mode"], "recommendation": s["recommendation"],
             "input_digest": s["input_digest"]} for s in athlete["decision_snapshots"]]
        return {"athlete": athlete, "features": features, "prediction": prediction,
                "today_session": session, "recommendation": recommend(session, prediction),
                "today": str(today), "adherence_pct": adherence,
                "scheduled_today": any(s["date"] == str(today) for s in athlete["plan"]),
                "goal_days_remaining": (iso_date(athlete["goal"]["goal_date"]) - today).days,
                "evidence": manifest()}

    def decisions(self, athlete_id):
        with self.lock:
            athlete = self.athlete(self.state, athlete_id)
            return copy.deepcopy({"schema_version": 2, "snapshots": athlete["decision_snapshots"],
                                  "outcomes": athlete["decision_outcomes"],
                                  "limitations": "Only recorded session values and dose adherence are outcomes. Legacy decisions are not reconstructed; no physiological, injury or confidence outcome is inferred."})

    def export_csv(self, athlete_id):
        with self.lock:
            athlete = copy.deepcopy(self.athlete(self.state, athlete_id))
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=FIELDS + METADATA_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(athlete["records"])
        return output.getvalue().encode("utf-8")

    @staticmethod
    def validate_plan(payload, athlete, today):
        plan_date = iso_date(payload.get("date"))
        if not today <= plan_date <= today + timedelta(days=365):
            raise ValidationError("Plan date must be today or within the next year.")
        title = payload.get("title", "")
        sport = payload.get("sport_type")
        if not isinstance(title, str) or not title.strip() or len(title) > 80:
            raise ValidationError("Session title must contain 1-80 characters.")
        if not isinstance(sport, str) or sport not in SPORTS:
            raise ValidationError("Choose a supported sport.")
        if not isinstance(payload.get("key", False), bool):
            raise ValidationError("key must be boolean.")
        raw = dict.fromkeys(FIELDS, "")
        raw.update(athlete_id=athlete["id"], timestamp=f"{today}T12:00:00+00:00",
                   timezone=athlete["timezone"], sport_type=sport,
                   duration_min=payload.get("duration_min"), session_rpe=payload.get("session_rpe"))
        for field in STRENGTH_FIELDS:
            raw[field] = payload.get(field)
        record = normalized_record(raw, athlete["id"], today)
        return {"date": str(plan_date), "title": title.strip(), "sport_type": sport,
                "duration_min": record["duration_min"], "session_rpe": record["session_rpe"],
                "key": payload.get("key", False),
                **{field: record[field] for field in STRENGTH_FIELDS}}

    def mutate(self, athlete_id, action, payload):
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be an object.")
        with self.lock:
            candidate = copy.deepcopy(self.state)
            athlete = self.athlete(candidate, athlete_id)
            today = self.day(athlete)
            if action == "goal":
                allowed = {"Marathon", "Half marathon", "10K", "Strength", "General fitness"}
                goal_type = payload.get("goal_type")
                if not isinstance(goal_type, str) or goal_type not in allowed:
                    raise ValidationError("Choose a supported goal type.")
                goal_date = iso_date(payload.get("goal_date"))
                if not today < goal_date <= today + timedelta(days=1095):
                    raise ValidationError("Goal date must be in the next 3 years.")
                target = payload.get("target_time_min")
                if target not in (None, ""):
                    if isinstance(target, bool) or not isinstance(target, (int, float)) or not 1 <= target <= 1440:
                        raise ValidationError("target_time_min must be 1-1440 minutes or blank.")
                secondary = payload.get("secondary", "")
                if not isinstance(secondary, str) or len(secondary) > 200:
                    raise ValidationError("Secondary priority must be at most 200 characters.")
                athlete["goal"] = {"goal_type": goal_type, "goal_date": str(goal_date),
                                   "target_time_min": target if target != "" else None, "secondary": secondary}
                athlete["adjustments"].pop(str(today), None)
            elif action == "plan":
                session = self.validate_plan(payload, athlete, today)
                if any(c["date"] == session["date"] for c in athlete["completions"]):
                    raise ValidationError("Completed sessions cannot be edited.")
                athlete["plan"] = sorted([s for s in athlete["plan"] if s["date"] != session["date"]] + [session],
                                         key=lambda s: s["date"])
                athlete["adjustments"].pop(session["date"], None)
            elif action == "checkin":
                if not any(payload.get(f) not in (None, "") for f in RECOVERY_FIELDS):
                    raise ValidationError("Enter at least one measured or self-reported value.")
                values = {f: number(payload.get(f), f) for f in RECOVERY_FIELDS}
                values.update(measurement_metadata(payload, values))
                athlete["checkins"][str(today)] = values
                # A check-in alone is not evidence of training or of a rest day.
                current = next((r for r in athlete["records"] if r["date"] == str(today)), None)
                if current:
                    current.update(values)
                    current["recovery_source"] = "App check-in"
                athlete["adjustments"].pop(str(today), None)
            elif action == "import":
                records = parse_csv(payload.get("csv"), athlete_id, today)
                if any(r["timezone"] != athlete["timezone"] for r in records):
                    raise ValidationError(f"CSV timezone must match this demo athlete: {athlete['timezone']}.")
                replaced = {r["date"] for r in records}
                if any(c["date"] in replaced for c in athlete["completions"]):
                    raise ValidationError("Import overlaps completed sessions. Keep their recorded history intact.")
                athlete["records"] = sorted([r for r in athlete["records"] if r["date"] not in replaced] + records,
                                            key=lambda r: r["date"])
                for day in replaced:
                    athlete["checkins"].pop(day, None)
                    athlete["adjustments"].pop(day, None)
            elif action in {"accept", "complete"}:
                features = calculate_features(athlete["records"], today, athlete["checkins"].get(str(today)))
                prediction = predict_demo(features)
                session = next((s for s in athlete["plan"] if s["date"] == str(today)), None)
                if session is None:
                    raise ValidationError("Add today's session to the plan first.")
                if any(c["date"] == str(today) for c in athlete["completions"]):
                    raise ValidationError("Today's session is already recorded.")
                adapted = recommend(session, prediction)
                if action == "accept":
                    if not adapted["adjusted"]:
                        raise ValidationError("There is no calculated adjustment to accept.")
                    decision_id = self.snapshot(athlete, today, "accepted", features, prediction, session, adapted)
                    athlete["adjustments"][str(today)] = {
                        "recommendation": adapted, "mode": prediction["mode"],
                        "signals": prediction["signals"], "accepted_at": datetime.now(timezone.utc).isoformat(),
                        "decision_id": decision_id, "trace_status": "recorded", "rule_version": RULE_VERSION}
                    self.win(athlete, "smart-" + str(today), "Smart Training", "Smart Decisions",
                             "Accepted a calculated reduction grounded in recovery signals.", today)
                else:
                    self.complete(athlete, session, adapted, prediction, payload, today)
            elif action == "snapshot":
                self.snapshot_current(athlete, today, "reviewed")
            else:
                raise ValidationError("Unknown action.")
            if action in {"goal", "plan", "checkin", "import"}:
                self.snapshot_current(athlete, today, f"recalculated-after-{action}")
            self.save(candidate)
            self.state = candidate
        return self.view(athlete_id)

    @staticmethod
    def snapshot(athlete, today, trigger, features, prediction, session, recommendation):
        inputs = {"records": [copy.deepcopy(r) for r in athlete["records"]
                              if today - timedelta(days=34) <= iso_date(r["date"]) <= today],
                  "checkin": copy.deepcopy(athlete["checkins"].get(str(today))),
                  "goal": copy.deepcopy(athlete["goal"]), "session": copy.deepcopy(session),
                  "scheduled_today": any(s["date"] == str(today) for s in athlete["plan"])}
        snapshot = {"id": str(uuid.uuid4()), "as_of": str(today), "trigger": trigger,
                    "captured_at": datetime.now(timezone.utc).isoformat(), "rule_version": RULE_VERSION,
                    "prediction_source": prediction["prediction_source"], "inputs": inputs,
                    "input_digest": digest(inputs), "features": copy.deepcopy(features),
                    "prediction": copy.deepcopy(prediction), "recommendation": copy.deepcopy(recommendation),
                    "evidence_manifest": manifest()}
        snapshot["evidence_digest"] = digest(snapshot["evidence_manifest"])
        athlete["decision_snapshots"].append(snapshot)
        return snapshot["id"]

    def snapshot_current(self, athlete, today, trigger):
        features = calculate_features(athlete["records"], today, athlete["checkins"].get(str(today)))
        prediction = predict_demo(features)
        session = next((s for s in athlete["plan"] if s["date"] == str(today)), None)
        if session is None:
            session = {"date": str(today), "title": "No session scheduled", "sport_type": "rest",
                       "duration_min": 0, "session_rpe": 0, "key": False}
        return self.snapshot(athlete, today, trigger, features, prediction, session, recommend(session, prediction))

    def complete(self, athlete, session, adapted, prediction, payload, today):
        chosen = athlete["adjustments"].get(str(today))
        if adapted["adjusted"] and chosen is None:
            raise ValidationError("Accept today's recovery adjustment before recording the session.")
        dose = chosen["recommendation"] if chosen else adapted
        actual_duration = number(payload.get("duration_min"), "duration_min", True)
        actual_rpe = number(payload.get("session_rpe"), "session_rpe", True)
        raw = dict.fromkeys(FIELDS, "")
        raw.update(athlete_id=athlete["id"], timestamp=f"{today}T12:00:00+00:00",
                   timezone=athlete["timezone"], sport_type=dose["sport_type"],
                   duration_min=actual_duration, session_rpe=actual_rpe,
                   distance_km=payload.get("distance_km"))
        for field in STRENGTH_FIELDS:
            raw[field] = payload.get(field)
        existing = next((r for r in athlete["records"] if r["date"] == str(today)), None)
        for field in RECOVERY_FIELDS:
            raw[field] = athlete["checkins"].get(str(today), existing or {}).get(field)
        for field in METADATA_FIELDS:
            raw[field] = athlete["checkins"].get(str(today), existing or {}).get(field)
        record = normalized_record(raw, athlete["id"], today)
        record.update(source="App session log", recovery_source="App check-in" if str(today) in athlete["checkins"] else
                      (existing or {}).get("recovery_source", "Missing"))
        decision_id = chosen.get("decision_id") if chosen else self.snapshot_current(athlete, today, "logged-from-current")
        prior = [r for r in athlete["records"] if r["date"] < str(today)]
        athlete["records"] = sorted([r for r in athlete["records"] if r["date"] != str(today)] + [record],
                                    key=lambda r: r["date"])
        within_dose = (actual_duration * actual_rpe <= dose["load_au"]
                       and actual_duration <= dose["duration_min"] and actual_rpe <= dose["session_rpe"])
        if record["sport_type"] == "strength":
            actual_volume = record["sets"] * record["reps"] * record["load_kg"]
            planned_volume = session["sets"] * session["reps"] * session["load_kg"]
            within_dose = within_dose and actual_volume <= planned_volume and record["sets"] <= session["sets"]
        win_parameters = RULES["wins"]["parameters"]
        completion = {"date": str(today), "duration_min": actual_duration,
                      "session_rpe": actual_rpe, "adapted": chosen is not None,
                      "within_dose": within_dose, "mode_at_completion": prediction["mode"],
                      "key": session["key"],
                      "decision_id": decision_id, "trace_status": "recorded" if decision_id else "legacy-unrecorded",
                      "rule_version": RULE_VERSION if decision_id else None,
                      "on_plan": within_dose and actual_duration >= dose["duration_min"] * win_parameters["minimum_adherence"]}
        athlete["completions"].append(completion)
        athlete["decision_outcomes"].append({
            **copy.deepcopy(completion), "recorded_at": datetime.now(timezone.utc).isoformat(),
            "actual_load_au": actual_duration * actual_rpe, "actual_distance_km": record["distance_km"],
            "actual_strength_volume_kg": record["sets"] * record["reps"] * record["load_kg"] if record["sets"] is not None else None,
            "chosen_dose": copy.deepcopy(dose),
            "limitations": "Session dose adherence only; no physiological response, injury reduction or future performance inferred."})
        if chosen and within_dose:
            self.win(athlete, "recovery-" + str(today), "Recovery Win", "Recovery",
                     "Completed the accepted recovery dose without exceeding duration, RPE or sRPE load.", today)
        keys = [c for c in athlete["completions"] if c["key"] and c["on_plan"]]
        if len(keys) >= win_parameters["key_sessions"]:
            self.win(athlete, "consistency-3", "Consistency Win", "Consistency",
                     "Recorded three key sessions within 80-100% of planned duration and without excess RPE or load.", today)
        elapsed = [s for s in athlete["plan"] if s["date"] <= str(today)]
        on_plan = {c["date"] for c in athlete["completions"] if c["on_plan"]}
        if len(elapsed) >= win_parameters["milestone_days"] and sum(s["date"] in on_plan for s in elapsed) / len(elapsed) >= win_parameters["minimum_adherence"]:
            self.win(athlete, "milestone-5", "Goal Progress Win", "Consistency",
                     "Reached the first plan milestone: at least 80% on-plan adherence over 5 scheduled days.", today)
        previous_days = {r["date"]: r for r in prior}
        if all(previous_days.get(str(today - timedelta(days=i)), {}).get("sport_type") == "rest" for i in range(1, win_parameters["rest_days"] + 1)):
            if dose["sport_type"] != "rest" and within_dose and prediction["mode"] in {"BUILD", "MAINTAIN"}:
                self.win(athlete, "comeback-" + str(today), "Comeback Win", "Consistency",
                         "Returned within the planned dose after two explicitly recorded rest days.", today)
        if record["sport_type"] == "strength" and within_dose and prediction["mode"] in {"BUILD", "MAINTAIN"}:
            week = calculate_features(athlete["records"], today)
            sets = week["direct_sets_by_muscle"]
            if sets and sum(count >= win_parameters["minimum_direct_sets"] for count in sets.values()) >= win_parameters["muscle_groups"] and all(count <= win_parameters["maximum_direct_sets"] for count in sets.values()):
                self.win(athlete, "balance-" + str(today), "Strength Balance", "Strength",
                         "At least 3 direct sets in two muscle groups this week, no group above 12; today's dose was not exceeded.", today)
        pace_parameters = RULES["pace"]["parameters"]
        if record["sport_type"] == "run" and (record["distance_km"] or 0) >= pace_parameters["minimum_distance_km"] and pace_parameters["rpe_low"] <= actual_rpe <= pace_parameters["rpe_high"]:
            matches = [r for r in prior if today - timedelta(days=28) <= iso_date(r["date"])
                       and r["sport_type"] == "run" and r["session_rpe"] == actual_rpe
                       and r["distance_km"] is not None
                       and abs(r["distance_km"] - record["distance_km"]) <= record["distance_km"] * win_parameters["distance_tolerance"]]
            if len(matches) >= win_parameters["comparable_runs"] and prediction["mode"] in {"BUILD", "MAINTAIN"} and within_dose:
                baseline = sum(r["duration_min"] / r["distance_km"] for r in matches) / len(matches)
                if record["duration_min"] / record["distance_km"] <= baseline * (1 - win_parameters["pace_improvement"]):
                    self.win(athlete, "adaptation-" + str(today), "Adaptation Win", "Performance",
                             "Recorded pace at least 2% faster than 3+ prior runs at identical RPE and distance within 10%; terrain is not controlled.", today)

    @staticmethod
    def win(athlete, win_id, title, category, reason, today):
        if not any(w["id"] == win_id for w in athlete["wins"]):
            athlete["wins"].append({"id": win_id, "title": title, "category": category,
                                   "reason": reason, "date": str(today), "goal_type": athlete["goal"]["goal_type"],
                                   "rule_version": RULE_VERSION, "trace_status": "recorded", "evidence_status": "provisional-motivation-rule"})

    def coach(self, athlete_id, topic):
        view = self.view(athlete_id)
        f, p = view["features"], view["prediction"]
        if topic == "readiness":
            answer = f"Today's mode is {p['mode']}. " + " ".join(p["reasons"])
        elif topic == "plan":
            r = view["recommendation"]
            answer = f"Your {view['athlete']['goal']['goal_type']} goal has {view['goal_days_remaining']} days remaining. Suggested dose: {r['duration_min']:g} min at RPE {r['session_rpe']:g}, {r['load_au']:g} AU. {r['explanation']}"
        elif topic == "load":
            answer = (f"7-day sRPE load is {f['weekly_load_au']:g} AU. " if f["weekly_load_au"] is not None else
                      f"Only {f['week_days_observed']}/7 activity days are observed; full weekly load is unavailable. ")
            answer += "sRPE = minutes x session RPE. " + (f"Monotony is {f['monotony_ratio']:.2f}." if f["monotony_ratio"] is not None else "Monotony is unavailable; see data-quality notes.")
        elif topic == "overload":
            review = p["monitoring_review"]
            answer = review["summary"] + " Observations: " + "; ".join(
                f"{RULES[s['rule_id']]['title']}: "
                + (f"{s['value']:+.1f} {s['unit']}" if s["value"] is not None else "unavailable")
                + f" (comparability {s['comparability']})" for s in p["observed_signals"])
            answer += ". " + review["criterion"] + " " + review["review_action"] + " " + review["limitations"]
            answer += " Provisional cuts: " + "; ".join(
                f"{RULES[s['rule_id']]['title']} {s['operator']} {s['threshold']:g} {s['unit']}"
                + (" (not evaluated)" if s["crossed"] is None else " (crossed)" if s["crossed"] else " (no crossing)")
                for s in p["observed_signals"]) + "."
            r = view["recommendation"]
            answer += f" Suggested dose: {r['duration_min']:g} min at RPE {r['session_rpe']:g}; {r['explanation']}"
        elif topic == "strength":
            answer = (f"Recorded 7-day volume is {f['strength_volume_kg']:g} kg-repetitions. " if f["strength_volume_kg"] is not None else "Weekly strength volume is unavailable. ")
            answer += "Only recorded direct sets count; indirect sets are not estimated. Epley estimates use sets with 1-10 reps and positive weight, per exercise. None of these measures demonstrates muscle growth."
        elif topic == "wins":
            answer = f"You have {len(view['athlete']['wins'])} verified Micro Wins. Accepting a calculated reduction earns Smart Training; completing it within duration, RPE and load ceilings earns Recovery Win. Rest has no punitive streak."
        else:
            raise ValidationError("Choose readiness, plan, load, overload, strength or wins.")
        topics = {"readiness": ["sleep", "fatigue", "soreness", "hrv", "resting-hr", "readiness"],
                  "plan": ["readiness", "dose"], "load": ["srpe", "weekly-load"],
                  "overload": ["srpe", "weekly-load", "sleep", "fatigue", "soreness", "hrv", "resting-hr", "monitoring-review", "readiness", "dose"],
                  "strength": ["strength-volume", "epley", "wins"], "wins": ["wins"]}
        explanation_trace = trace(topics[topic])
        answer += f" Product rule version: {RULE_VERSION}. Exact decision/reward thresholds remain provisional; supporting a variable or method does not validate this recommendation."
        if topic == "readiness":
            for label, quality in (("HRV", f["baseline_quality"]["hrv"]), ("Resting HR", f["baseline_quality"]["resting_hr"])):
                answer += f" {label}: {quality['used_count']}/{quality['observation_count']} observations used, {quality['status']}, comparability {quality['comparability']}; SD/CV are descriptive, not significance or confidence."
        if topic in {"readiness", "load", "plan"}:
            review = p["monitoring_review"]
            answer += " " + review["summary"] + " " + review["review_action"] + " " + review["limitations"]
            explanation_trace = trace([*topics[topic], "monitoring-review"])
        return {"answer": answer, "source": p["prediction_source"], "as_of": view["today"],
                "disclaimer": p["limitations"], "trace": explanation_trace,
                "baseline_quality": f["baseline_quality"], "monitoring_review": p["monitoring_review"]}


class Handler(BaseHTTPRequestHandler):
    store = None

    def send(self, status, content, content_type="application/json; charset=utf-8"):
        data = json.dumps(content, allow_nan=False).encode() if content_type.startswith("application/json") else content
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def local_request(self):
        port = self.server.server_address[1]
        if self.headers.get("Host") not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            self.send(403, {"error": "Only a local loopback Host is permitted."})
            return False
        return True

    def do_GET(self):
        if not self.local_request():
            return
        path = urlsplit(self.path).path
        try:
            if path == "/api/health":
                return self.send(200, {"status": "ok", "predictor": PREDICTION_SOURCE, "rule_version": RULE_VERSION})
            if path == "/api/athletes":
                return self.send(200, self.store.summary())
            if path == "/api/evidence":
                return self.send(200, manifest())
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["api", "athletes"]:
                return self.send(200, self.store.view(parts[2]))
            if len(parts) == 4 and parts[:2] == ["api", "athletes"] and parts[3] == "export":
                return self.send(200, self.store.export_csv(parts[2]), "text/csv; charset=utf-8")
            if len(parts) == 4 and parts[:2] == ["api", "athletes"] and parts[3] == "decisions":
                return self.send(200, self.store.decisions(parts[2]))
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8"),
                      "/favicon.svg": ("favicon.svg", "image/svg+xml"),
                      "/sample.csv": ("sample.csv", "text/csv; charset=utf-8")}
            if path in assets:
                filename, content_type = assets[path]
                return self.send(200, (ROOT / "web" / filename).read_bytes(), content_type)
            self.send(404, {"error": "Not found."})
        except ValidationError as error:
            self.send(400, {"error": str(error)})
        except (OSError, ValueError, KeyError, TypeError):
            LOG.exception("Failed GET %s", path)
            self.send(500, {"error": "Server could not read local data. See server log."})

    def do_POST(self):
        if not self.local_request():
            return
        path = urlsplit(self.path).path
        try:
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://{self.headers.get('Host')}":
                return self.send(403, {"error": "Cross-origin writes are not allowed."})
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self.send(415, {"error": "Use application/json."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValidationError("Invalid Content-Length.") from None
            if not 0 < length <= 2_000_000:
                return self.send(413, {"error": "Body must be 1-2,000,000 bytes."})
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"), parse_constant=invalid_constant)
            except (UnicodeDecodeError, ValueError):
                raise ValidationError("Body must be valid UTF-8 JSON with finite numbers.") from None
            if not isinstance(payload, dict):
                raise ValidationError("Body must be an object.")
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "athletes"]:
                return self.send(404, {"error": "Not found."})
            result = self.store.coach(parts[2], payload.get("topic")) if parts[3] == "coach" else self.store.mutate(parts[2], parts[3], payload)
            self.send(200, result)
        except ValidationError as error:
            self.send(400, {"error": str(error)})
        except (OSError, ValueError, KeyError, TypeError):
            LOG.exception("Failed POST %s", path)
            self.send(500, {"error": "Changes could not be processed or saved. See server log; no success was reported."})


def invalid_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def main():
    parser = argparse.ArgumentParser(description="Run AthleteOS locally.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data", type=Path, default=ROOT / ".athleteos" / "state.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    Handler.store = Store(args.data)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"AthleteOS: http://127.0.0.1:{args.port} (local-only, Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
