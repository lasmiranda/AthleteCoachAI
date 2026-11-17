"""Safe ZIP inspection and Protocol-only, subject-disjoint PAMAP2 feature windows."""

import io
import json
import math
import re
import shutil
import tempfile
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

from research_data.acquire import CHUNK, DATA_ROOT, ResearchError, hashes, local_root, sources
from research_data.prepare import SEED, Moments, integer, subject_assignments, write_json, write_partition_tables

ACTIVITIES = {1: "lying", 2: "sitting", 3: "standing", 4: "walking", 5: "running",
              6: "cycling", 7: "Nordic walking", 9: "watching TV", 10: "computer work",
              11: "car driving", 12: "ascending stairs", 13: "descending stairs",
              16: "vacuum cleaning", 17: "ironing", 18: "folding laundry",
              19: "house cleaning", 20: "playing soccer", 24: "rope jumping"}
WINDOW_SAMPLES = 500
CHANNELS = {"heart_rate_bpm": 2}
for location, offset in (("hand", 3), ("chest", 20), ("ankle", 37)):
    CHANNELS[f"{location}_temperature_C"] = offset
    for measurement, start, unit in (("accel_16g", 1, "m_s2"), ("accel_6g", 4, "m_s2"),
                                     ("gyro", 7, "rad_s"), ("magnetometer", 10, "uT")):
        for axis_index, axis in enumerate("xyz"):
            CHANNELS[f"{location}_{measurement}_{axis}_{unit}"] = offset + start + axis_index
FEATURES = [f"{channel}__{stat}" for channel in CHANNELS for stat in ("mean", "sd", "observed_fraction")]


def inspect_zip(archive):
    entries = archive.infolist()
    if len(entries) > 200:
        raise ResearchError("Unexpected archive member count.")
    total = 0
    names = set()
    for item in entries:
        name = item.filename
        path = PurePosixPath(name)
        if (name in names or "\\" in name or ":" in name or path.is_absolute()
                or ".." in path.parts or (item.external_attr >> 16) & 0o170000 == 0o120000):
            raise ResearchError("Unsafe/duplicate/symlink archive entry.")
        if item.flag_bits & 1:
            raise ResearchError("Encrypted archives require an access decision, not a bypass.")
        names.add(name)
        total += item.file_size
        if item.file_size > 1024 ** 3 or item.file_size > max(1, item.compress_size) * 500:
            raise ResearchError("Archive entry exceeds safe size/expansion limits.")
    if total > 4 * 1024 ** 3:
        raise ResearchError("Archive expanded size exceeds 4 GiB guard.")
    return entries


def protocol_archive(outer_path, directory):
    try:
        with zipfile.ZipFile(outer_path) as archive:
            entries = inspect_zip(archive)
            if any(re.fullmatch(r"(?:PAMAP2_Dataset/)?Protocol/subject10[1-9]\.dat", e.filename) for e in entries):
                return Path(outer_path)
            nested = [e for e in entries if PurePosixPath(e.filename).name == "PAMAP2_Dataset.zip"]
            if len(nested) != 1:
                raise ResearchError("Expected reviewed PAMAP2_Dataset.zip or Protocol data, not another archive layout.")
            item = nested[0]
            target = directory / "PAMAP2_Dataset.zip"
            if target.exists():
                if target.stat().st_size != item.file_size:
                    raise ResearchError("Cached nested archive size mismatch; inspect local cache.")
                # Verify content against ZIP CRC, not just a filename/size.
                import zlib
                crc = 0
                with target.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(CHUNK), b""):
                        crc = zlib.crc32(chunk, crc)
                if crc != item.CRC:
                    raise ResearchError("Cached nested archive CRC mismatch.")
                return target
            if shutil.disk_usage(directory).free < item.file_size + 512 * 1024 * 1024:
                raise ResearchError("Insufficient disk for fixed-name nested archive plus reserve.")
            temporary = target.with_suffix(".zip.partial")
            if temporary.exists():
                raise ResearchError("Nested archive partial exists; inspect it before retrying.")
            try:
                with archive.open(item) as source, temporary.open("xb") as destination:
                    total = 0
                    while True:
                        chunk = source.read(CHUNK)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > item.file_size:
                            raise ResearchError("Nested archive exceeded declared size.")
                        destination.write(chunk)
                if total != item.file_size:
                    raise ResearchError("Incomplete nested archive.")
                temporary.rename(target)
            except Exception:
                if temporary.exists():
                    temporary.unlink()
                raise
            return target
    except zipfile.BadZipFile as error:
        raise ResearchError("PAMAP2 ZIP format/CRC verification failed.") from error


def sample_values(line):
    if len(line) > 16384:
        raise ResearchError("PAMAP2 sample exceeds the line-size guard.")
    fields = line.split()
    if len(fields) != 54:
        raise ResearchError("PAMAP2 requires exactly 54 columns per sample.")
    values = []
    for field in fields:
        try:
            value = float(field)
        except ValueError:
            raise ResearchError("Invalid PAMAP2 numeric sample.") from None
        if math.isinf(value):
            raise ResearchError("Infinite PAMAP2 value.")
        values.append(None if math.isnan(value) else value)
    if values[0] is None or values[0] < 0:
        raise ResearchError("Missing or negative sensor timestamp.")
    activity = integer(values[1], "activityID")
    if activity not in ACTIVITIES and activity != 0:
        raise ResearchError("Unknown source activityID.")
    return values, activity


