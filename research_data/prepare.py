"""Reproducible research tables; no join with the AthleteOS demo or across sources."""

import csv
import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from research_data.acquire import DATA_ROOT, ResearchError, hashes, local_root, sources, validate_file

DAY = ["nr. sessions", "total km", "km Z3-4", "km Z5-T1-T2", "km sprinting",
       "strength training", "hours alternative", "perceived exertion",
       "perceived trainingSuccess", "perceived recovery"]
WEEK = ["nr. sessions", "nr. rest days", "total kms", "max km one day", "total km Z3-Z4-Z5-T1-T2",
        "nr. tough sessions (effort in Z5, T1 or T2)", "nr. days with interval session",
        "total km Z3-4", "max km Z3-4 one day", "total km Z5-T1-T2", "max km Z5-T1-T2 one day",
        "total hours alternative training", "nr. strength trainings", "avg exertion", "min exertion",
        "max exertion", "avg training success", "min training success", "max training success",
        "avg recovery", "min recovery", "max recovery"]
RATIOS = ["rel total kms week 0_1", "rel total kms week 0_2", "rel total kms week 1_2"]
SPLITS = ("train", "validation", "test")
SEED = "athleteos-research-v1"


def expanded(base, count):
    return [f"{name}.{lag}" if lag else name for lag in range(count) for name in base]


def finite(value, name):
    if value in ("", "NaN", "nan", None):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ResearchError(f"{name}: expected numeric or explicit missing value.") from None
    if not math.isfinite(result):
        raise ResearchError(f"{name}: infinite values are not accepted.")
    return result


def integer(value, name):
    result = finite(value, name)
    if result is None or result < 0 or not result.is_integer():
        raise ResearchError(f"{name}: expected nonnegative integer.")
    return int(result)


def runner_features(approach):
    if approach not in {"day", "week"}:
        raise ResearchError("Choose day or week approach; never concatenate their overlapping events.")
    return expanded(DAY if approach == "day" else WEEK, 7 if approach == "day" else 3)


def runner_rows(path, approach):
    features = runner_features(approach)
    expected = features + ["Athlete ID", "injury"] + (RATIOS if approach == "week" else []) + ["Date"]
    seen = set()
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != expected:
            raise ResearchError("Runners schema changed: headers/order do not match reviewed source v2.")
        for line, raw in enumerate(reader, 2):
            if None in raw or any(v is None for v in raw.values()):
                raise ResearchError(f"Runners row {line}: incorrect column count.")
            subject = str(integer(raw["Athlete ID"], "Athlete ID"))
            day = integer(raw["Date"], "Date")
            label = integer(raw["injury"], "injury")
            if label not in {0, 1}:
                raise ResearchError("injury label must be the source binary 0/1.")
            if (subject, day) in seen:
                raise ResearchError("Duplicate subject/event day; resolve provenance before splitting.")
            seen.add((subject, day))
            values = {}
            for name in features:
                value = finite(raw[name], name)
                subjective = any(term in name for term in ("perceived", "exertion", "success", "recovery"))
                if subjective and value == -0.01:
                    value = None
                if value is not None and value < 0:
                    raise ResearchError(f"{name}: unexpected negative source value.")
                values[name] = value
            yield {"row_id": f"runners-{approach}:{line}", "subject_id": subject,
                   "event_day": day, "label": label, "features": values}


def subject_assignments(subjects):
    ordered = sorted(set(subjects), key=lambda s: hashlib.sha256(f"{SEED}:{s}".encode()).hexdigest())
    if len(ordered) < 5:
        raise ResearchError("At least five subjects required for meaningful nonempty grouped partitions.")
    train_end = max(1, int(len(ordered) * 0.6))
    val_end = train_end + max(1, round(len(ordered) * 0.2))
    return {subject: "train" if i < train_end else "validation" if i < val_end else "test"
            for i, subject in enumerate(ordered)}


