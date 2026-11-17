import copy
import csv
import io
import math
import unittest
from datetime import date, timedelta
from pathlib import Path

from athleteos.domain import (FIELDS, ValidationError, calculate_features, demo_state,
                             normalized_record, parse_csv, predict_demo, recommend)

TODAY = date(2026, 11, 3)


def csv_text(records):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue()


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.athletes = demo_state(TODAY)["athletes"]
        self.alex = self.athletes[0]

    def features(self):
        return calculate_features(self.alex["records"], TODAY)

    def test_demo_records_are_normalized_and_export_round_trips(self):
        for athlete in self.athletes:
            parsed = parse_csv(csv_text(athlete["records"]), athlete["id"], TODAY)
            self.assertEqual(len(parsed), 35)
            self.assertEqual(parsed[0]["duration_min"], 0)
            self.assertEqual(parsed[-1]["date"], str(TODAY))

    def test_documented_sample_has_valid_column_counts_and_values(self):
        sample = Path(__file__).resolve().parent.parent / "web" / "sample.csv"
        rows = parse_csv(sample.read_text(), "demo-alex", TODAY)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[2]["sets"] * rows[2]["reps"] * rows[2]["load_kg"], 960)

    def test_weekly_load_monotony_and_strain_exact_values(self):
        f = self.features()
        # Explicit weekly daily doses: rest, run, strength, run, run, strength, run.
        loads = [0, 180, 140, 220, 240, 140, 280]
        self.assertEqual(f["weekly_load_au"], 1200)
        mean = sum(loads) / 7
        sd = math.sqrt(sum((v - mean) ** 2 for v in loads) / 7)
        self.assertAlmostEqual(f["monotony_ratio"], mean / sd)
        self.assertAlmostEqual(f["strain_au"], 1200 * mean / sd)
        self.assertEqual(f["baseline_weekly_load_au"], 1200)
        self.assertEqual(f["load_change_pct"], 0)

    def test_strength_units_and_per_exercise_estimates(self):
        f = self.features()
        self.assertEqual(f["strength_volume_kg"], 3 * 8 * 40 + 3 * 8 * 25)
        self.assertEqual(f["direct_sets_by_muscle"], {"core": 0, "legs": 3, "pull": 3, "push": 0})
        self.assertAlmostEqual(f["e1rm_estimates"][0]["e1rm_kg"], 40 * (1 + 8 / 30))
        self.assertEqual(f["e1rm_estimates"][0]["exercise"], "Squat")

    def test_hr_reserve_baseline_excludes_today_and_pace_has_units(self):
        f = self.features()
        self.assertAlmostEqual(f["hr_reserve_ratio"], (142 - 55) / (190 - 55))
        preceding = self.alex["records"][-29:-1]
        self.assertAlmostEqual(f["hrv_baseline_ms"], sum(r["hrv_ms"] for r in preceding) / 28)
        self.assertGreater(f["pace_min_per_km"], 5)
        self.assertLess(f["pace_min_per_km"], 6)

    def test_constant_load_is_explicitly_undefined_not_infinity(self):
        for r in self.alex["records"]:
            r.update(duration_min=30, session_rpe=4)
        f = self.features()
        self.assertIsNone(f["monotony_ratio"])
        self.assertIsNone(f["strain_au"])
        self.assertTrue(any("Constant" in warning for warning in f["warnings"]))

    def test_missing_day_not_imputed_as_rest(self):
        self.alex["records"].pop(-2)
        f = self.features()
        self.assertEqual(f["week_days_observed"], 6)
        for field in ("weekly_load_au", "monotony_ratio", "strain_au", "strength_volume_kg"):
            self.assertIsNone(f[field])
        self.assertIsNone(f["history"][-2]["load_au"])

    def test_zero_baselines_and_missing_recovery_are_not_fabricated(self):
        for record in self.alex["records"][:-7]:
            record.update(duration_min=0, session_rpe=0)
        for record in self.alex["records"]:
            record["hrv_ms"] = 0
        f = self.features()
        self.assertIsNone(f["load_change_pct"])
        self.assertIsNone(f["hrv_change_pct"])
        empty = calculate_features([], TODAY)
        self.assertIsNone(empty["current"])
        self.assertEqual(predict_demo(empty)["mode"], "INSUFFICIENT")
        self.assertIsNone(predict_demo(empty)["readiness_score"])

    def test_checkin_does_not_create_activity_day(self):
        f = calculate_features([], TODAY, {"sleep_hours": 8, "fatigue": 2, "stress": 2})
        self.assertEqual(f["week_days_observed"], 0)
        self.assertIsNone(f["weekly_load_au"])
        self.assertEqual(predict_demo(f)["mode"], "BUILD")
        self.assertEqual(f["current"]["recovery_source"], "App check-in")

    def test_demo_modes_are_distinct_and_bounded(self):
        self.assertEqual(predict_demo(self.features())["mode"], "BUILD")
        sam = calculate_features(self.athletes[1]["records"], TODAY)
        prediction = predict_demo(sam)
        self.assertEqual(prediction["mode"], "PROTECT")
        self.assertGreaterEqual(prediction["readiness_score"], 0)
        self.assertLessEqual(prediction["readiness_score"], 100)
        dose = recommend(self.athletes[1]["plan"][0], prediction)
        self.assertEqual(dose["duration_min"], 18)
        self.assertEqual(dose["session_rpe"], 2)
        self.assertEqual(dose["load_au"], 36)
        self.assertEqual(dose["sport_type"], "walk")

    def test_threshold_edges_and_priority(self):
        f = calculate_features([], TODAY, {"sleep_hours": 6, "fatigue": 7, "soreness": 6.9, "stress": 0})
        self.assertEqual(len(predict_demo(f)["signals"]), 1)
        self.assertEqual(predict_demo(f)["mode"], "MAINTAIN")
        f = calculate_features([], TODAY, {"sleep_hours": 5.99, "fatigue": 7, "soreness": 6.9})
        self.assertEqual(predict_demo(f)["mode"], "RECOVER")
        f["current"]["soreness"] = 7
        self.assertEqual(predict_demo(f)["mode"], "PROTECT")
        # Overload evidence is not suppressed just because a score is unavailable.
        f = calculate_features([], TODAY, {"fatigue": 8, "soreness": 8})
        self.assertIsNone(predict_demo(f)["readiness_score"])
        self.assertEqual(predict_demo(f)["mode"], "RECOVER")

    def test_hrv_and_load_thresholds_are_strict(self):
        f = self.features()
        f["hrv_change_pct"] = -20
        f["load_change_pct"] = 30
        self.assertEqual(predict_demo(f)["signals"], [])
        f["hrv_change_pct"] = -20.01
        f["load_change_pct"] = 30.01
        self.assertEqual(len(predict_demo(f)["signals"]), 2)

    def test_rest_is_preserved_under_protect(self):
        p = predict_demo(calculate_features(self.athletes[1]["records"], TODAY))
        r = recommend(self.athletes[1]["plan"][3], p)
        self.assertEqual(r["sport_type"], "rest")
        self.assertFalse(r["adjusted"])
        self.assertEqual(r["load_au"], 0)

    def test_csv_all_invalid_paths(self):
        base = self.alex["records"][-1]
        cases = [
            ("athlete_id", "someone-else"), ("session_rpe", "NaN"),
            ("session_rpe", 11), ("duration_min", -1), ("sport_type", "swim"),
            ("timestamp", "2026-11-03T08:00:00"), ("timestamp", "nonsense"),
            ("timestamp", "2026-11-04T08:00:00+00:00"), ("timezone", "Bad/Zone"),
            ("timestamp", "2026-11-03T08:00:00+02:00"), ("avg_hr_bpm", 220),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                invalid = copy.deepcopy(base)
                invalid[field] = value
                with self.assertRaises(ValidationError):
                    parse_csv(csv_text([invalid]), "demo-alex", TODAY)
        with self.assertRaisesRegex(ValidationError, "duplicate"):
            parse_csv(csv_text([base, base]), "demo-alex", TODAY)
        with self.assertRaises(ValidationError):
            parse_csv("bad,header\n1,2", "demo-alex", TODAY)
        with self.assertRaises(ValidationError):
            parse_csv(",".join(FIELDS) + "\n", "demo-alex", TODAY)
        with self.assertRaises(ValidationError):
            parse_csv(csv_text([base]).rstrip() + ",extra", "demo-alex", TODAY)

    def test_strength_and_numeric_types_validation(self):
        raw = copy.deepcopy(self.alex["records"][2])
        for field, value in (("sets", 2.5), ("reps", True), ("load_kg", float("inf")),
                             ("exercise", None), ("muscle_group", "unknown")):
            invalid = copy.deepcopy(raw)
            invalid[field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                normalized_record(invalid, "demo-alex", TODAY)


if __name__ == "__main__":
    unittest.main()
