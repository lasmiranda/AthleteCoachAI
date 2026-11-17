"""Experimental daily runner source-label logistic baseline; no clinical inference."""

import argparse
import csv
import json
import math
import platform
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from research_data.acquire import DATA_ROOT, ResearchError, hashes
from research_data.prepare import Moments, SPLITS, runner_features, subject_assignments
from research_data.training import inside, new_json, numeric, read_json
from research_data.verify import verify_prepared

FEATURES = runner_features("day")
VERSION = "runners-day-logistic-v1"
DEFAULT_DATA = DATA_ROOT / "prepared" / "runners-day-v1"
DEFAULT_MODEL = DATA_ROOT / "models" / VERSION
PENALTIES = (0.01, 0.1)
EPOCHS = 160
SCHEMES = ("subject-disjoint", "temporal-purged")


def vector(features):
    if not isinstance(features, dict) or set(features) != set(FEATURES):
        raise ResearchError("Require exactly 70 daily source features, no label, ID, date or weekly fields.")
    result = []
    for name in FEATURES:
        value = features[name]
        if value is not None and (not numeric(value) or value < 0):
            raise ResearchError(f"{name}: require a nonnegative finite number or explicit null.")
        if value is None and not name.startswith("perceived "):
            raise ResearchError(f"{name}: source objective field must be observed.")
        result.append(value)
    if all(value is None for value in result):
        raise ResearchError("No observed features.")
    return result


