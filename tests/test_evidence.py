import copy
import csv
import io
import json
import statistics
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from athleteos.domain import (FIELDS, METADATA_FIELDS, ValidationError, calculate_features,
                             demo_state, iso_date, normalized_record, parse_csv, predict_demo, recommend)
from athleteos.evidence import PREDICTION_SOURCE, RULES, RULE_VERSION, SOURCES, digest, manifest, trace
from athleteos.server import Store
from test_domain import TODAY, csv_text


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.records = demo_state(TODAY)["athletes"][0]["records"]

    def test_registry_links_and_scoped_review_are_not_exact_threshold_validation(self):
        for rule in manifest()["rules"]:
            self.assertEqual(rule["version"], RULE_VERSION)
            self.assertTrue(rule["protocol"] and rule["limitations"] and rule["population"])
            for source_id in rule["source_ids"]:
                self.assertIn(source_id, SOURCES)
            if rule["kind"] in {"signal", "product", "reward"}:
                self.assertEqual(rule["evidence"]["exact_threshold"], "provisional")
        prediction = predict_demo(calculate_features(self.records, TODAY))
        self.assertEqual(prediction["prediction_source"], PREDICTION_SOURCE)
        self.assertEqual(prediction["trace"]["rule_version"], RULE_VERSION)
        self.assertIsNone(prediction["trace"]["confidence"])
        self.assertIn("abstract", SOURCES["walsh-2021"]["verification"])
        self.assertIn("403", SOURCES["walsh-2021"]["verification"])
        self.assertIn("not the same metric", SOURCES["impellizzeri-2020"]["limitations"])
        self.assertIn("underestimated", SOURCES["lesuer-1997"]["limitations"])

    def test_trace_and_manifest_are_independent_copies_with_stable_digests(self):
        original = digest(manifest())
        changed = manifest()
        changed["rules"][0]["parameters"]["formula"] = "not a real rule"
        scoped = trace(["sleep"])
        scoped["rules"][0]["parameters"]["threshold"] = 99
        scoped["sources"][0]["limitations"] = "changed"
        self.assertEqual(digest(manifest()), original)
        self.assertEqual(trace(["sleep"])["rules"][0]["parameters"]["threshold"], 6)
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))

    def test_descriptive_baseline_counts_variability_and_no_today_leakage(self):
        before = self.records[-29:-1]
        for i, record in enumerate(before):
            record["hrv_ms"] = 60 if i < 14 else 70
        self.records[-1]["hrv_ms"] = 400
        features = calculate_features(self.records, TODAY)
        q = features["baseline_quality"]["hrv"]
        self.assertEqual((q["observation_count"], q["used_count"]), (28, 28))
        self.assertEqual(q["mean"], 65)
        self.assertEqual(q["population_sd"], 5)
        self.assertAlmostEqual(q["coefficient_of_variation_pct"], 5 / 65 * 100)
        self.assertEqual(q["comparability"], "unknown")
        self.assertEqual(q["window_end"], str(TODAY - timedelta(days=1)))
        self.assertIn("not measurement error", q["notes"][0])
        legacy = statistics.mean(r["resting_hr_bpm"] for r in before)
        self.assertEqual(features["resting_hr_baseline_bpm"], legacy)

    def test_declared_matches_exclude_other_and_unknown_measurements(self):
        for i, record in enumerate(self.records[-29:-1]):
            record.update(hrv_device="A" if i < 7 else "B", hrv_protocol="RMSSD; morning")
        self.records[-1].update(hrv_device="A", hrv_protocol="RMSSD; morning")
        f = calculate_features(self.records, TODAY)
        q = f["baseline_quality"]["hrv"]
        self.assertEqual((q["used_count"], q["excluded_mismatch_count"]), (7, 21))
        self.assertEqual(q["comparability"], "declared-match")
        self.assertIsNotNone(f["hrv_change_pct"])
        self.records[-29].update(hrv_device=None, hrv_protocol=None)
        f = calculate_features(self.records, TODAY)
        q = f["baseline_quality"]["hrv"]
        self.assertEqual((q["used_count"], q["unknown_metadata_count"]), (6, 1))
        self.assertEqual(q["status"], "insufficient-history")
        self.assertIsNone(f["hrv_baseline_ms"])
        self.assertIsNone(f["hrv_change_pct"])
        signal = next(s for s in predict_demo(f)["observed_signals"] if s["rule_id"] == "hrv")
        self.assertIsNone(signal["crossed"])

    def test_mixed_known_protocols_without_current_metadata_are_not_combined(self):
        for i, record in enumerate(self.records[-29:-1]):
            record.update(hrv_device="A", hrv_protocol="RMSSD" if i < 14 else "SDNN")
        q = calculate_features(self.records, TODAY)["baseline_quality"]["hrv"]
        self.assertEqual(q["comparability"], "mixed-declared-protocols")
        self.assertEqual(q["used_count"], 0)
        self.assertIsNone(q["mean"])
        self.records[-1].update(hrv_device="C", hrv_protocol="RMSSD")
        q = calculate_features(self.records, TODAY)["baseline_quality"]["hrv"]
        self.assertEqual(q["comparability"], "declared-mismatch")
        self.assertEqual(q["excluded_mismatch_count"], 28)

    def test_missing_zero_constant_and_insufficient_quality_is_explicit(self):
        q = calculate_features([], TODAY)["baseline_quality"]["hrv"]
        self.assertEqual((q["status"], q["used_count"]), ("insufficient-history", 0))
        self.assertIsNone(q["population_sd"])
        for value, status, cv in ((60, "constant-history", 0), (0, "zero-baseline", None)):
            for record in self.records:
                record["hrv_ms"] = value
            f = calculate_features(self.records, TODAY)
            q = f["baseline_quality"]["hrv"]
            self.assertEqual(q["status"], status)
            self.assertEqual(q["population_sd"], 0)
            self.assertEqual(q["coefficient_of_variation_pct"], cv)
            if value == 0:
                self.assertIsNone(f["hrv_change_pct"])
        for record in self.records[-29:-7]:
            record["hrv_ms"] = None
        q = calculate_features(self.records, TODAY)["baseline_quality"]["hrv"]
        self.assertEqual(q["used_count"], 6)
        self.assertIsNone(q["mean"])

    def test_extended_csv_round_trip_and_metadata_validation(self):
        record = copy.deepcopy(self.records[-1])
        record.update(hrv_device="A", hrv_protocol="RMSSD; morning")

        def extended(raw):
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=FIELDS + METADATA_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerow(raw)
            return stream.getvalue()

        parsed = parse_csv(extended(record), "demo-alex", TODAY)[0]
        self.assertEqual(parsed["hrv_protocol"], "RMSSD; morning")
        self.assertIsNone(parse_csv(csv_text([record]), "demo-alex", TODAY)[0]["hrv_device"])
        for edits in ({"hrv_protocol": ""}, {"hrv_ms": ""},
                      {"hrv_device": " "}, {"hrv_protocol": "a" * 161}):
            with self.subTest(edits=edits), self.assertRaisesRegex(ValidationError, "Row 2"):
                parse_csv(extended({**record, **edits}), "demo-alex", TODAY)
        with self.assertRaises(ValidationError):
            normalized_record({**record, "hrv_device": True}, "demo-alex", TODAY)

    def test_observed_signal_values_operators_and_thresholds_match_actual_decision(self):
        for rule_id in ("sleep", "fatigue", "soreness", "hrv", "resting-hr", "weekly-load"):
            parameters = RULES[rule_id]["parameters"]
            for at_boundary in (True, False):
                f = calculate_features(self.records, TODAY)
                value = parameters["threshold"]
                if not at_boundary:
                    value += -0.01 if parameters["operator"] == "<" else 0.01
                if rule_id == "hrv":
                    f["hrv_change_pct"] = value
                elif rule_id == "resting-hr":
                    f["current"]["resting_hr_bpm"] = f["resting_hr_baseline_bpm"] + value
                elif rule_id == "weekly-load":
                    f["load_change_pct"] = value
                else:
                    f["current"][{"sleep": "sleep_hours", "fatigue": "fatigue", "soreness": "soreness"}[rule_id]] = value
                p = predict_demo(f)
                signal = next(s for s in p["observed_signals"] if s["rule_id"] == rule_id)
                self.assertEqual(signal["threshold"], parameters["threshold"])
                self.assertEqual(signal["crossed"], not at_boundary or parameters["operator"] == ">=")
                self.assertEqual(len(p["signals"]), sum(s["crossed"] is True for s in p["observed_signals"]))
        with patch.dict(RULES["sleep"]["parameters"], {"threshold": 9}):
            p = predict_demo(calculate_features(self.records, TODAY))
            self.assertIn("sleep below 9 h", p["signals"])
            self.assertEqual(p["trace"]["rules"][0]["parameters"]["threshold"], 9)

    def test_strength_estimates_are_protocol_dependent_not_tested_maxes(self):
        for rir, expected in ((3, "non-failure-set"), (None, "effort-unknown"), (0, "declared-to-failure")):
            for record in self.records:
                if record["sport_type"] == "strength":
                    record["rir"] = rir
            estimates = calculate_features(self.records, TODAY)["e1rm_estimates"]
            self.assertTrue(estimates)
            self.assertTrue(all(e["protocol_status"] == expected for e in estimates))
            self.assertTrue(all("Not a tested max" in e["limitations"] for e in estimates))

    def test_load_only_and_combined_review_do_not_change_numeric_modes_or_doses(self):
        for record in self.records[-7:]:
            record["duration_min"] *= 2
        f = calculate_features(self.records, TODAY)
        p = predict_demo(f)
        self.assertEqual((f["load_change_pct"], p["mode"]), (100, "MAINTAIN"))
        self.assertEqual(p["monitoring_review"]["status"], "load-change-only")
        self.assertEqual(p["monitoring_review"]["combined_signal_rule_ids"], [])
        session = {"duration_min": 50, "session_rpe": 5, "title": "Run", "sport_type": "run"}
        self.assertEqual(recommend(session, p)["load_au"], 250)
        f["current"]["sleep_hours"] = 5
        p = predict_demo(f)
        self.assertEqual(p["monitoring_review"]["status"], "combined-signals")
        self.assertEqual(p["monitoring_review"]["combined_signal_rule_ids"], ["weekly-load", "sleep"])
        self.assertEqual(p["mode"], "RECOVER")
        r = recommend(session, p)
        self.assertEqual((r["duration_min"], r["session_rpe"], r["load_au"]), (30, 3, 90))
        self.assertIn("provisional reduction", r["explanation"])
        f["current"]["fatigue"] = 8
        p = predict_demo(f)
        self.assertEqual(p["mode"], "PROTECT")
        self.assertEqual(recommend(session, p)["duration_min"], 20)

    def test_absolute_high_load_and_incomplete_or_zero_baseline_are_not_combined_overload(self):
        for record in self.records:
            record["duration_min"] *= 2
        f = calculate_features(self.records, TODAY)
        self.assertEqual((f["weekly_load_au"], f["load_change_pct"]), (2400, 0))
        self.assertEqual(predict_demo(f)["monitoring_review"]["status"], "no-crossings")
        for records in ([], self.records[-7:]):
            p = predict_demo(calculate_features(records, TODAY))
            self.assertIn("weekly-load", p["monitoring_review"]["missing_rule_ids"])
            self.assertEqual(p["monitoring_review"]["combined_signal_rule_ids"], [])
        for record in self.records[:-7]:
            record.update(duration_min=0, session_rpe=0)
        f = calculate_features(self.records, TODAY)
        f["current"]["fatigue"] = 8
        p = predict_demo(f)
        self.assertIsNone(f["load_change_pct"])
        self.assertEqual(p["monitoring_review"]["status"], "recovery-signals-only")
        self.assertIn("weekly-load", p["monitoring_review"]["missing_rule_ids"])

    def test_review_context_tracks_actual_rules_and_unknown_or_mismatched_comparability(self):
        for record in self.records[-29:-1]:
            record.update(hrv_device="A", hrv_protocol="RMSSD")
        self.records[-1].update(hrv_device="B", hrv_protocol="RMSSD", hrv_ms=1)
        p = predict_demo(calculate_features(self.records, TODAY))
        self.assertIn("hrv", p["monitoring_review"]["missing_rule_ids"])
        hrv = next(c for c in p["monitoring_review"]["contexts"] if c["rule_id"] == "hrv")
        self.assertEqual(hrv["comparability"], "declared-mismatch")
        for context in p["monitoring_review"]["contexts"]:
            self.assertEqual(context["source_ids"], RULES[context["rule_id"]]["source_ids"])
        self.assertIn("Unknown", p["monitoring_review"]["limitations"])
        source = SOURCES["impellizzeri-load-2020"]
        self.assertEqual(source["published_on"], "2020-09-19")
        self.assertIn("Corrigendum", source["verification"])
        self.assertIn("does not establish", RULES["monitoring-review"]["limitations"])


class DecisionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"
        self.store = Store(self.path, today=TODAY)

    def legacy_state(self, accepted=False):
        if accepted:
            self.store.mutate("demo-sam", "accept", {})
        state = copy.deepcopy(self.store.state)
        state["version"] = 1
        for athlete in state["athletes"]:
            athlete.pop("decision_snapshots")
            athlete.pop("decision_outcomes")
            for record in athlete["records"]:
                for field in METADATA_FIELDS:
                    record.pop(field)
            for item in athlete["wins"] + athlete["completions"] + list(athlete["adjustments"].values()):
                for key in ("decision_id", "trace_status", "rule_version", "evidence_status"):
                    item.pop(key, None)
                if "recommendation" in item:
                    item["recommendation"].pop("rule_version", None)
                    item["recommendation"].pop("evidence_status", None)
        self.path.write_text(json.dumps(state), encoding="utf-8")
        return state

    def test_v1_migration_preserves_original_backup_and_legacy_acceptance_without_inventing_history(self):
        legacy = self.legacy_state(accepted=True)
        original = self.path.read_bytes()
        migrated = Store(self.path, today=TODAY)
        self.assertEqual(migrated.state["version"], 2)
        backup = self.path.with_suffix(".v1-backup.json")
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(migrated.view("demo-sam")["athlete"]["goal"], legacy["athletes"][1]["goal"])
        self.assertEqual(migrated.decisions("demo-sam")["snapshots"], [])
        chosen = migrated.view("demo-sam")["athlete"]["adjustments"][str(TODAY)]
        self.assertEqual(chosen["trace_status"], "legacy-unrecorded")
        self.assertIsNone(chosen["decision_id"])
        migrated.mutate("demo-sam", "complete", {"duration_min": 18, "session_rpe": 2})
        history = migrated.decisions("demo-sam")
        self.assertEqual(history["snapshots"], [])
        self.assertIsNone(history["outcomes"][0]["decision_id"])
        self.assertEqual(history["outcomes"][0]["trace_status"], "legacy-unrecorded")
        Store(self.path, today=TODAY)
        self.assertEqual(backup.read_bytes(), original)

    def test_existing_v1_backup_is_never_overwritten_and_migration_failure_preserves_disk(self):
        self.legacy_state()
        original = self.path.read_bytes()
        backup = self.path.with_suffix(".v1-backup.json")
        backup.write_text("existing backup", encoding="utf-8")
        with patch.object(Store, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                Store(self.path, today=TODAY)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(backup.read_text(), "existing backup")
        copies = list(self.path.parent.glob("state.v1-backup-*.json"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), original)
        self.assertEqual(Store(self.path, today=TODAY).state["version"], 2)

    def test_snapshots_replay_exactly_and_survive_edits_rules_changes_and_restart(self):
        self.store.mutate("demo-alex", "snapshot", {})
        saved = self.store.decisions("demo-alex")["snapshots"][0]
        inputs = saved["inputs"]
        f = calculate_features(inputs["records"], iso_date(saved["as_of"]), inputs["checkin"])
        p = predict_demo(f)
        self.assertEqual(f, saved["features"])
        self.assertEqual(p, saved["prediction"])
        self.assertEqual(recommend(inputs["session"], p), saved["recommendation"])
        self.assertEqual(digest(inputs), saved["input_digest"])
        self.assertEqual(digest(saved["evidence_manifest"]), saved["evidence_digest"])
        self.store.mutate("demo-alex", "checkin", {"sleep_hours": 5, "fatigue": 8, "soreness": 8})
        record = self.store.view("demo-alex")["athlete"]["records"][0]
        record["sleep_hours"] = 4
        self.store.mutate("demo-alex", "import", {"csv": csv_text([record])})
        with patch.dict(RULES["sleep"]["parameters"], {"threshold": 9}):
            self.store.mutate("demo-alex", "snapshot", {})
            self.assertEqual(self.store.decisions("demo-alex")["snapshots"][0], saved)
        reloaded = Store(self.path, today=TODAY)
        self.assertEqual(reloaded.decisions("demo-alex")["snapshots"][0], saved)
        reloaded.decisions("demo-alex")["snapshots"][0]["inputs"]["goal"]["goal_type"] = "changed copy"
        self.assertEqual(reloaded.decisions("demo-alex")["snapshots"][0], saved)

    def test_legacy_v2_snapshot_stays_byte_identical_on_read_and_new_v3_snapshot_is_additive(self):
        self.store.mutate("demo-alex", "snapshot", {})
        old = self.store.state["athletes"][0]["decision_snapshots"][0]
        old["rule_version"] = old["evidence_manifest"]["rule_version"] = "demo-rules-v2"
        old["prediction_source"] = old["prediction"]["prediction_source"] = "demo-heuristic-v2"
        old["prediction"]["rule_version"] = old["recommendation"]["rule_version"] = "demo-rules-v2"
        old["prediction"].pop("monitoring_review")
        old["evidence_manifest"]["reviewed_on"] = "2026-11-03"
        old["evidence_manifest"]["sources"] = [s for s in old["evidence_manifest"]["sources"] if s["id"] != "impellizzeri-load-2020"]
        old["evidence_manifest"]["rules"] = [r for r in old["evidence_manifest"]["rules"] if r["id"] != "monitoring-review"]
        old["prediction"]["trace"]["rule_version"] = "demo-rules-v2"
        old["prediction"]["trace"]["rules"] = [r for r in old["prediction"]["trace"]["rules"] if r["id"] != "monitoring-review"]
        old["prediction"]["trace"]["sources"] = [s for s in old["prediction"]["trace"]["sources"] if s["id"] != "impellizzeri-load-2020"]
        for r in old["evidence_manifest"]["rules"] + old["prediction"]["trace"]["rules"]:
            r["version"] = "demo-rules-v2"
        old["evidence_digest"] = digest(old["evidence_manifest"])
        saved = copy.deepcopy(old)
        self.store.save(self.store.state)
        original_bytes = self.path.read_bytes()
        reloaded = Store(self.path, today=TODAY)
        reloaded.view("demo-alex")
        self.assertEqual(reloaded.decisions("demo-alex")["snapshots"][0], saved)
        self.assertEqual(self.path.read_bytes(), original_bytes)
        reloaded.mutate("demo-alex", "snapshot", {})
        snapshots = Store(self.path, today=TODAY).decisions("demo-alex")["snapshots"]
        self.assertEqual(snapshots[0], saved)
        self.assertEqual(snapshots[1]["rule_version"], "demo-rules-v3")
        self.assertIn("monitoring_review", snapshots[1]["prediction"])
        self.assertEqual(digest(snapshots[1]["evidence_manifest"]), snapshots[1]["evidence_digest"])

    def test_coach_shared_review_matches_prediction_and_has_no_injury_probability(self):
        view = self.store.view("demo-sam")
        review = view["prediction"]["monitoring_review"]
        for topic in ("overload", "readiness", "load", "plan"):
            reply = self.store.coach("demo-sam", topic)
            self.assertEqual(reply["monitoring_review"], review)
            self.assertIn(review["summary"], reply["answer"])
            self.assertIn(review["review_action"], reply["answer"])
            self.assertIn(review["limitations"], reply["answer"])
            self.assertIn("monitoring-review", [r["id"] for r in reply["trace"]["rules"]])
            self.assertIn("impellizzeri-load-2020", [s["id"] for s in reply["trace"]["sources"]])
            self.assertIsNone(reply["trace"]["confidence"])
            self.assertNotRegex(reply["answer"], r"\d+(?:\.\d+)?% (?:injury|risk|chance|probability)")
            self.assertNotIn("injury_probability", view["prediction"])
        answer = self.store.coach("demo-sam", "overload")["answer"]
        self.assertIn("Provisional cuts:", answer)
        self.assertIn("Weekly-load change flag > 30 %", answer)
    def test_actual_outcome_links_original_accepted_decision_not_post_session_features(self):
        v = self.store.mutate("demo-sam", "accept", {})
        decision_id = v["athlete"]["adjustments"][str(TODAY)]["decision_id"]
        snapshot = self.store.decisions("demo-sam")["snapshots"][0]
        self.store.mutate("demo-sam", "complete", {"duration_min": 18, "session_rpe": 2})
        history = self.store.decisions("demo-sam")
        self.assertEqual(history["snapshots"][0], snapshot)
        outcome = history["outcomes"][0]
        self.assertEqual(outcome["decision_id"], decision_id)
        self.assertEqual(outcome["actual_load_au"], 36)
        self.assertIsNone(outcome["actual_distance_km"])
        self.assertIsNone(outcome["actual_strength_volume_kg"])
        self.assertEqual(outcome["chosen_dose"], snapshot["recommendation"])
        self.assertNotIn("confidence", outcome)
        self.assertNotIn("predicted_performance", outcome)
        self.assertEqual(Store(self.path, today=TODAY).decisions("demo-sam"), history)

    def test_actual_adherence_does_not_hide_rpe_overrun_behind_shorter_duration(self):
        self.store.mutate("demo-sam", "accept", {})
        v = self.store.mutate("demo-sam", "complete", {"duration_min": 14.4, "session_rpe": 2.5})
        outcome = self.store.decisions("demo-sam")["outcomes"][0]
        self.assertEqual(outcome["actual_load_au"], 36)
        self.assertFalse(outcome["within_dose"])
        self.assertFalse(outcome["on_plan"])
        self.assertEqual([w["title"] for w in v["athlete"]["wins"]], ["Smart Training"])

    def test_normal_completion_captures_pre_log_decision_and_reads_are_side_effect_free(self):
        before = self.store.view("demo-alex")
        disk = self.path.read_bytes()
        self.store.coach("demo-alex", "readiness")
        self.store.decisions("demo-alex")
        self.assertEqual(self.path.read_bytes(), disk)
        self.store.mutate("demo-alex", "complete", {"duration_min": 45, "session_rpe": 4})
        history = self.store.decisions("demo-alex")
        self.assertEqual(history["snapshots"][0]["features"], before["features"])
        self.assertEqual(history["outcomes"][0]["decision_id"], history["snapshots"][0]["id"])

    def test_goal_invalidates_acceptance_but_does_not_rewrite_decision(self):
        self.store.mutate("demo-sam", "accept", {})
        saved = self.store.decisions("demo-sam")
        goal = self.store.view("demo-sam")["athlete"]["goal"]
        self.store.mutate("demo-sam", "goal", {**goal, "secondary": "Updated priority"})
        self.assertNotIn(str(TODAY), self.store.view("demo-sam")["athlete"]["adjustments"])
        self.assertEqual(self.store.decisions("demo-sam")["snapshots"][0], saved["snapshots"][0])
        with self.assertRaisesRegex(ValidationError, "Accept"):
            self.store.mutate("demo-sam", "complete", {"duration_min": 18, "session_rpe": 2})

    def test_metadata_persists_through_checkin_actual_log_and_csv_export(self):
        self.store.mutate("demo-alex", "checkin", {
            "sleep_hours": 8, "fatigue": 2, "stress": 2, "hrv_ms": 70,
            "hrv_device": "A", "hrv_protocol": "RMSSD; morning"})
        self.store.mutate("demo-alex", "complete", {"duration_min": 45, "session_rpe": 4})
        reloaded = Store(self.path, today=TODAY)
        self.assertEqual(reloaded.view("demo-alex")["features"]["current"]["hrv_device"], "A")
        records = parse_csv(reloaded.export_csv("demo-alex").decode(), "demo-alex", TODAY)
        self.assertEqual(records[-1]["hrv_protocol"], "RMSSD; morning")
        before = self.path.read_bytes()
        with self.assertRaises(ValidationError):
            reloaded.mutate("demo-alex", "checkin", {"hrv_ms": 70, "hrv_device": "only one field"})
        self.assertEqual(self.path.read_bytes(), before)

    def test_unscheduled_missing_day_is_not_recorded_as_observed_rest(self):
        self.store.clock = TODAY + timedelta(days=40)
        self.store.mutate("demo-new", "snapshot", {})
        snapshot = self.store.decisions("demo-new")["snapshots"][0]
        self.assertFalse(snapshot["inputs"]["scheduled_today"])
        self.assertEqual(snapshot["inputs"]["records"], [])
        self.assertIsNone(snapshot["prediction"]["readiness_score"])
        self.assertEqual(self.store.view("demo-new")["athlete"]["records"], [])