class Moments:
    def __init__(self):
        self.n, self.mean, self.m2 = 0, 0.0, 0.0

    def add(self, value):
        if value is None:
            return
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)

    def result(self):
        return {"count": self.n, "mean": self.mean if self.n else None,
                "population_sd": math.sqrt(max(0, self.m2 / self.n)) if self.n else None}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_partition_tables(row_factory, features, assignment, directory):
    """Two passes: train-only fit, then write aligned X/y/index and nullable raw records."""
    directory.mkdir()
    moments = {name: Moments() for name in features}
    for row in row_factory():
        if assignment(row) == "train":
            for name in features:
                moments[name].add(row["features"][name])
    transforms = {name: stats.result() for name, stats in moments.items()}
    if not any(item["count"] for item in transforms.values()):
        raise ResearchError("No observed training features; no success-shaped empty preparation.")
    write_json(directory / "transforms.json", {"fit_split": "train", "method": "z-score",
               "missing": "Preserve null/blank; no imputation. Missing masks in X are explicit.",
               "constant": "Observed constant training columns use scale=1; not evidence of informativeness.",
               "columns": transforms})
    counts = {split: Counter() for split in SPLITS}
    subjects = {split: set() for split in SPLITS}
    times = {split: [] for split in SPLITS}
    missing = {split: Counter() for split in SPLITS}
    purged = 0
    with ExitStack() as stack:
        writers = {}
        raw_stream = stack.enter_context((directory / "records.jsonl").open("w", encoding="utf-8"))
        for split in SPLITS:
            x = csv.writer(stack.enter_context((directory / f"{split}.features.csv").open("w", newline="", encoding="utf-8")))
            y = csv.writer(stack.enter_context((directory / f"{split}.labels.csv").open("w", newline="", encoding="utf-8")))
            index = csv.writer(stack.enter_context((directory / f"{split}.index.csv").open("w", newline="", encoding="utf-8")))
            x.writerow(features + [f"{name}__missing" for name in features])
            y.writerow(["row_id", "label"])
            index.writerow(["row_id", "source_subject_pseudonym", "relative_time", "split"])
            writers[split] = x, y, index
        for row in row_factory():
            split = assignment(row)
            if split is None:
                purged += 1
                continue
            if split not in SPLITS:
                raise ResearchError("Invalid split assignment.")
            values = row["features"]
            normalized = []
            masks = []
            for name in features:
                value, fitted = values[name], transforms[name]
                missing[split][name] += value is None
                # All-missing train columns remain missing even if later observed.
                normalized.append((value - fitted["mean"]) / (fitted["population_sd"] or 1)
                                  if value is not None and fitted["count"] else "")
                masks.append(int(value is None or not fitted["count"]))
            x, y, index = writers[split]
            relative_time = row.get("relative_time", row.get("event_day"))
            x.writerow(normalized + masks)
            y.writerow([row["row_id"], row["label"]])
            index.writerow([row["row_id"], row["subject_id"], relative_time, split])
            raw_stream.write(json.dumps({**row, "split": split}, allow_nan=False) + "\n")
            counts[split][str(row["label"])] += 1
            subjects[split].add(row["subject_id"])
            times[split].append(relative_time)
    coverage = {split: {"rows": sum(counts[split].values()), "subjects": len(subjects[split]),
                       "classes": dict(sorted(counts[split].items())),
                       "relative_time_min": min(times[split]) if times[split] else None,
                       "relative_time_max": max(times[split]) if times[split] else None,
                       "missing_feature_cells": sum(missing[split].values())} for split in SPLITS}
    if any(not entry["rows"] for entry in coverage.values()):
        raise ResearchError("An evaluation partition is empty; revise scope before claiming training readiness.")
    overlaps = {f"{a}/{b}": len(subjects[a] & subjects[b])
                for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))}
    all_classes = set.union(*(set(counts[s]) for s in SPLITS))
    report = {"coverage": coverage, "purged_rows": purged, "subject_overlap_counts": overlaps,
              "class_coverage_warnings": [f"{s} lacks label {c}" for s in SPLITS for c in sorted(all_classes) if c not in counts[s]],
              "all_missing_training_features": [name for name, stats in transforms.items() if not stats["count"]],
              "constant_training_features": [name for name, stats in transforms.items() if stats["count"] and stats["population_sd"] == 0],
              "outputs": {p.name: hashes(p) for p in sorted(directory.iterdir()) if p.is_file()}}
    write_json(directory / "summary.json", report)
    return report