def load_data(directory):
    directory = inside(directory)
    verified = verify_prepared(directory)
    summary, dictionary = read_json(directory / "summary.json"), read_json(directory / "dictionary.json")
    if (verified["source"] != "runners" or summary["approach"] != "day"
            or dictionary["features"] != FEATURES or set(summary["schemes"]) != set(SCHEMES)):
        raise ResearchError("Require the reviewed daily runner preparation with both inherited schemes.")
    data, coverage = {}, {}
    for scheme in SCHEMES:
        arrays = {split: {"X": [], "y": []} for split in SPLITS}
        groups = {split: set() for split in SPLITS}
        dates = {split: [] for split in SPLITS}
        with (directory / scheme / "records.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if type(row["label"]) is not int or row["label"] not in (0, 1):
                    raise ResearchError("Source label must be binary 0/1.")
                split = row["split"]
                groups[split].add(row["subject_id"])
                dates[split].append(row["event_day"])
                arrays[split]["X"].append(vector(row["features"]))
                arrays[split]["y"].append(row["label"])
        if scheme == "subject-disjoint":
            assignment = subject_assignments(set.union(*groups.values()))
            if any(assignment[s] != split for split in SPLITS for s in groups[split]):
                raise ResearchError("Inherited deterministic subject assignment changed.")
        else:
            purge = summary["temporal"]["purge_days"]
            if purge != 7 or min(dates["validation"]) - 7 <= max(dates["train"]) or min(dates["test"]) - 7 <= max(dates["validation"]):
                raise ResearchError("Daily temporal window purge failed.")
        coverage[scheme] = {}
        for split in SPLITS:
            labels = arrays[split]["y"]
            if set(labels) != {0, 1}:
                raise ResearchError(f"{scheme}/{split}: both source classes required for this benchmark.")
            coverage[scheme][split] = {
                "rows": len(labels), "subjects": len(groups[split]), "positives": sum(labels),
                "negatives": len(labels) - sum(labels), "prevalence": sum(labels) / len(labels),
                "missing_feature_cells": sum(v is None for r in arrays[split]["X"] for v in r),
            }
        data[scheme] = arrays
    inputs = ("summary.json", "dictionary.json",
              "subject-disjoint/records.jsonl", "temporal-purged/records.jsonl")
    return data, coverage, {name: hashes(directory / name) for name in inputs}, verified


def fit_transform(x):
    stats = []
    for i in range(len(FEATURES)):
        observed = [row[i] for row in x if row[i] is not None]
        median = statistics.median(observed) if observed else 0.0
        moment = Moments()
        for row in x:
            moment.add(median if row[i] is None else row[i])
        result = moment.result()
        stats.append({"count": len(observed), "median": median,
                      "mean": result["mean"], "sd": result["population_sd"]})
    return stats


def transform(x, stats):
    result = []
    for row in x:
        if len(row) != len(FEATURES) or len(stats) != len(FEATURES):
            raise ResearchError("Transform input width mismatch.")
        values, masks = [], []
        for value, column in zip(row, stats):
            missing = value is None or column["count"] == 0
            scaled = ((column["median"] if missing else value) - column["mean"]) / (column["sd"] or 1)
            if not math.isfinite(scaled):
                raise ResearchError("Feature exceeds finite transform arithmetic range.")
            values.append(scaled)
            masks.append(float(missing))
        result.append(values + masks)
    return result


def sigmoid(score):
    if not math.isfinite(score):
        raise ResearchError("Nonfinite logistic score.")
    if score >= 0:
        return 1 / (1 + math.exp(-score))
    exp = math.exp(score)
    return exp / (1 + exp)


def probabilities(model, x):
    weights = model["weights"]
    result = []
    for row in x:
        if len(row) != len(weights):
            raise ResearchError("Classifier feature width mismatch.")
        result.append(sigmoid(model["intercept"] + sum(w * v for w, v in zip(weights, row))))
    return result


def objective(model, x, y, penalty):
    loss = 0.0
    for row, label in zip(x, y):
        z = model["intercept"] + sum(w * v for w, v in zip(model["weights"], row))
        loss += max(z, 0) - label * z + math.log1p(math.exp(-abs(z)))
    return loss / len(y) + penalty * sum(w * w for w in model["weights"]) / 2


def fit_logistic(x, y, penalty, epochs=EPOCHS):
    if not x or len(x) != len(y) or set(y) != {0, 1} or penalty <= 0:
        raise ResearchError("Logistic fit requires aligned rows, both classes and positive L2.")
    n, width = len(y), len(x[0])
    if not width or any(len(row) != width or any(not numeric(v) for v in row) for row in x):
        raise ResearchError("Invalid logistic design matrix.")
    prior = sum(y) / n
    initial = {"weights": [0.0] * width, "intercept": math.log(prior / (1 - prior))}
    lipschitz = .25 * sum(1 + sum(v * v for v in row) for row in x) / n + penalty
    step = 1 / lipschitz
    current, lookahead, momentum = initial, initial, 1.0
    start = objective(initial, x, y, penalty)
    best, best_loss = initial, start
    for epoch in range(epochs):
        grad = [penalty * w for w in lookahead["weights"]]
        bias_grad = 0.0
        for row, label in zip(x, y):
            residual = (sigmoid(lookahead["intercept"] + sum(w * v for w, v in zip(lookahead["weights"], row))) - label) / n
            bias_grad += residual
            for i, value in enumerate(row):
                grad[i] += residual * value
        updated = {"weights": [w - step * g for w, g in zip(lookahead["weights"], grad)],
                   "intercept": lookahead["intercept"] - step * bias_grad}
        next_momentum = (1 + math.sqrt(1 + 4 * momentum * momentum)) / 2
        factor = (momentum - 1) / next_momentum
        lookahead = {"weights": [a + factor * (a - b) for a, b in zip(updated["weights"], current["weights"])],
                     "intercept": updated["intercept"] + factor * (updated["intercept"] - current["intercept"])}
        current, momentum = updated, next_momentum
        if (epoch + 1) % 20 == 0 or epoch == epochs - 1:
            loss = objective(current, x, y, penalty)
            if loss < best_loss:
                best, best_loss = current, loss
    if not math.isfinite(best_loss):
        raise ResearchError("Logistic optimization produced nonfinite loss.")
    return {**best, "optimization": {"epochs": epochs, "step_size": step,
            "initial_objective": start, "selected_training_objective": best_loss,
            "algorithm": "Full-batch Nesterov gradient; Lipschitz trace upper bound; best train objective checked every 20 iterations. Fixed budget, not proof of convergence."}}


def ranking_metrics(y, scores):
    if not y or len(y) != len(scores) or any(type(a) is not int or a not in (0, 1) for a in y) or any(not numeric(s) or not 0 <= s <= 1 for s in scores):
        raise ResearchError("Ranking metrics require aligned binary labels and finite [0,1] scores.")
    positives, negatives = sum(y), len(y) - sum(y)
    if not positives or not negatives:
        return {"average_precision": None, "roc_auc": None,
                "defined": False, "reason": "Both classes required; not fabricated."}
    pairs = sorted(zip(scores, y), reverse=True)
    tp, fp, ap, roc_area, previous_tp, previous_fp = 0, 0, 0.0, 0.0, 0, 0
    i = 0
    while i < len(pairs):
        score = pairs[i][0]
        while i < len(pairs) and pairs[i][0] == score:
            tp += pairs[i][1]
            fp += 1 - pairs[i][1]
            i += 1
        ap += ((tp - previous_tp) / positives) * tp / (tp + fp)
        roc_area += ((fp - previous_fp) / negatives) * (tp + previous_tp) / (2 * positives)
        previous_tp, previous_fp = tp, fp
    return {"average_precision": ap, "roc_auc": roc_area, "defined": True,
            "convention": "AP=sum(delta recall * precision) at descending distinct score thresholds; ties grouped. Not trapezoidal PR-AUC. ROC trapezoids with tied scores grouped."}


def binary_metrics(y, scores, threshold):
    rank = ranking_metrics(y, scores)
    tn = fp = fn = tp = 0
    for label, score in zip(y, scores):
        predicted = score >= threshold
        if label == 1:
            if predicted: tp += 1
            else: fn += 1
        else:
            if predicted: fp += 1
            else: tn += 1
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {**rank, "threshold": threshold, "rows": len(y), "positives": sum(y),
            "prevalence": sum(y) / len(y), "predicted_positives": tp + fp,
            "accuracy": (tp + tn) / len(y), "precision": precision, "recall": recall,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            "confusion_matrix": [[tn, fp], [fn, tp]], "matrix_order": "rows actual 0/1; columns predicted 0/1",
            "undefined_precision": precision is None}


def choose_threshold(y, scores):
    # This fixed validation-only tradeoff favors F1, not a medical operating point.
    candidates = (.01, .02, .05, .1, .2, .5)
    rows = [binary_metrics(y, scores, threshold) for threshold in candidates]
    chosen = max(rows, key=lambda row: (row["f1"] or 0, row["threshold"]))
    return chosen["threshold"], rows


def train(prepared=DEFAULT_DATA, output=DEFAULT_MODEL):
    output = inside(output)
    if output.exists():
        raise ResearchError("Output exists; preserve the prior frozen run, choose a new --output.")
    data, coverage, fingerprints, verified = load_data(prepared)
    output.mkdir(parents=True, exist_ok=False)
    new_json(output / "status.json", {"status": "incomplete until frozen.json exists"})
    bundles, validations = {}, {}
    for scheme in SCHEMES:
        train_set, validation = data[scheme]["train"], data[scheme]["validation"]
        stats = fit_transform(train_set["X"])
        x = transform(train_set["X"], stats)
        val_x = transform(validation["X"], stats)
        candidates, selected, best_ap = [], None, -1
        for penalty in PENALTIES:
            model = fit_logistic(x, train_set["y"], penalty)
            scores = probabilities(model, val_x)
            rank = ranking_metrics(validation["y"], scores)
            candidates.append({"l2": penalty, "validation_ranking": rank, "optimization": model["optimization"]})
            if rank["average_precision"] > best_ap:
                best_ap = rank["average_precision"]
                selected = {"model": model, "l2": penalty, "scores": scores}
        threshold, table = choose_threshold(validation["y"], selected["scores"])
        prior = sum(train_set["y"]) / len(train_set["y"])
        bundles[scheme] = {"transform": stats, "classifier": selected["model"],
                           "selected_l2": selected["l2"], "threshold": threshold,
                           "dummy_score": prior}
        validations[scheme] = {"candidates": candidates, "threshold_candidates": table,
                               "selected": binary_metrics(validation["y"], selected["scores"], threshold),
                               "default_0_5": binary_metrics(validation["y"], selected["scores"], .5)}
    new_json(output / "model.json", {"model_version": VERSION, "features": FEATURES, "schemes": bundles})
    source_files = ("README.txt", "day_approach_maskedID_timeseries.csv")
    manifest = {"model_version": VERSION, "contract_version": 1,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "features": FEATURES, "label": "Source injury event on indexed day t, 0/1; retrospective benchmark, not diagnosis.",
                "window": "Seven preceding days t-7 through t-1; base=t-7, .6=t-1 per corrected README v2. No event-day features.",
                "source": "https://doi.org/10.34894/UWU9PV", "license": "CC0-1.0",
                "source_hashes": {name: hashes(DATA_ROOT / "raw" / "runners" / name) for name in source_files},
                "dataset_fingerprints": fingerprints, "coverage": coverage, "verification": verified,
                "versions": {"python": platform.python_version(), "dependencies": "Standard library only"},
                "configuration": {"l2_candidates": list(PENALTIES), "epochs": EPOCHS,
                    "objective": "Unweighted mean binary log loss + L2*sum(weights^2)/2; intercept unpenalized.",
                    "transform": "Train-only median imputation -> train-only mean/population SD; scale=1 if constant; append70missing masks. All-empty train field forced to0 with mask1. No class balancing, resampling, clipping or feature selection.",
                    "model_selection": "Highest validation average precision; exact tie keeps first L2.",
                    "threshold_selection": "Highest validation F1 among .01,.02,.05,.1,.2,.5; exact ties favor larger threshold. Exploratory tradeoff, not clinically chosen.",
                    "randomness": "None; no seed, no shuffling; existing athleteos-research-v1 partition preserved.",
                    "test_policy": "No test predictions in train. Freeze artifact and thresholds before separate test command; no refit."},
                "validation": validations, "artifact": hashes(output / "model.json"),
                "code": {name: hashes(Path(__file__).with_name(name)) for name in
                         ("runners_training.py", "prepare.py", "verify.py", "training.py")}}
    new_json(output / "frozen.json", manifest)
    return {"model_version": VERSION, "directory": str(output), "test_evaluated": False,
            "selected": {scheme: {"l2": bundle["selected_l2"], "threshold": bundle["threshold"],
                         "validation_ap": validations[scheme]["selected"]["average_precision"]}
                         for scheme, bundle in bundles.items()}}


def load_model(directory):
    directory = inside(directory)
    manifest = read_json(directory / "frozen.json")
    if manifest["model_version"] != VERSION or manifest["features"] != FEATURES or manifest["contract_version"] != 1:
        raise ResearchError("Frozen feature/model contract mismatch.")
    if hashes(directory / "model.json") != manifest["artifact"]:
        raise ResearchError("Frozen model hash mismatch.")
    model = read_json(directory / "model.json")
    if model["model_version"] != VERSION or model["features"] != FEATURES or set(model["schemes"]) != set(SCHEMES):
        raise ResearchError("Model contract mismatch.")
    for bundle in model["schemes"].values():
        if len(bundle["transform"]) != 70 or len(bundle["classifier"]["weights"]) != 140:
            raise ResearchError("Invalid fitted parameter width.")
        for column in bundle["transform"]:
            if (type(column["count"]) is not int or column["count"] < 0
                    or not all(numeric(column[key]) for key in ("median", "mean", "sd")) or column["sd"] < 0):
                raise ResearchError("Invalid fitted transform.")
        if (not all(numeric(v) for v in bundle["classifier"]["weights"])
                or not numeric(bundle["classifier"]["intercept"])
                or not numeric(bundle["threshold"]) or not 0 < bundle["threshold"] <= 1):
            raise ResearchError("Invalid logistic parameters/threshold.")
    return model, manifest


def evaluate(directory=DEFAULT_MODEL, prepared=DEFAULT_DATA):
    directory = inside(directory)
    model, manifest = load_model(directory)
    data, coverage, fingerprints, _ = load_data(prepared)
    if fingerprints != manifest["dataset_fingerprints"] or coverage != manifest["coverage"]:
        raise ResearchError("Evaluation preparation changed after model freeze.")
    results = {}
    for scheme, bundle in model["schemes"].items():
        test = data[scheme]["test"]
        scores = probabilities(bundle["classifier"], transform(test["X"], bundle["transform"]))
        dummy = [bundle["dummy_score"]] * len(test["y"])
        results[scheme] = {"coverage": coverage[scheme]["test"],
                          "selected_threshold": binary_metrics(test["y"], scores, bundle["threshold"]),
                          "default_0_5": binary_metrics(test["y"], scores, .5),
                          "dummy_most_frequent": binary_metrics(test["y"], dummy, .5)}
    result = {"model_version": VERSION, "frozen_manifest": hashes(directory / "frozen.json"),
              "artifact": manifest["artifact"], "schemes": results,
              "scope": "Retrospective source-label evaluation. Temporal scheme permits same people across periods; grouped scheme tests different people. No clinical/predictive deployment claim."}
    path = directory / "evaluation.json"
    if path.exists():
        if read_json(path) != result:
            raise ResearchError("Existing test evaluation differs; never overwrite it to tune.")
    else:
        new_json(path, result)
    return result


def infer(directory, payload):
    if (not isinstance(payload, dict) or set(payload) != {"contract_version", "features"}
            or type(payload["contract_version"]) is not int or payload["contract_version"] != 1):
        raise ResearchError("Require exactly contract_version=1 and source daily features.")
    raw = vector(payload["features"])
    model, _ = load_model(directory)
    bundle = model["schemes"]["subject-disjoint"]
    score = probabilities(bundle["classifier"], transform([raw], bundle["transform"]))[0]
    return {"model_version": VERSION, "scheme": "subject-disjoint", "score": score,
            "threshold": bundle["threshold"], "source_label_prediction": int(score >= bundle["threshold"]),
            "scope": "Uncalibrated source-label research score, not individual clinical risk or intervention."}


def sample_input(prepared, output):
    output = inside(output)
    verify_prepared(inside(prepared))
    with (inside(prepared) / "subject-disjoint" / "records.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["split"] == "test":
                vector(row["features"])
                output.parent.mkdir(parents=True, exist_ok=True)
                new_json(output, {"contract_version": 1, "features": row["features"]})
                return {"input_written": str(output), "privacy": "Individual features; local only."}
    raise ResearchError("No test source record.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fit = commands.add_parser("train")
    fit.add_argument("--prepared", default=str(DEFAULT_DATA))
    fit.add_argument("--output", default=str(DEFAULT_MODEL))
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("--prepared", default=str(DEFAULT_DATA))
    evaluation.add_argument("--model", default=str(DEFAULT_MODEL))
    prediction = commands.add_parser("infer")
    prediction.add_argument("--model", default=str(DEFAULT_MODEL))
    prediction.add_argument("--input", required=True)
    prediction.add_argument("--output", required=True)
    example = commands.add_parser("sample-input")
    example.add_argument("--prepared", default=str(DEFAULT_DATA))
    example.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "train":
            result = train(args.prepared, args.output)
        elif args.command == "evaluate":
            result = evaluate(args.model, args.prepared)
        elif args.command == "sample-input":
            result = sample_input(args.prepared, args.output)
        else:
            output = inside(args.output)
            prediction_result = infer(args.model, read_json(inside(args.input)))
            output.parent.mkdir(parents=True, exist_ok=True)
            new_json(output, prediction_result)
            result = {"prediction_written": str(output), "privacy": "Individual prediction, keep local."}
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ResearchError, OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Runner research error: {error}\n")


if __name__ == "__main__":
    main()
