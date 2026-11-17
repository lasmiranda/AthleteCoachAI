"""Synthetic-only logistic/ranking/leakage and local artifact tests."""

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_data.acquire import DATA_ROOT, ResearchError
from research_data.prepare import subject_assignments, write_json, write_partition_tables
from research_data.runners_training import (FEATURES, binary_metrics, choose_threshold, evaluate,
    fit_logistic, fit_transform, infer, load_data, load_model, objective, probabilities,
    ranking_metrics, sample_input, sigmoid, train, transform, vector)


def values(value=2):
    return {name: float(value) for name in FEATURES}


class LogisticTests(unittest.TestCase):
    def test_logistic_convex_analytic_intercept_and_symmetric_separation(self):
        x = [[0.0], [0.0], [0.0], [0.0]]
        model = fit_logistic(x, [0, 0, 0, 1], .1, epochs=40)
        self.assertAlmostEqual(model["weights"][0], 0)
        self.assertAlmostEqual(model["intercept"], math.log(1 / 3))
        self.assertEqual(probabilities(model, [[0.0]])[0], .25)
        symmetric = fit_logistic([[-2.0], [-1.0], [1.0], [2.0]], [0, 0, 1, 1], .1, epochs=120)
        self.assertGreater(symmetric["weights"][0], 0)
        self.assertAlmostEqual(symmetric["intercept"], 0, places=10)
        self.assertLess(symmetric["optimization"]["selected_training_objective"],
                        symmetric["optimization"]["initial_objective"])
        self.assertLess(probabilities(symmetric, [[-2.0]])[0], .2)
        self.assertGreater(probabilities(symmetric, [[2.0]])[0], .8)
        self.assertEqual(sigmoid(-1000), 0)
        self.assertEqual(sigmoid(1000), 1)

    def test_logistic_solution_has_small_numerical_gradient(self):
        x = [[-2.0], [-1.0], [0.0], [1.0], [2.0], [3.0]]
        y = [0, 0, 1, 0, 1, 1]
        model = fit_logistic(x, y, .1)
        epsilon = 1e-5
        for field in ("weights", "intercept"):
            lower, upper = copy.deepcopy(model), copy.deepcopy(model)
            if field == "weights":
                lower[field][0] -= epsilon
                upper[field][0] += epsilon
            else:
                lower[field] -= epsilon
                upper[field] += epsilon
            gradient = (objective(upper, x, y, .1) - objective(lower, x, y, .1)) / (2 * epsilon)
            self.assertLess(abs(gradient), 1e-4)

    def test_average_precision_auc_ties_and_no_positive_predictions(self):
        rank = ranking_metrics([0, 0, 1, 1], [.1, .4, .35, .8])
        self.assertAlmostEqual(rank["average_precision"], 5 / 6)
        self.assertAlmostEqual(rank["roc_auc"], .75)
        tied = ranking_metrics([1, 0, 0, 0], [.2] * 4)
        self.assertEqual(tied["average_precision"], .25)
        self.assertEqual(tied["roc_auc"], .5)
        absent = ranking_metrics([0, 0], [.2, .5])
        self.assertIsNone(absent["average_precision"])
        no_predictions = binary_metrics([0, 0, 1], [.1, .1, .1], .5)
        self.assertIsNone(no_predictions["precision"])
        self.assertEqual(no_predictions["recall"], 0)
        self.assertEqual(no_predictions["confusion_matrix"], [[2, 0], [1, 0]])
        threshold, _ = choose_threshold([0, 0, 1], [.01, .02, .15])
        self.assertEqual(threshold, .1)

    def test_train_only_missingness_and_contract_validation(self):
        x = [[1.0] * 70, [3.0] * 70, [None] * 70]
        stats = fit_transform(x)
        self.assertEqual(stats[0]["median"], 2)
        self.assertEqual(stats[0]["mean"], 2)
        original = copy.deepcopy(stats)
        self.assertGreater(transform([[1000.0] * 70], stats)[0][0], 1000)
        self.assertEqual(original, stats)
        for bad in (dict(values(), injury=1), {}, dict(values(), **{FEATURES[0]: None}),
                    dict(values(), **{FEATURES[0]: float("inf")}),
                    dict(values(), **{FEATURES[0]: -1}),
                    dict(values(), **{FEATURES[0]: True})):
            with self.assertRaises(ResearchError):
                vector(bad)
        missing = values()
        missing["perceived exertion"] = None
        self.assertIn(None, vector(missing))
        all_missing = fit_transform([[None] * 70, [None] * 70])
        self.assertEqual(transform([[10.0] * 70], all_missing), [[0.0] * 70 + [1.0] * 70])


