"""Synthetic parser/split fixtures only. No real individual records are embedded here."""

import copy
import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from research_data.acquire import DATA_ROOT, ROOT, ResearchError, acquire, download, hashes, local_root
from research_data.pamap2 import (CHANNELS, FEATURES, inspect_zip, prepare_pamap2,
                                protocol_archive, sample_values, windows_from_lines)
from research_data.prepare import (DAY, RATIOS, SPLITS, WEEK, expanded, prepare_runners,
                                   runner_features, runner_rows, subject_assignments, write_partition_tables)
from research_data.verify import verify_prepared


class ResearchFixture(unittest.TestCase):
    def setUp(self):
        DATA_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-test-", dir=DATA_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)


class DownloadTests(ResearchFixture):
    def spec(self, data):
        return {"name": "synthetic.csv", "url": "https://example.invalid/synthetic.csv",
                "bytes": len(data), "sha1": hashlib.sha1(data).hexdigest()}

    def response(self, data):
        response = io.BytesIO(data)
        response.headers = {"Content-Length": str(len(data))}
        return response

    def test_published_checksum_guard_and_cached_idempotence(self):
        data = b"synthetic,data\n1,2\n"
        with patch("urllib.request.urlopen", return_value=self.response(data)) as get:
            result = download(self.spec(data), self.root)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
        with patch("urllib.request.urlopen", side_effect=AssertionError("cache should not transfer")):
            cached = download(self.spec(data), self.root)
        self.assertTrue(cached["cached"])
        self.assertEqual(hashes(self.root / "synthetic.csv")["bytes"], len(data))

    def test_limits_and_checksum_failures_never_publish_download(self):
        data = b"synthetic"
        spec = self.spec(data)
        with patch("urllib.request.urlopen", return_value=self.response(b"tampered!")):
            with self.assertRaisesRegex(ResearchError, "SHA-1"):
                download(spec, self.root)
        self.assertEqual(list(self.root.iterdir()), [])
        with patch("urllib.request.urlopen", side_effect=AssertionError("over-budget must not transfer")):
            with self.assertRaisesRegex(ResearchError, "limit"):
                download(spec, self.root, byte_limit=1)
        with patch("urllib.request.urlopen", return_value=self.response(b"<html>not zip</html>")):
            with self.assertRaisesRegex(ResearchError, "ZIP"):
                download({"name": "source.zip", "url": spec["url"]}, self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cached_corruption_is_not_silently_trusted(self):
        path = self.root / "synthetic.csv"
        path.write_bytes(b"bad")
        with self.assertRaisesRegex(ResearchError, "byte count"):
            download(self.spec(b"longer data"), self.root)

    def test_nonignored_output_root_is_rejected(self):
        with self.assertRaisesRegex(ResearchError, "ignored"):
            local_root(ROOT / "tests")
        for name in ("../outside.csv", "C:\\outside.csv"):
            with self.assertRaisesRegex(ResearchError, "basename"):
                download({**self.spec(b"fixture"), "name": name}, self.root)

    def test_large_or_restricted_sources_do_not_download_implicitly(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("not authorized")):
            for source in ("fitrec", "garmin", "pamap2"):
                with self.subTest(source=source), self.assertRaises(ResearchError):
                    acquire(source, self.root)


class RunnerPreparationTests(ResearchFixture):
    def fixture_csv(self, approach="day", duplicate=False, invalid=None):
        features = runner_features(approach)
        path = self.root / f"{approach}.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=features + ["Athlete ID", "injury"]
                                    + (RATIOS if approach == "week" else []) + ["Date"])
            writer.writeheader()
            for subject in range(10):
                for day in range(100):
                    raw = dict.fromkeys(features, 2.0)
                    raw.update({"Athlete ID": subject, "injury": int(day % 10 == 0), "Date": day * 3})
                    if approach == "day":
                        raw["perceived recovery"] = -0.01
                    for ratio in RATIOS if approach == "week" else []:
                        raw[ratio] = 1.0
                    if invalid is not None:
                        raw.update(invalid)
                    writer.writerow(raw)
                    if duplicate and subject == day == 0:
                        writer.writerow(raw)
        return path

    def test_exact_schema_counts_and_source_sentinel_preserve_missingness(self):
        for approach, size in (("day", 70), ("week", 66)):
            path = self.fixture_csv(approach)
            rows = list(runner_rows(path, approach))
            self.assertEqual(len(rows), 1000)
            self.assertEqual(len(rows[0]["features"]), size)
            self.assertEqual(rows[0]["event_day"], 0)
            self.assertNotIn("Athlete ID", rows[0]["features"])
            if approach == "day":
                self.assertIsNone(rows[0]["features"]["perceived recovery"])
            else:
                self.assertTrue(all(ratio not in rows[0]["features"] for ratio in RATIOS))

    def test_corruption_duplicates_and_new_schema_fail_explicitly(self):
        with self.assertRaisesRegex(ResearchError, "Duplicate"):
            list(runner_rows(self.fixture_csv(duplicate=True), "day"))
        for invalid in ({"injury": 2}, {"Date": -1}, {"total km": "Infinity"}, {"Athlete ID": 0.1}):
            with self.subTest(invalid=invalid), self.assertRaises(ResearchError):
                list(runner_rows(self.fixture_csv(invalid=invalid), "day"))
        self.assertEqual(len(expanded(DAY, 7)), 70)
        self.assertEqual(len(expanded(WEEK, 3)), 66)
        with self.assertRaisesRegex(ResearchError, "schema"):
            list(runner_rows(self.fixture_csv("week"), "day"))

    def test_subject_hash_split_is_order_independent_and_label_blind(self):
        subjects = [str(i) for i in range(74)]
        assignment = subject_assignments(subjects)
        self.assertEqual(assignment, subject_assignments(reversed(subjects)))
        self.assertEqual({s: sum(v == s for v in assignment.values()) for s in SPLITS},
                         {"train": 44, "validation": 15, "test": 15})
        with self.assertRaises(ResearchError):
            subject_assignments(["one"])

    def test_transforms_use_training_only_and_do_not_impute_missing_or_leak_metadata(self):
        rows = [{"row_id": f"synthetic:{i}", "subject_id": str(i), "event_day": i,
                 "label": i % 2, "features": {"measured": value, "empty": None, "constant": 7}}
                for i, value in enumerate((2, 4, 1000, None, 2000, 10000))]
        assignment = lambda r: SPLITS[int(r["subject_id"]) // 2]
        result = write_partition_tables(lambda: iter(copy.deepcopy(rows)), ["measured", "empty", "constant"],
                                        assignment, self.root / "split")
        transforms = json.loads((self.root / "split" / "transforms.json").read_text())["columns"]
        self.assertEqual(transforms["measured"]["mean"], 3)
        self.assertEqual(transforms["measured"]["population_sd"], 1)
        self.assertEqual(transforms["measured"]["count"], 2)
        with (self.root / "split" / "validation.features.csv").open(newline="") as stream:
            x = list(csv.DictReader(stream))
        self.assertEqual(float(x[0]["measured"]), 997)
        self.assertEqual(x[1]["measured"], "")
        self.assertEqual(x[1]["measured__missing"], "1")
        self.assertEqual(x[0]["constant"], "0.0")
        self.assertNotIn("subject_id", x[0])
        self.assertNotIn("event_day", x[0])
        self.assertNotIn("label", x[0])
        self.assertEqual(result["all_missing_training_features"], ["empty"])
        self.assertEqual(result["constant_training_features"], ["constant"])

    def test_full_fixture_preparation_purges_lookback_and_is_reproducible(self):
        for approach, purge in (("day", 7), ("week", 21)):
            path = self.fixture_csv(approach)
            raw_dir = self.root / "raw" / "runners"
            raw_dir.mkdir(parents=True, exist_ok=True)
            target = raw_dir / f"{approach}_synthetic.csv"
            target.write_bytes(path.read_bytes())
            source = {"runners": {"files": [{"name": target.name, **hashes(target)}]}}
            with patch("research_data.prepare.sources", return_value=source):
                report = prepare_runners(approach, self.root, self.root / f"prepared-{approach}")
                second = prepare_runners(approach, self.root, self.root / f"second-{approach}")
                with self.assertRaisesRegex(ResearchError, "Output exists"):
                    prepare_runners(approach, self.root, self.root / f"second-{approach}")
            self.assertEqual(report, second)
            self.assertEqual(report["temporal"]["purge_days"], purge)
            grouped = report["schemes"]["subject-disjoint"]
            self.assertTrue(all(count == 0 for count in grouped["subject_overlap_counts"].values()))
            temporal = report["schemes"]["temporal-purged"]["coverage"]
            self.assertGreater(temporal["validation"]["relative_time_min"] - purge, temporal["train"]["relative_time_max"])
            self.assertGreater(temporal["test"]["relative_time_min"] - purge, temporal["validation"]["relative_time_max"])
            dictionary = json.loads((self.root / f"prepared-{approach}" / "dictionary.json").read_text())
            self.assertIn(".6=1 day", dictionary["suffix_mapping"])
            self.assertEqual(report["rows"], 1000)
            verified = verify_prepared(self.root / f"prepared-{approach}")
            self.assertTrue(verified["schemes"]["subject-disjoint"]["train_only_transforms_recomputed"])
            x = self.root / f"prepared-{approach}" / "subject-disjoint" / "test.features.csv"
            x.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ResearchError, "hash"):
                verify_prepared(self.root / f"prepared-{approach}")


