import copy
import json
import tempfile
import threading
import unittest
from datetime import date, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from athleteos.domain import ValidationError, parse_csv
from athleteos.server import Handler, Store
from test_domain import TODAY, csv_text


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.store = Store(self.path, today=TODAY)

    def test_goal_checkin_plan_import_and_wins_persist_after_restart(self):
        self.store.mutate("demo-sam", "goal", {
            "goal_type": "10K", "goal_date": str(TODAY + timedelta(days=90)),
            "target_time_min": 55, "secondary": "Recovery first"})
        self.store.mutate("demo-sam", "checkin", {
            "sleep_hours": 5, "fatigue": 8, "soreness": 8, "stress": 6, "hrv_ms": 40, "resting_hr_bpm": 65})
        self.store.mutate("demo-sam", "accept", {})
        result = self.store.mutate("demo-sam", "complete", {"duration_min": 18, "session_rpe": 2})
        self.assertEqual({w["title"] for w in result["athlete"]["wins"]}, {"Smart Training", "Recovery Win"})
        reloaded = Store(self.path, today=TODAY).view("demo-sam")
        self.assertEqual(reloaded, result)
        self.assertEqual(reloaded["athlete"]["goal"]["goal_type"], "10K")
        self.assertEqual(reloaded["features"]["current"]["source"], "App session log")
        self.assertIsNone(reloaded["features"]["current"]["distance_km"])
        with self.assertRaises(ValidationError):
            self.store.mutate("demo-sam", "complete", {"duration_min": 18, "session_rpe": 2})

    def test_checkin_only_is_persistent_but_not_an_activity(self):
        self.store.mutate("demo-new", "checkin", {"sleep_hours": 8, "fatigue": 2, "stress": 2})
        v = Store(self.path, today=TODAY).view("demo-new")
        self.assertEqual(len(v["athlete"]["records"]), 0)
        self.assertEqual(v["prediction"]["mode"], "BUILD")
        self.assertIsNone(v["features"]["weekly_load_au"])

    def test_accept_is_required_and_excess_dose_does_not_earn_recovery_win(self):
        with self.assertRaisesRegex(ValidationError, "Accept"):
            self.store.mutate("demo-sam", "complete", {"duration_min": 18, "session_rpe": 2})
        self.store.mutate("demo-sam", "accept", {})
        v = self.store.mutate("demo-sam", "complete", {"duration_min": 30, "session_rpe": 5})
        self.assertEqual([w["title"] for w in v["athlete"]["wins"]], ["Smart Training"])
        self.assertFalse(v["athlete"]["completions"][0]["on_plan"])

    def test_accept_is_deduplicated_and_checkin_invalidates_pending_adjustment(self):
        self.store.mutate("demo-sam", "accept", {})
        v = self.store.mutate("demo-sam", "accept", {})
        self.assertEqual(len(v["athlete"]["wins"]), 1)
        self.store.mutate("demo-sam", "checkin", {"sleep_hours": 5, "fatigue": 8, "soreness": 8})
        with self.assertRaisesRegex(ValidationError, "Accept"):
            self.store.mutate("demo-sam", "complete", {"duration_min": 18, "session_rpe": 2})

    def test_blank_checkin_values_clear_old_measurements(self):
        v = self.store.mutate("demo-alex", "checkin", {"fatigue": 2})
        self.assertIsNone(v["features"]["current"]["sleep_hours"])
        self.assertIsNone(v["features"]["hrv_change_pct"])
        self.assertIsNone(v["prediction"]["readiness_score"])
        with self.assertRaises(ValidationError):
            self.store.mutate("demo-alex", "checkin", {})

    def test_import_all_or_nothing_and_date_replacement(self):
        records = self.store.view("demo-alex")["athlete"]["records"]
        invalid = copy.deepcopy(records[:2])
        invalid[1]["duration_min"] = -1
        before = self.path.read_bytes()
        with self.assertRaises(ValidationError):
            self.store.mutate("demo-alex", "import", {"csv": csv_text(invalid)})
        self.assertEqual(self.path.read_bytes(), before)
        records[1]["duration_min"] = 50
        v = self.store.mutate("demo-alex", "import", {"csv": csv_text(records[:2])})
        self.assertEqual(len(v["athlete"]["records"]), 35)
        self.assertEqual(v["athlete"]["records"][1]["duration_min"], 50)
        self.assertEqual(v["athlete"]["records"][1]["source"], "CSV import")
        exported = self.store.export_csv("demo-alex").decode()
        self.assertEqual(len(parse_csv(exported, "demo-alex", TODAY)), 35)
        self.assertEqual(Store(self.path, today=TODAY).view("demo-alex"), v)

    def test_write_failure_rolls_back_in_memory_and_does_not_report_success(self):
        before = self.store.view("demo-alex")
        with patch.object(self.store, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.mutate("demo-alex", "checkin", {"fatigue": 3})
        self.assertEqual(self.store.view("demo-alex"), before)
        self.assertEqual(Store(self.path, today=TODAY).view("demo-alex"), before)

    def test_corrupt_store_does_not_silently_reset(self):
        self.path.write_text("{broken")
        with self.assertRaises(json.JSONDecodeError):
            Store(self.path, today=TODAY)
        self.assertEqual(self.path.read_text(), "{broken")

    def test_completed_observations_and_plan_cannot_be_overwritten(self):
        v = self.store.mutate("demo-alex", "complete", {"duration_min": 45, "session_rpe": 4})
        with self.assertRaises(ValidationError):
            self.store.mutate("demo-alex", "import", {"csv": csv_text(v["athlete"]["records"][-1:])})
        with self.assertRaises(ValidationError):
            self.store.mutate("demo-alex", "plan", v["today_session"])

    def test_goal_and_plan_validation(self):
        goal = {"goal_type": "Marathon", "goal_date": str(TODAY), "target_time_min": 240}
        for field, value in (("goal_date", str(TODAY)), ("goal_type", "unknown"), ("target_time_min", True)):
            invalid = {**goal, "goal_date": str(TODAY + timedelta(days=100)), field: value}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.store.mutate("demo-alex", "goal", invalid)
        session = self.store.view("demo-alex")["today_session"]
        for field, value in (("date", str(TODAY - timedelta(days=1))), ("duration_min", -1), ("key", "true")):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.store.mutate("demo-alex", "plan", {**session, field: value})
        self.store.mutate("demo-alex", "plan", {**session, "duration_min": 60})
        self.assertEqual(Store(self.path, today=TODAY).view("demo-alex")["today_session"]["duration_min"], 60)

    def test_coach_is_bounded_deterministic_and_uses_current_metrics(self):
        for topic in ("readiness", "plan", "load", "strength", "wins"):
            self.assertEqual(self.store.coach("demo-alex", topic), self.store.coach("demo-alex", topic))
        self.assertIn("1200 AU", self.store.coach("demo-alex", "load")["answer"])
        with self.assertRaises(ValidationError):
            self.store.coach("demo-alex", "diagnose my injury")

    def test_future_day_is_not_silently_seeded(self):
        self.store.clock = TODAY + timedelta(days=40)
        v = self.store.view("demo-alex")
        self.assertFalse(v["scheduled_today"])
        self.assertIsNone(v["prediction"]["readiness_score"])
        self.assertEqual(v["features"]["week_days_observed"], 0)

    def test_strength_balance_requires_recorded_on_dose_work(self):
        session = {**self.store.view("demo-alex")["today_session"],
                   "sport_type": "strength", "title": "Rows", "exercise": "Row",
                   "muscle_group": "pull", "sets": 3, "reps": 8, "load_kg": 25, "rir": 3}
        self.store.mutate("demo-alex", "plan", session)
        actual = {field: session[field] for field in (
            "duration_min", "session_rpe", "exercise", "muscle_group", "sets", "reps", "load_kg", "rir")}
        result = self.store.mutate("demo-alex", "complete", actual)
        self.assertIn("Strength Balance", [w["title"] for w in result["athlete"]["wins"]])
        self.assertEqual(result["features"]["direct_sets_by_muscle"]["pull"], 6)

    def test_strength_overrun_does_not_earn_balance_even_within_srpe(self):
        session = {**self.store.view("demo-alex")["today_session"],
                   "sport_type": "strength", "title": "Rows", "exercise": "Row",
                   "muscle_group": "pull", "sets": 3, "reps": 8, "load_kg": 25, "rir": 3}
        self.store.mutate("demo-alex", "plan", session)
        actual = {field: session[field] for field in (
            "duration_min", "session_rpe", "exercise", "muscle_group", "sets", "reps", "load_kg", "rir")}
        result = self.store.mutate("demo-alex", "complete", {**actual, "sets": 4})
        self.assertNotIn("Strength Balance", [w["title"] for w in result["athlete"]["wins"]])
        self.assertFalse(result["athlete"]["completions"][0]["within_dose"])

    def test_adaptation_win_requires_comparable_actual_pace(self):
        result = self.store.mutate("demo-alex", "complete",
                                   {"duration_min": 43, "session_rpe": 4, "distance_km": 8})
        self.assertIn("Adaptation Win", [w["title"] for w in result["athlete"]["wins"]])

    def test_comeback_requires_explicit_rest_not_missing_days(self):
        records = copy.deepcopy(self.store.view("demo-alex")["athlete"]["records"][-3:-1])
        for record in records:
            record.update(sport_type="rest", duration_min=0, session_rpe=0, distance_km=0,
                          exercise=None, muscle_group=None, sets=None, reps=None, load_kg=None, rir=None)
        self.store.mutate("demo-alex", "import", {"csv": csv_text(records)})
        result = self.store.mutate("demo-alex", "complete", {"duration_min": 45, "session_rpe": 4})
        self.assertIn("Comeback Win", [w["title"] for w in result["athlete"]["wins"]])
        self.store.mutate("demo-new", "checkin", {"sleep_hours": 8, "fatigue": 2, "stress": 2})
        result = self.store.mutate("demo-new", "complete", {"duration_min": 45, "session_rpe": 4})
        self.assertNotIn("Comeback Win", [w["title"] for w in result["athlete"]["wins"]])

    def test_three_key_sessions_and_goal_milestone_require_actual_logs(self):
        for offset in range(5):
            self.store.clock = TODAY + timedelta(days=offset)
            self.store.mutate("demo-alex", "checkin", {"sleep_hours": 8, "fatigue": 2, "stress": 2})
            s = self.store.view("demo-alex")["today_session"]
            s["key"] = True
            self.store.mutate("demo-alex", "plan", s)
            self.store.mutate("demo-alex", "complete", {"duration_min": s["duration_min"], "session_rpe": s["session_rpe"]})
        v = self.store.view("demo-alex")
        self.assertIn("Consistency Win", [w["title"] for w in v["athlete"]["wins"]])
        self.assertIn("Goal Progress Win", [w["title"] for w in v["athlete"]["wins"]])
        self.assertEqual(v["adherence_pct"], 100)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        store = Store(Path(self.temp.name) / "state.json", today=TODAY)

        class TestHandler(Handler):
            def log_message(self, *args):
                pass

        TestHandler.store = store
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None, extra_headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        headers = {"Content-Type": "application/json", **(extra_headers or {})}
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_real_frontend_assets_and_api_connection(self):
        for path, text in (("/", "AthleteOS"), ("/app.js", "/api/athletes"),
                           ("/style.css", "--green"), ("/sample.csv", "athlete_id")):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn(text, body.decode())
            self.assertIn("Content-Security-Policy", headers)
        status, _, body = self.request("GET", "/api/athletes/demo-alex")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["features"]["weekly_load_au"], 1200)
        status, _, body = self.request("POST", "/api/athletes/demo-alex/checkin",
                                       json.dumps({"fatigue": 8, "soreness": 8, "sleep_hours": 5}))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["prediction"]["mode"], "PROTECT")

    def test_evidence_coach_and_decision_http_contracts_share_source_version(self):
        status, _, body = self.request("GET", "/api/evidence")
        self.assertEqual(status, 200)
        evidence = json.loads(body)
        self.assertEqual(evidence["rule_version"], "demo-rules-v3")
        status, _, body = self.request("GET", "/api/health")
        self.assertEqual(json.loads(body)["predictor"], "demo-heuristic-v3")
        status, _, body = self.request("POST", "/api/athletes/demo-alex/snapshot", "{}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["prediction"]["trace"]["rule_version"], evidence["rule_version"])
        status, _, body = self.request("GET", "/api/athletes/demo-alex/decisions")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["snapshots"][0]["evidence_manifest"], evidence)
        for topic in ("readiness", "plan", "load", "strength", "wins"):
            reply = self.server.RequestHandlerClass.store.coach("demo-alex", topic)
            self.assertEqual(reply["trace"]["rule_version"], evidence["rule_version"])
            self.assertIsNone(reply["trace"]["confidence"])
            self.assertTrue(reply["trace"]["rules"] and reply["trace"]["sources"])

    def test_json_invalid_utf8_types_and_ranges_return_actionable_errors(self):
        for body in ('{', '[]', '{"fatigue":NaN}', '{"fatigue":11}', '{"fatigue":true}', b"\xff"):
            with self.subTest(body=body):
                status, _, response = self.request("POST", "/api/athletes/demo-alex/checkin", body)
                self.assertEqual(status, 400)
                self.assertIn("error", json.loads(response))
        status, _, _ = self.request("POST", "/api/athletes/demo-alex/checkin", "{}",
                                    {"Content-Type": "text/plain"})
        self.assertEqual(status, 415)

    def test_cross_origin_host_and_traversal_are_rejected(self):
        status, _, _ = self.request("POST", "/api/athletes/demo-alex/checkin", '{"fatigue":2}',
                                    {"Origin": "https://example.com"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("GET", "/", extra_headers={"Host": "example.com"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("GET", "/../athleteos/server.py")
        self.assertEqual(status, 404)

    def test_http_save_failure_is_explicit_and_preserves_previous_state(self):
        store = self.server.RequestHandlerClass.store
        before = store.view("demo-alex")
        with patch.object(store, "save", side_effect=OSError("disk full")):
            with self.assertLogs("athleteos", level="ERROR"):
                status, _, body = self.request("POST", "/api/athletes/demo-alex/checkin", '{"fatigue":3}')
        self.assertEqual(status, 500)
        self.assertIn("could not be processed or saved", json.loads(body)["error"])
        self.assertEqual(store.view("demo-alex"), before)


if __name__ == "__main__":
    unittest.main()