class RunnerPipelineTests(unittest.TestCase):
    def setUp(self):
        DATA_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-runner-training-", dir=DATA_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prepared = self.root / "prepared"
        self.prepared.mkdir()
        raw = self.root / "raw" / "runners"
        raw.mkdir(parents=True)
        for name in ("README.txt", "day_approach_maskedID_timeseries.csv"):
            (raw / name).write_text("synthetic metadata fixture only\n", encoding="utf-8")
        self.patchroot = patch("research_data.runners_training.DATA_ROOT", self.root)
        self.patchroot.start()
        self.addCleanup(self.patchroot.stop)
        grouped = subject_assignments([f"synthetic-{i}" for i in range(9)])
        rows = []
        for subject in sorted(grouped):
            for ordinal in range(12):
                label = int(ordinal % 3 == 2)
                rows.append({"row_id": f"{subject}:{ordinal}", "subject_id": subject,
                             "event_day": ordinal * 10 + 10, "label": label,
                             "features": values(1 + 3 * label)})
        def temporal(row):
            day = row["event_day"]
            return "train" if day <= 40 else "validation" if 47 < day <= 80 else "test" if day > 87 else None
        reports = {}
        for scheme in ("subject-disjoint", "temporal-purged"):
            assign = (lambda r: grouped[r["subject_id"]]) if scheme == "subject-disjoint" else temporal
            reports[scheme] = write_partition_tables(lambda: iter(copy.deepcopy(rows)), FEATURES,
                                                     assign, self.prepared / scheme)
        write_json(self.prepared / "dictionary.json", {"features": FEATURES})
        write_json(self.prepared / "summary.json", {"source": "runners", "approach": "day",
                    "temporal": {"purge_days": 7}, "schemes": reports})

    def test_real_pipeline_synthetic_fit_freeze_evaluate_infer(self):
        data, coverage, _, _ = load_data(self.prepared)
        self.assertEqual([coverage["subject-disjoint"][s]["subjects"] for s in ("train", "validation", "test")], [5, 2, 2])
        self.assertEqual(len(data["subject-disjoint"]["train"]["X"][0]), 70)
        output = self.root / "model"
        result = train(self.prepared, output)
        self.assertFalse(result["test_evaluated"])
        self.assertFalse((output / "evaluation.json").exists())
        bundle, manifest = load_model(output)
        self.assertEqual(len(bundle["schemes"]["subject-disjoint"]["classifier"]["weights"]), 140)
        with patch("research_data.runners_training.fit_logistic", side_effect=AssertionError("test cannot fit")):
            metrics = evaluate(output, self.prepared)
        self.assertEqual(metrics["schemes"]["subject-disjoint"]["selected_threshold"]["roc_auc"], 1)
        self.assertEqual(evaluate(output, self.prepared), metrics)
        summary_path = self.prepared / "summary.json"
        summary_text = summary_path.read_text()
        changed_summary = json.loads(summary_text)
        changed_summary["new_metadata_after_freeze"] = True
        summary_path.write_text(json.dumps(changed_summary))
        with self.assertRaisesRegex(ResearchError, "changed"):
            evaluate(output, self.prepared)
        summary_path.write_text(summary_text)
        sample = self.root / "sample.json"
        sample_input(self.prepared, sample)
        prediction = infer(output, json.loads(sample.read_text()))
        self.assertIn(prediction["source_label_prediction"], (0, 1))
        with self.assertRaises(ResearchError):
            infer(output, {"features": values()})
        with self.assertRaisesRegex(ResearchError, "exists"):
            train(self.prepared, output)
        second = self.root / "replay"
        train(self.prepared, second)
        self.assertEqual((output / "model.json").read_bytes(), (second / "model.json").read_bytes())
        (output / "model.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ResearchError, "hash"):
            load_model(output)

    def test_modified_schema_and_overlapping_partitions_rejected(self):
        dictionary = self.prepared / "dictionary.json"
        original = dictionary.read_text()
        dictionary.write_text(json.dumps({"features": FEATURES + ["injury"]}))
        with self.assertRaises(ResearchError):
            load_data(self.prepared)
        dictionary.write_text(original)
        rows_path = self.prepared / "subject-disjoint" / "records.jsonl"
        rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
        group = next(row["subject_id"] for row in rows if row["split"] == "train")
        for row in rows:
            if row["split"] == "test": row["subject_id"] = group
        rows_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with patch("research_data.runners_training.verify_prepared", return_value={"source": "runners"}):
            with self.assertRaisesRegex(ResearchError, "assignment"):
                load_data(self.prepared)

    def test_modified_temporal_purge_rejected(self):
        summary_path = self.prepared / "summary.json"
        summary = json.loads(summary_path.read_text())
        summary["temporal"]["purge_days"] = 0
        summary_path.write_text(json.dumps(summary))
        with self.assertRaisesRegex(ResearchError, "purge"):
            load_data(self.prepared)