class PamapTests(unittest.TestCase):
    @staticmethod
    def line(i, label=4, missing_hr=False, gap=0):
        values = [i / 100 + gap, label, "NaN" if missing_hr else 80] + [1] * 51
        # Invalid orientation per source is never used as a model feature.
        for index in (16, 17, 18, 19, 33, 34, 35, 36, 50, 51, 52, 53):
            values[index] = "NaN"
        return " ".join(str(v) for v in values)

    def test_no_overlapping_windows_and_missing_hr_is_not_hrv(self):
        rows = list(windows_from_lines((self.line(i, missing_hr=True) for i in range(1000)), "synthetic"))
        self.assertEqual(len(rows), 2)
        self.assertGreater(rows[1]["window_start_s"], rows[0]["window_end_s"])
        self.assertIsNone(rows[0]["features"]["heart_rate_bpm__mean"])
        self.assertEqual(rows[0]["features"]["heart_rate_bpm__observed_fraction"], 0)
        self.assertEqual(rows[0]["features"]["hand_temperature_C__mean"], 1)
        self.assertEqual(len(rows[0]["features"]), 120)
        self.assertEqual(len(CHANNELS), 40)
        self.assertFalse(any("orientation" in feature or "hrv" in feature for feature in FEATURES))

    def test_windows_never_cross_label_gap_or_transient_boundaries(self):
        lines = [self.line(i, label=4 if i < 250 else 5) for i in range(750)]
        rows = list(windows_from_lines(lines, "synthetic"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label"], 5)
        lines = [self.line(i, gap=0 if i < 250 else 1) for i in range(500)]
        self.assertEqual(list(windows_from_lines(lines, "synthetic")), [])
        self.assertEqual(list(windows_from_lines((self.line(i, label=0) for i in range(700)), "synthetic")), [])

    def test_exact_columns_monotonic_time_and_known_labels_required(self):
        for line in ("0 1 2", self.line(0, label=3.5), self.line(0, label=99),
                     self.line(0).replace("80", "inf")):
            with self.subTest(line=line[:20]), self.assertRaises(ResearchError):
                sample_values(line)
        with self.assertRaisesRegex(ResearchError, "Non-increasing"):
            list(windows_from_lines([self.line(1), self.line(0)], "synthetic"))

    def test_safe_archive_inventory_rejects_traversal_and_bombs_without_extracting(self):
        for filename, content in (("../outside.dat", b"fixture"), ("/absolute.dat", b"fixture"),
                                  ("C:\\outside.dat", b"fixture"), ("huge.txt", b"0" * 100000)):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(filename, content)
            buffer.seek(0)
            with zipfile.ZipFile(buffer) as archive:
                with self.subTest(filename=filename), self.assertRaises(ResearchError):
                    inspect_zip(archive)


class PamapPipelineTests(ResearchFixture):
    def test_complete_synthetic_archive_nested_crc_windows_and_partition_pipeline(self):
        directory = self.root / "raw" / "pamap2"
        directory.mkdir(parents=True)
        nested_bytes = io.BytesIO()
        with zipfile.ZipFile(nested_bytes, "w", compression=zipfile.ZIP_DEFLATED) as nested:
            for subject in range(101, 110):
                lines = [PamapTests.line(i, label=4 if i < 500 else 5) for i in range(1000)]
                nested.writestr(f"PAMAP2_Dataset/Protocol/subject{subject}.dat", "\n".join(lines))
        outer = directory / "pamap2.zip"
        with zipfile.ZipFile(outer, "w") as archive:
            archive.writestr("PAMAP2_Dataset.zip", nested_bytes.getvalue())
        (directory / "acquisition.json").write_text(json.dumps({"files": [hashes(outer)]}), encoding="utf-8")
        result = prepare_pamap2(self.root)
        self.assertEqual((result["subjects"], result["windows"]), (9, 18))
        self.assertEqual(result["sample_audit"]["raw_samples"], 9000)
        self.assertEqual(result["sample_audit"]["discarded_boundary_samples"], 0)
        self.assertEqual(result["classes"], {"4": 9, "5": 9})
        verified = verify_prepared(self.root / "prepared" / "pamap2-protocol-v1")
        self.assertEqual(verified["schemes"]["subject-disjoint"]["verified_rows"], 18)
        cached = protocol_archive(outer, directory)
        self.assertEqual(cached.name, "PAMAP2_Dataset.zip")
        with cached.open("r+b") as stream:
            stream.write(b"BAD!")
        with self.assertRaisesRegex(ResearchError, "CRC"):
            protocol_archive(outer, directory)
