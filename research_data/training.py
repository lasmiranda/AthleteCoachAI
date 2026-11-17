"""Reproducible, standard-library PAMAP2 Gaussian Naive Bayes baseline."""

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
from research_data.pamap2 import ACTIVITIES, CHANNELS, FEATURES
from research_data.prepare import SPLITS, Moments
from research_data.verify import verify_prepared

LABELS = (1, 2, 3, 4, 5, 6, 7, 12, 13, 16, 17, 24)
SMOOTHING = (1e-9, 1e-3)
VERSION = "pamap2-activity-gnb-v1"
DEFAULT_PREPARED = DATA_ROOT / "prepared" / "pamap2-protocol-v1"
DEFAULT_MODEL = DATA_ROOT / "models" / "pamap2-gnb-v1"


def inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(DATA_ROOT.resolve()):
        raise ResearchError("Research inputs/artifacts must remain inside ignored .research-data.")
    return path


def read_json(path):
    def reject_constant(value):
        raise ResearchError(f"Nonstandard JSON numeric constant: {value}.")
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject_constant)


def new_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def numeric(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def feature_vector(values):
    if not isinstance(values, dict) or set(values) != set(FEATURES):
        raise ResearchError("Require exactly the 120 raw PAMAP2 feature names; metadata/labels are forbidden.")
    for name in FEATURES:
        if values[name] is not None and not numeric(values[name]):
            raise ResearchError(f"{name}: require a finite number or explicit null.")
    for channel in CHANNELS:
        fraction = values[f"{channel}__observed_fraction"]
        mean, sd = values[f"{channel}__mean"], values[f"{channel}__sd"]
        if fraction is None or not 0 <= fraction <= 1:
            raise ResearchError(f"{channel}: observed_fraction must be finite in [0,1].")
        if fraction == 0:
            if mean is not None or sd is not None:
                raise ResearchError(f"{channel}: zero observations require null mean and SD.")
        elif mean is None or sd is None or sd < 0:
            raise ResearchError(f"{channel}: observed samples require finite mean and nonnegative SD.")
    if not any(values[f"{channel}__observed_fraction"] > 0 for channel in CHANNELS):
        raise ResearchError("No observed sensor channels; cannot classify an entirely missing window.")
    return [values[name] for name in FEATURES]


def load_data(prepared):
    prepared = inside(prepared)
    verified = verify_prepared(prepared)
    summary, dictionary = read_json(prepared / "summary.json"), read_json(prepared / "dictionary.json")
    if (verified["source"] != "pamap2" or summary["pipeline_version"] != 1
            or dictionary["features"] != FEATURES
            or set(summary["schemes"]) != {"subject-disjoint"}):
        raise ResearchError("Only verified PAMAP2 v1 Protocol subject-disjoint preparations are supported.")
    groups = {split: set() for split in SPLITS}
    arrays = {split: {"X": [], "y": []} for split in SPLITS}
    with (prepared / "subject-disjoint" / "records.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if type(row["label"]) is not int or row["label"] not in LABELS:
                raise ResearchError("Unexpected Protocol label.")
            split = row["split"]
            groups[split].add(row["subject_id"])
            arrays[split]["X"].append(feature_vector(row["features"]))
            arrays[split]["y"].append(row["label"])
    if any(groups[a] & groups[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
        raise ResearchError("Training/evaluation subjects overlap.")
    if len(set(arrays["train"]["y"])) < 2:
        raise ResearchError("Training requires at least two observed activity classes.")
    coverage = {}
    for split in SPLITS:
        x, y = arrays[split]["X"], arrays[split]["y"]
        counts = Counter(y)
        coverage[split] = {
            "windows": len(y), "subjects": len(groups[split]),
            "labels": {str(label): counts[label] for label in LABELS},
            "missing_classes": [ACTIVITIES[label] for label in LABELS if not counts[label]],
            "null_feature_cells": sum(value is None for row in x for value in row),
            "null_cells_by_feature": {name: sum(row[i] is None for row in x) for i, name in enumerate(FEATURES)},
            "mean_sensor_observed_fraction": statistics.mean(value for row in x for value in row[2::3]),
            "windows_with_incomplete_sensor_samples": sum(any(value < 1 for value in row[2::3]) for row in x),
        }
    fingerprints = {name: hashes(prepared / name) for name in
                    ("summary.json", "dictionary.json", "subject-disjoint/records.jsonl")}
    return arrays, coverage, fingerprints, verified


def fit_transform(x):
    if not x or any(len(row) != len(FEATURES) for row in x):
        raise ResearchError("Training requires nonempty aligned raw feature vectors.")
    columns = []
    for i in range(len(FEATURES)):
        observed = [row[i] for row in x if row[i] is not None]
        median = statistics.median(observed) if observed else 0.0
        moments = Moments()
        for row in x:
            moments.add(median if row[i] is None else row[i])
        stats = moments.result()
        columns.append({"observed_count": len(observed), "median": median,
                        "mean": stats["mean"], "population_sd": stats["population_sd"]})
    return columns


def transform(x, columns):
    if len(columns) != len(FEATURES):
        raise ResearchError("Transform feature count mismatch.")
    result = []
    for row in x:
        if len(row) != len(FEATURES):
            raise ResearchError("Feature vector length mismatch.")
        values, masks = [], []
        for value, stats in zip(row, columns):
            missing = value is None or not stats["observed_count"]
            filled = stats["median"] if missing else value
            scaled = (filled - stats["mean"]) / (stats["population_sd"] or 1)
            if not math.isfinite(scaled):
                raise ResearchError("Feature outside finite transform arithmetic range.")
            values.append(scaled)
            masks.append(int(missing))
        result.append(values + masks)
    return result


def fit_gaussian(x, y, smoothing):
    if not x or len(x) != len(y) or smoothing not in SMOOTHING:
        raise ResearchError("Invalid Gaussian training arrays/configuration.")
    width = len(x[0])
    total = [Moments() for _ in range(width)]
    grouped = {label: [Moments() for _ in range(width)] for label in sorted(set(y))}
    counts = Counter(y)
    for row, label in zip(x, y):
        for i, value in enumerate(row):
            total[i].add(value)
            grouped[label][i].add(value)
    epsilon = smoothing * max(1.0, max(stats.result()["population_sd"] ** 2 for stats in total))
    return {"epsilon": epsilon, "classes": [
        {"label": label, "count": counts[label], "prior": counts[label] / len(y),
         "mean": [stats.mean for stats in grouped[label]],
         "variance": [stats.result()["population_sd"] ** 2 + epsilon for stats in grouped[label]]}
        for label in sorted(grouped)]}


def predict(model, x):
    predictions = []
    for row in x:
        if not model["classes"] or len(row) != len(model["classes"][0]["mean"]):
            raise ResearchError("Classifier feature vector length mismatch.")
        scored = []
        for group in model["classes"]:
            score = math.log(group["prior"])
            for value, mean, variance in zip(row, group["mean"], group["variance"]):
                delta = value - mean
                score -= 0.5 * (math.log(2 * math.pi * variance) + delta * delta / variance)
            if not math.isfinite(score):
                raise ResearchError("Feature outside finite classifier arithmetic range.")
            scored.append((score, -group["label"]))
        predictions.append(-max(scored)[1])
    return predictions


def metrics(y, prediction):
    if not y or len(y) != len(prediction) or any(label not in LABELS for label in y + prediction):
        raise ResearchError("Metrics require nonempty aligned known-class labels.")
    matrix = [[0] * len(LABELS) for _ in LABELS]
    for actual, predicted in zip(y, prediction):
        matrix[LABELS.index(actual)][LABELS.index(predicted)] += 1
    classes = {}
    for i, label in enumerate(LABELS):
        tp, support = matrix[i][i], sum(matrix[i])
        predicted_count = sum(row[i] for row in matrix)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        classes[str(label)] = {"name": ACTIVITIES[label], "precision": precision, "recall": recall,
                              "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
                              "support": support, "predicted_count": predicted_count,
                              "precision_defined": predicted_count > 0, "recall_defined": support > 0}
    present = [group for group in classes.values() if group["support"]]
    return {"accuracy": sum(matrix[i][i] for i in range(len(LABELS))) / len(y),
            "macro_f1": sum(group["f1"] for group in classes.values()) / len(LABELS),
            "balanced_accuracy": sum(group["recall"] for group in present) / len(present),
            "per_class": classes, "confusion_matrix": matrix, "label_order": list(LABELS),
            "metric_scope": "Macro-F1 over the fixed 12 classes; balanced accuracy over classes present in y. Undefined precision/recall/F1=0, explicitly flagged; see support."}


def train(prepared=DEFAULT_PREPARED, output=DEFAULT_MODEL):
    output = inside(output)
    if output.exists():
        raise ResearchError("Model output exists; preserve the frozen run and choose a new --output.")
    arrays, coverage, fingerprints, verified = load_data(prepared)
    x, y = arrays["train"]["X"], arrays["train"]["y"]
    columns = fit_transform(x)
    transformed_train = transform(x, columns)
    transformed_val = transform(arrays["validation"]["X"], columns)
    candidates = []
    selected, selected_score, selected_smoothing = None, -1.0, None
    for smoothing in SMOOTHING:
        candidate = fit_gaussian(transformed_train, y, smoothing)
        score = metrics(arrays["validation"]["y"], predict(candidate, transformed_val))
        candidates.append({"var_smoothing": smoothing, "validation": score})
        if score["macro_f1"] > selected_score:
            selected, selected_score, selected_smoothing = candidate, score["macro_f1"], smoothing
    counts = Counter(y)
    dummy = min(counts, key=lambda label: (-counts[label], label))
    output.mkdir(parents=True, exist_ok=False)
    new_json(output / "status.json", {"status": "incomplete until frozen.json exists"})
    new_json(output / "model.json", {"model_version": VERSION, "features": FEATURES, "transform": columns,
                                    "classifier": selected, "dummy_label": dummy})
    config = {"family": "Gaussian Naive Bayes", "var_smoothing_candidates": list(SMOOTHING),
              "selected_var_smoothing": selected_smoothing, "class_priors": "Training class frequencies.",
              "random_seed": None, "determinism": "No randomness, resampling, split changes or parallel arithmetic.",
              "selection": "Highest validation macro-F1; exact ties keep first candidate (1e-9). No refit on validation.",
              "preprocessing": "Raw features -> train-only median imputation -> train-only mean/population-SD scaling; scale=1 if constant. Append 120 explicit missing masks. All-empty train columns remain unavailable/0 with mask=1.",
              "variance": "Per-class population variance + var_smoothing * max(1, largest global transformed training variance).",
              "numeric_policy": "Natural-log Gaussian likelihood; exact ties choose lowest class ID; finite arithmetic required."}
    manifest = {"model_version": VERSION, "contract_version": 1,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "task": "PAMAP2 Protocol activity classification, not readiness/fatigue or medical inference.",
                "source": {"citation": "Reiss, A. (2012). PAMAP2. https://doi.org/10.24432/C5NW2H",
                           "license": "CC BY 4.0", "scope": "Nine Protocol recordings only; fixed subject-disjoint windows."},
                "features": FEATURES, "label_map": {str(label): ACTIVITIES[label] for label in LABELS},
                "versions": {"python": platform.python_version(), "dependencies": "Python standard library only"},
                "configuration": config,
                "prepared_directory": str(inside(prepared).relative_to(DATA_ROOT)),
                "dataset_fingerprints": fingerprints, "coverage": coverage, "verification": verified,
                "validation_candidates": candidates,
                "dummy_validation": metrics(arrays["validation"]["y"], [dummy] * len(arrays["validation"]["y"])),
                "artifact": hashes(output / "model.json"),
                "code": {name: hashes(Path(__file__).with_name(name)) for name in
                         ("training.py", "pamap2.py", "prepare.py", "verify.py", "acquire.py")},
                "test_policy": "No held-out test predictions or metrics computed by train. Configuration/artifact frozen here before separate evaluate."}
    new_json(output / "frozen.json", manifest)
    return {"model_directory": str(output), "version": VERSION, "selected_var_smoothing": selected_smoothing,
            "validation_macro_f1": selected_score, "test_evaluated": False}


def load_model(directory):
    directory = inside(directory)
    manifest = read_json(directory / "frozen.json")
    if (manifest["model_version"] != VERSION or manifest["contract_version"] != 1
            or manifest["features"] != FEATURES
            or manifest["label_map"] != {str(label): ACTIVITIES[label] for label in LABELS}):
        raise ResearchError("Unsupported model/feature contract.")
    if hashes(directory / "model.json") != manifest["artifact"]:
        raise ResearchError("Frozen artifact hash mismatch; refusing to load.")
    if (directory / "model.json").stat().st_size > 5 * 1024 * 1024:
        raise ResearchError("Model exceeds the JSON size guard.")
    bundle = read_json(directory / "model.json")
    if bundle["model_version"] != VERSION or bundle["features"] != FEATURES or len(bundle["transform"]) != len(FEATURES):
        raise ResearchError("Invalid fitted feature contract.")
    for stats in bundle["transform"]:
        if (type(stats["observed_count"]) is not int or stats["observed_count"] < 0
                or not all(numeric(stats[key]) for key in ("median", "mean", "population_sd"))
                or stats["population_sd"] < 0):
            raise ResearchError("Invalid fitted transform.")
    groups = bundle["classifier"]["classes"]
    if (not groups or len({group["label"] for group in groups}) != len(groups)
            or any(group["label"] not in LABELS for group in groups) or bundle["dummy_label"] not in LABELS):
        raise ResearchError("Invalid fitted class labels.")
    for group in groups:
        if (len(group["mean"]) != 2 * len(FEATURES) or len(group["variance"]) != 2 * len(FEATURES)
                or not all(numeric(value) for value in group["mean"])
                or not all(numeric(value) and value > 0 for value in group["variance"])
                or not numeric(group["prior"]) or not 0 < group["prior"] <= 1):
            raise ResearchError("Invalid fitted Gaussian parameters.")
    return bundle, manifest


def evaluate(directory=DEFAULT_MODEL, prepared=DEFAULT_PREPARED):
    directory = inside(directory)
    bundle, manifest = load_model(directory)
    arrays, coverage, fingerprints, _ = load_data(prepared)
    if fingerprints != manifest["dataset_fingerprints"] or coverage != manifest["coverage"]:
        raise ResearchError("Evaluation data differs from the frozen training run.")
    test = arrays["test"]
    result = {"model_version": VERSION, "frozen_manifest": hashes(directory / "frozen.json"),
              "model_artifact": manifest["artifact"], "dataset_fingerprints": fingerprints,
              "split": "test; two held-out subjects in the real benchmark",
              "windows": len(test["y"]), "coverage": coverage["test"],
              "classifier": metrics(test["y"], predict(bundle["classifier"], transform(test["X"], bundle["transform"]))),
              "dummy": metrics(test["y"], [bundle["dummy_label"]] * len(test["y"])),
              "limitation": "Correlated windows from nine people, only two test subjects; not population/clinical validation. No tuning after test."}
    path = directory / "evaluation.json"
    if path.exists():
        if read_json(path) != result:
            raise ResearchError("Existing test evaluation differs; do not overwrite or tune the frozen run.")
    else:
        new_json(path, result)
    confusion = directory / "test-confusion.csv"
    if not confusion.exists():
        with confusion.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["actual/predicted"] + [ACTIVITIES[label] for label in LABELS])
            for label, row in zip(LABELS, result["classifier"]["confusion_matrix"]):
                writer.writerow([ACTIVITIES[label]] + row)
    return result


def infer(directory, payload):
    if not isinstance(payload, dict) or set(payload) != {"contract_version", "features"} or type(payload["contract_version"]) is not int or payload["contract_version"] != 1:
        raise ResearchError("Input requires exactly contract_version=1 and features; no labels/metadata.")
    vector = feature_vector(payload["features"])
    bundle, _ = load_model(directory)
    label = predict(bundle["classifier"], transform([vector], bundle["transform"]))[0]
    return {"model_version": VERSION, "activity_id": label, "activity": ACTIVITIES[label],
            "scope": "Research activity classification; no calibrated confidence or readiness."}


def sample_input(prepared, output):
    output = inside(output)
    verify_prepared(inside(prepared))
    with (inside(prepared) / "subject-disjoint" / "records.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["split"] == "test":
                feature_vector(row["features"])
                output.parent.mkdir(parents=True, exist_ok=True)
                new_json(output, {"contract_version": 1, "features": row["features"]})
                return {"input_written": str(output), "privacy": "Individual sensor features; keep local and ignored."}
    raise ResearchError("No test window available for local inference.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fit = commands.add_parser("train")
    fit.add_argument("--prepared", default=str(DEFAULT_PREPARED))
    fit.add_argument("--output", default=str(DEFAULT_MODEL))
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("--prepared", default=str(DEFAULT_PREPARED))
    evaluation.add_argument("--model", default=str(DEFAULT_MODEL))
    prediction = commands.add_parser("infer")
    prediction.add_argument("--model", default=str(DEFAULT_MODEL))
    prediction.add_argument("--input", required=True)
    prediction.add_argument("--output", required=True)
    example = commands.add_parser("sample-input")
    example.add_argument("--prepared", default=str(DEFAULT_PREPARED))
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
            result = {"prediction_written": str(output), "privacy": "Individual prediction retained locally."}
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ResearchError, OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Research training error: {error}\n")


if __name__ == "__main__":
    main()
