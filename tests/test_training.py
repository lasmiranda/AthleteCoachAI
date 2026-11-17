"""Synthetic-only tests for the separate local PAMAP2 classifier."""

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_data.acquire import DATA_ROOT, ResearchError
from research_data.pamap2 import CHANNELS, FEATURES
from research_data.prepare import subject_assignments, write_json, write_partition_tables
from research_data.training import (LABELS, evaluate, feature_vector, fit_gaussian, fit_transform,
                                    infer, load_data, load_model, metrics, predict, read_json,
                                    sample_input, train, transform)


def synthetic_features(mean=2.0):
    features = {}
    for channel in CHANNELS:
        features.update({f"{channel}__mean": mean, f"{channel}__sd": 0.1,
                         f"{channel}__observed_fraction": 1.0})
    return features


class ArithmeticTests(unittest.TestCase):
    def test_gaussian_parameters_and_predictions_match_analytic_example(self):
        x, y = [[0, 2], [2, 4], [8, 10], [10, 12]], [1, 1, 2, 2]
        model = fit_gaussian(x, y, 1e-9)
        self.assertAlmostEqual(model["epsilon"], 17e-9)
        self.assertEqual(model["classes"][0]["mean"], [1, 3])
        self.assertAlmostEqual(model["classes"][0]["variance"][0], 1 + 17e-9)
        self.assertEqual(predict(model, [[1, 3], [9, 11]]), [1, 2])

    def test_metrics_and_confusion_use_fixed_labels_and_report_undefined_precision(self):
        result = metrics([1, 1, 2, 2], [1, 2, 2, 2])
        self.assertEqual(result["accuracy"], 0.75)
        self.assertEqual(result["balanced_accuracy"], 0.75)
        self.assertAlmostEqual(result["macro_f1"], (2 / 3 + 0.8) / 12)
        self.assertEqual(result["confusion_matrix"][0][:2], [1, 1])
        self.assertFalse(result["per_class"]["3"]["precision_defined"])
        self.assertEqual(sum(sum(row) for row in result["confusion_matrix"]), 4)
        with self.assertRaises(ResearchError):
            metrics([1], [])

    def test_train_only_imputation_scaling_constant_and_unavailable_columns(self):
        x = [[float(i)] * len(FEATURES) for i in (1, 3, 5)]
        x[2][0] = None
        for row in x:
            row[1] = None
            row[2] = 9
        columns = fit_transform(x)
        self.assertEqual(columns[0]["median"], 2)
        self.assertEqual(columns[0]["mean"], 2)
        self.assertAlmostEqual(columns[0]["population_sd"], math.sqrt(2 / 3))
        heldout = [[1000.0] * len(FEATURES)]
        frozen = copy.deepcopy(columns)
        transformed = transform(heldout, columns)[0]
        self.assertEqual(columns, frozen)
        self.assertEqual(transformed[1], 0)
        self.assertEqual(transformed[len(FEATURES) + 1], 1)
        self.assertEqual(transformed[2], 991)
        self.assertGreater(transformed[0], 1000)

    def test_feature_input_rejects_metadata_missing_keys_invalid_numbers_and_coverage(self):
        valid = synthetic_features()
        self.assertEqual(len(feature_vector(valid)), 120)
        bad = []
        extra = dict(valid, subject_id="synthetic", label=1)
        bad.append(extra)
        absent = dict(valid)
        del absent[FEATURES[0]]
        bad.append(absent)
        for value in (float("inf"), float("nan"), True, "2", None, 10 ** 1000):
            row = dict(valid)
            row["heart_rate_bpm__mean"] = value
            bad.append(row)
        for fraction in (None, -0.1, 1.1, 0):
            row = dict(valid)
            row["heart_rate_bpm__observed_fraction"] = fraction
            bad.append(row)
        row = dict(valid)
        row["heart_rate_bpm__sd"] = -1
        bad.append(row)
        empty = dict(valid)
        for channel in CHANNELS:
            empty[f"{channel}__mean"] = empty[f"{channel}__sd"] = None
            empty[f"{channel}__observed_fraction"] = 0
        bad.append(empty)
        for values in bad:
            with self.subTest(keys=len(values)), self.assertRaises(ResearchError):
                feature_vector(values)
        missing_hr = dict(valid)
        missing_hr.update(heart_rate_bpm__mean=None, heart_rate_bpm__sd=None,
                          heart_rate_bpm__observed_fraction=0)
        self.assertIsNone(feature_vector(missing_hr)[0])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        DATA_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-training-", dir=DATA_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prepared = self.root / "prepared"
        self.prepared.mkdir()
        self.assignment = subject_assignments([f"synthetic-{i}" for i in range(9)])
        self.rows = []
        for subject in sorted(self.assignment):
            for ordinal in range(12):
                label = 1 if ordinal < 6 else 2
                self.rows.append({"row_id": f"{subject}:{ordinal}", "subject_id": subject,
                                  "relative_time": ordinal * 5 + 5.0,
                                  "window_start_s": ordinal * 5.0,
                                  "window_end_s": ordinal * 5 + 4.99,
                                  "label": label, "features": synthetic_features(label * 4 + ordinal / 100)})
        report = write_partition_tables(lambda: iter(copy.deepcopy(self.rows)), FEATURES,
                                        lambda row: self.assignment[row["subject_id"]],
                                        self.prepared / "subject-disjoint")
        write_json(self.prepared / "dictionary.json", {"features": FEATURES})
        write_json(self.prepared / "summary.json", {"source": "pamap2", "pipeline_version": 1,
                                                   "schemes": {"subject-disjoint": report}})

    def test_schema_metadata_exclusion_and_subject_disjoint_coverage(self):
        arrays, coverage, _, _ = load_data(self.prepared)
        self.assertEqual(sum(c["windows"] for c in coverage.values()), 108)
        self.assertEqual([coverage[s]["subjects"] for s in ("train", "validation", "test")], [5, 2, 2])
        self.assertEqual(len(arrays["train"]["X"][0]), 120)
        self.assertEqual(len(coverage["train"]["missing_classes"]), 10)
        path = self.prepared / "dictionary.json"
        write_json(self.root / "bad-dictionary.json", {"features": FEATURES + ["subject_id"]})
        path.write_text((self.root / "bad-dictionary.json").read_text(), encoding="utf-8")
        with self.assertRaisesRegex(ResearchError, "schema"):
            load_data(self.prepared)

    def test_fit_freeze_roundtrip_separate_test_and_reproducibility(self):
        output = self.root / "model"
        original_predict = predict
        widths = []

        def capture_predict(model, rows):
            widths.append(len(rows))
            return original_predict(model, rows)

        with patch("research_data.training.predict", side_effect=capture_predict):
            result = train(self.prepared, output)
        self.assertFalse(result["test_evaluated"])
        self.assertEqual(widths, [24, 24])  # Only validation is predicted during train.
        self.assertFalse((output / "evaluation.json").exists())
        bundle, manifest = load_model(output)
        self.assertEqual(len(bundle["classifier"]["classes"][0]["mean"]), 240)
        self.assertEqual(manifest["configuration"]["selected_var_smoothing"], 1e-9)
        second = self.root / "model-repeat"
        train(self.prepared, second)
        self.assertEqual((output / "model.json").read_bytes(), (second / "model.json").read_bytes())
        with self.assertRaisesRegex(ResearchError, "exists"):
            train(self.prepared, output)
        with patch("research_data.training.fit_gaussian", side_effect=AssertionError("test cannot fit")):
            evaluated = evaluate(output, self.prepared)
        self.assertEqual(evaluated["windows"], 24)
        self.assertEqual(evaluated["classifier"]["accuracy"], 1)
        self.assertEqual(evaluate(output, self.prepared), evaluated)
        input_path = self.root / "inference.json"
        sample_input(self.prepared, input_path)
        prediction = infer(output, read_json(input_path))
        self.assertIn(prediction["activity_id"], LABELS)
        with self.assertRaisesRegex(ResearchError, "contract_version"):
            infer(output, {"features": synthetic_features()})
        with self.assertRaisesRegex(ResearchError, "range"):
            infer(output, {"contract_version": 1, "features": synthetic_features(1e308)})
        (output / "model.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ResearchError, "hash"):
            load_model(output)

    def test_subject_leakage_and_changed_evaluation_data_are_rejected(self):
        output = self.root / "model"
        train(self.prepared, output)
        summary_path = self.prepared / "summary.json"
        original_summary = summary_path.read_text(encoding="utf-8")
        summary = json.loads(original_summary)
        summary["changed_provenance"] = True
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        with self.assertRaisesRegex(ResearchError, "differs"):
            evaluate(output, self.prepared)
        summary_path.write_text(original_summary, encoding="utf-8")
        with patch("research_data.training.verify_prepared", return_value={"source": "pamap2"}):
            records = self.prepared / "subject-disjoint" / "records.jsonl"
            rows = [json.loads(line) for line in records.read_text().splitlines()]
            train_subject = next(row["subject_id"] for row in rows if row["split"] == "train")
            for row in rows:
                if row["split"] == "test":
                    row["subject_id"] = train_subject
            records.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            with self.assertRaisesRegex(ResearchError, "overlap"):
                load_data(self.prepared)
        with self.assertRaisesRegex(ResearchError, "hash"):
            evaluate(output, self.prepared)

    def test_json_artifact_cannot_execute_pickle_and_paths_stay_ignored(self):
        with self.assertRaisesRegex(ResearchError, "ignored"):
            train(self.prepared, DATA_ROOT.parent / "tracked-model")
        path = self.root / "invalid.json"
        path.write_text('{"value":NaN}', encoding="utf-8")
        with self.assertRaisesRegex(ResearchError, "constant"):
            read_json(path)