def prepare_runners(approach, root=DATA_ROOT, output=None):
    root = local_root(root)
    spec = next(f for f in sources()["runners"]["files"] if f["name"].startswith(f"{approach}_"))
    path = root / "raw" / "runners" / spec["name"]
    verified = validate_file(path, spec)
    features = runner_features(approach)
    subjects, dates, classes, n = set(), set(), Counter(), 0
    for row in runner_rows(path, approach):
        subjects.add(row["subject_id"])
        dates.add(row["event_day"])
        classes[str(row["label"])] += 1
        n += 1
    grouped = subject_assignments(subjects)
    dates = sorted(dates)
    if len(dates) < 5:
        raise ResearchError("Insufficient relative-date coverage.")
    cut1, cut2 = dates[int(len(dates) * 0.6) - 1], dates[int(len(dates) * 0.8) - 1]
    lookback = 7 if approach == "day" else 21

    def temporal(row):
        day = row["event_day"]
        if day <= cut1:
            return "train"
        if cut1 + lookback < day <= cut2:
            return "validation"
        if day > cut2 + lookback:
            return "test"
        return None

    final = (Path(output) if output else root / "prepared" / f"runners-{approach}-v1").resolve()
    local_root(final.parent)
    if final.exists():
        raise ResearchError("Output exists; preserve the prior run and choose a new --output path.")
    if shutil.disk_usage(root).free < 512 * 1024 * 1024:
        raise ResearchError("Preparation requires at least 512 MiB free for tables and safety reserve.")
    staging = Path(tempfile.mkdtemp(prefix="runners-staging-", dir=final.parent))
    try:
        factory = lambda: runner_rows(path, approach)
        by_subject = write_partition_tables(factory, features, lambda row: grouped[row["subject_id"]], staging / "subject-disjoint")
        if any(by_subject["subject_overlap_counts"].values()):
            raise ResearchError("Subject leakage detected.")
        by_time = write_partition_tables(factory, features, temporal, staging / "temporal-purged")
        coverage = by_time["coverage"]
        if coverage["validation"]["relative_time_min"] - lookback <= coverage["train"]["relative_time_max"]:
            raise ResearchError("Temporal training/validation input windows overlap.")
        if coverage["test"]["relative_time_min"] - lookback <= coverage["validation"]["relative_time_max"]:
            raise ResearchError("Temporal validation/test input windows overlap.")
        dictionary = {"source": "runners", "approach": approach, "label": "Source injury event 0/1; research label, not a medical product.",
                      "identifier_role": "Masked subject ID for grouped splitting only; never an X feature.",
                      "time": "Source Date: integer days relative to first dataset record; no calendar date or timezone asserted.",
                      "features": features, "excluded": ["Athlete ID", "Date", "injury"] + (RATIOS if approach == "week" else []),
                      "missing": "Source subjective -0.01 rest-day sentinel converted to null, not zero recovery.",
                      "suffix_mapping": "day: base lag=7 days before event, .6=1 day before; week: base=preceding week, .2=third preceding week (corrected README v2).",
                      "units": "Source km/hours/counts/indicator fields; subjective scales preserved as supplied, not equated to AthleteOS RPE 0-10.",
                      "normalization": "Source ratios excluded because their exact derivation/zero handling is not documented in README. Z-scores fit only on each scheme's train partition.",
                      "no_join": "Day/week are alternative overlapping event representations; do not concatenate or use one as external validation of the other."}
        write_json(staging / "dictionary.json", dictionary)
        report = {"pipeline_version": 1, "source": "runners", "approach": approach, "source_integrity": verified,
                  "rows": n, "subjects": len(subjects), "features": len(features), "classes": dict(classes),
                  "date_range": [dates[0], dates[-1]], "scope": "Full selected official CSV, no row sampling.",
                  "split_seed": SEED, "primary": "subject-disjoint 60/20/20 by deterministic subject hash; no test-label stratification.",
                  "temporal": {"cut_days": [cut1, cut2], "purge_days": lookback,
                               "interpretation": "Known-cohort forward-time benchmark; same subjects may recur, raw input windows across boundaries do not."},
                  "schemes": {"subject-disjoint": by_subject, "temporal-purged": by_time}}
        write_json(staging / "summary.json", report)
        staging.rename(final)
        return report
    except Exception:
        shutil.rmtree(staging)
        raise
