"""Verify prepared files against nullable raw rows and train-only fitted transforms."""

import csv
import json
import math
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from research_data.acquire import DATA_ROOT, ResearchError, hashes
from research_data.prepare import SPLITS, Moments


def verify_prepared(directory):
    directory = Path(directory).resolve()
    if not directory.is_relative_to(DATA_ROOT.resolve()):
        raise ResearchError("Verification input must stay inside ignored .research-data.")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    dictionary = json.loads((directory / "dictionary.json").read_text(encoding="utf-8"))
    features = dictionary["features"]
    result = {}
    for scheme, report in summary["schemes"].items():
        path = directory / scheme
        for name, expected in report["outputs"].items():
            if Path(name).name != name or hashes(path / name) != expected:
                raise ResearchError("Output hash/name mismatch; do not train on a modified run.")
        transforms = json.loads((path / "transforms.json").read_text(encoding="utf-8"))
        if transforms["fit_split"] != "train" or set(transforms["columns"]) != set(features):
            raise ResearchError("Transform provenance/schema mismatch.")
        fitted = transforms["columns"]
        counts = {s: Counter() for s in SPLITS}
        subjects = {s: set() for s in SPLITS}
        dates = {s: [] for s in SPLITS}
        seen = set()
        train_stats = {name: Moments() for name in features}
        previous_window_end = {}
        with ExitStack() as stack:
            readers = {}
            for split in SPLITS:
                x = csv.DictReader(stack.enter_context((path / f"{split}.features.csv").open(newline="", encoding="utf-8")))
                y = csv.DictReader(stack.enter_context((path / f"{split}.labels.csv").open(newline="", encoding="utf-8")))
                index = csv.DictReader(stack.enter_context((path / f"{split}.index.csv").open(newline="", encoding="utf-8")))
                if x.fieldnames != features + [f"{name}__missing" for name in features]:
                    raise ResearchError("X contains unapproved fields/order.")
                if y.fieldnames != ["row_id", "label"] or index.fieldnames != ["row_id", "source_subject_pseudonym", "relative_time", "split"]:
                    raise ResearchError("Label/index schema mismatch.")
                readers[split] = x, y, index
            with (path / "records.jsonl").open(encoding="utf-8") as raw:
                for line in raw:
                    row = json.loads(line)
                    split = row["split"]
                    if split not in SPLITS or row["row_id"] in seen:
                        raise ResearchError("Duplicate row or invalid partition.")
                    seen.add(row["row_id"])
                    x_reader, y_reader, index_reader = readers[split]
                    x, y, index = next(x_reader, None), next(y_reader, None), next(index_reader, None)
                    if x is None or y is None or index is None:
                        raise ResearchError("Missing aligned X/y/index rows.")
                    time = row.get("relative_time", row.get("event_day"))
                    if (y["row_id"] != row["row_id"] or y["label"] != str(row["label"])
                            or index["row_id"] != row["row_id"] or index["split"] != split
                            or index["source_subject_pseudonym"] != row["subject_id"]
                            or float(index["relative_time"]) != time):
                        raise ResearchError("X/y/index/raw alignment mismatch.")
                    for name in features:
                        value = row["features"][name]
                        stats = fitted[name]
                        unavailable = value is None or not stats["count"]
                        if x[f"{name}__missing"] != str(int(unavailable)):
                            raise ResearchError("Incorrect missing-value indicator.")
                        if unavailable:
                            if x[name] != "":
                                raise ResearchError("Missing value was silently fabricated.")
                        else:
                            expected = (value - stats["mean"]) / (stats["population_sd"] or 1)
                            actual = float(x[name])
                            if not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10):
                                raise ResearchError("Normalized feature differs from train-only transform.")
                        if split == "train":
                            train_stats[name].add(value)
                    counts[split][str(row["label"])] += 1
                    subjects[split].add(row["subject_id"])
                    dates[split].append(time)
                    if "window_start_s" in row:
                        key = row["subject_id"]
                        if row["window_start_s"] <= previous_window_end.get(key, -1):
                            raise ResearchError("Overlapping sensor windows.")
                        previous_window_end[key] = row["window_end_s"]
            if any(next(reader, None) is not None for readers3 in readers.values() for reader in readers3):
                raise ResearchError("Extra X/y/index rows lack source records.")
        for name in features:
            if train_stats[name].result() != fitted[name]:
                raise ResearchError("Fitted transforms were not calculated exclusively from training records.")
        for split in SPLITS:
            expected = report["coverage"][split]
            if (sum(counts[split].values()) != expected["rows"] or dict(counts[split]) != expected["classes"]
                    or len(subjects[split]) != expected["subjects"]):
                raise ResearchError("Coverage/class summary mismatch.")
        if scheme == "subject-disjoint" and any(subjects[a] & subjects[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
            raise ResearchError("Subject identity leakage.")
        if scheme == "temporal-purged":
            lookback = summary["temporal"]["purge_days"]
            if min(dates["validation"]) - lookback <= max(dates["train"]) or min(dates["test"]) - lookback <= max(dates["validation"]):
                raise ResearchError("Temporal input-window leakage.")
        result[scheme] = {"verified_rows": len(seen), "hashes_match": True,
                          "aligned_tables": True, "train_only_transforms_recomputed": True,
                          "split_integrity": True}
    return {"source": summary["source"], "schemes": result}