def windows_from_lines(lines, subject, audit=None):
    previous_time, active, block_start, size, ordinal = None, None, None, 0, 0
    stats = {channel: Moments() for channel in CHANNELS}
    for line in lines:
        values, activity = sample_values(line)
        timestamp = values[0]
        if previous_time is not None and timestamp <= previous_time:
            raise ResearchError("Non-increasing time within a PAMAP2 recording.")
        if audit is not None:
            audit["raw_samples"] += 1
            audit[f"raw_label_{activity}"] += 1
        contiguous = previous_time is None or abs(timestamp - previous_time - 0.01) <= 0.00001
        if activity != active or not contiguous:
            if audit is not None:
                audit["discarded_boundary_samples"] += size
            size, block_start = 0, timestamp
            stats = {channel: Moments() for channel in CHANNELS}
        active, previous_time = activity, timestamp
        if activity == 0:
            continue
        if not size:
            block_start = timestamp
        for channel, index in CHANNELS.items():
            stats[channel].add(values[index])
        size += 1
        if size == WINDOW_SAMPLES:
            features = {}
            for channel, moment in stats.items():
                result = moment.result()
                features[f"{channel}__mean"] = result["mean"]
                features[f"{channel}__sd"] = result["population_sd"]
                features[f"{channel}__observed_fraction"] = result["count"] / WINDOW_SAMPLES
            ordinal += 1
            yield {"row_id": f"pamap2-protocol:{subject}:{ordinal}", "subject_id": subject,
                   "relative_time": timestamp, "window_start_s": block_start,
                   "window_end_s": timestamp, "label": activity, "features": features}
            size = 0
            stats = {channel: Moments() for channel in CHANNELS}
    if audit is not None:
        audit["discarded_boundary_samples"] += size


def pamap_rows(path, audit=None):
    with zipfile.ZipFile(path) as archive:
        entries = inspect_zip(archive)
        members = sorted((e for e in entries if re.fullmatch(r"(?:PAMAP2_Dataset/)?Protocol/subject10[1-9]\.dat", e.filename)),
                         key=lambda e: e.filename)
        if len(members) != 9:
            raise ResearchError("Expected all nine official Protocol recording files; no silent partial cohort.")
        for item in members:
            subject = PurePosixPath(item.filename).stem.removeprefix("subject")
            with archive.open(item) as binary, io.TextIOWrapper(binary, encoding="ascii") as lines:
                bounded = iter(lambda: lines.readline(16385), "")
                yield from windows_from_lines(bounded, subject, audit)


def prepare_pamap2(root=DATA_ROOT, output=None):
    root = local_root(root)
    directory = root / "raw" / "pamap2"
    outer = directory / "pamap2.zip"
    acquisition = json.loads((directory / "acquisition.json").read_text(encoding="utf-8"))
    integrity = hashes(outer)
    if integrity["sha256"] != acquisition["files"][0]["sha256"]:
        raise ResearchError("Archive changed since acquisition; inspect provenance before preparing.")
    archive_path = protocol_archive(outer, directory)
    final = (Path(output) if output else root / "prepared" / "pamap2-protocol-v1").resolve()
    local_root(final.parent)
    if final.exists():
        raise ResearchError("Output exists; preserve the prior run and choose a new --output path.")
    if shutil.disk_usage(root).free < 512 * 1024 * 1024:
        raise ResearchError("Insufficient preparation disk reserve.")
    staging = Path(tempfile.mkdtemp(prefix="pamap2-staging-", dir=final.parent))
    try:
        audit = Counter()
        subjects, labels, windows = set(), Counter(), 0
        canonical = staging / "windows.jsonl"
        with canonical.open("w", encoding="utf-8") as stream:
            for row in pamap_rows(archive_path, audit):
                subjects.add(row["subject_id"])
                labels[str(row["label"])] += 1
                windows += 1
                stream.write(json.dumps(row, allow_nan=False) + "\n")
        grouped = subject_assignments(subjects)
        if len(subjects) != 9:
            raise ResearchError("A Protocol subject has no usable five-second windows; report and resolve before claiming full cohort.")

        def prepared_rows():
            with canonical.open(encoding="utf-8") as stream:
                for line in stream:
                    yield json.loads(line)

        report = write_partition_tables(prepared_rows, FEATURES,
                                        lambda row: grouped[row["subject_id"]], staging / "subject-disjoint")
        if any(report["subject_overlap_counts"].values()):
            raise ResearchError("PAMAP2 subject leakage.")
        dictionary = {"source": "PAMAP2", "task": "Five-second observed activity classification; not readiness or fatigue.",
                      "scope": "All nine Protocol recordings only; Optional files intentionally excluded from this benchmark.",
                      "label_map": ACTIVITIES, "excluded_label": "0 transient/other",
                      "window": "500 contiguous 100-Hz samples, nonoverlapping, single activity and subject; gaps/label changes reset window.",
                      "time": "Source seconds within recording; no calendar date/timezone.",
                      "channels_zero_based_indices": CHANNELS, "features": FEATURES,
                      "orientation": "Four orientation columns per IMU are invalid per source and excluded.",
                      "HR": "Source HR ~9Hz with NaN; never treat it as HRV or resting HR. Per-window mean/SD/count use observed values only.",
                      "missing": "NaN -> null; observed fraction exposes coverage. No interpolation or imputation.",
                      "normalization": "Mean/population SD fit on training subjects only; no identifier or timestamp in X."}
        write_json(staging / "dictionary.json", dictionary)
        summary = {"pipeline_version": 1, "source": "pamap2", "scope": dictionary["scope"],
                   "source_integrity": integrity, "nested_integrity": hashes(archive_path),
                   "subjects": len(subjects), "windows": windows, "features": len(FEATURES),
                   "classes": dict(labels), "sample_audit": dict(audit), "split_seed": SEED,
                   "schemes": {"subject-disjoint": report}}
        write_json(staging / "summary.json", summary)
        staging.rename(final)
        return summary
    except Exception:
        shutil.rmtree(staging)
        raise
