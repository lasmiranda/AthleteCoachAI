"""Guarded streaming downloads from reviewed official sources, never executing source code."""

import hashlib
import json
import os
import shutil
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / ".research-data"
MANIFEST = Path(__file__).with_name("sources.json")
CHUNK = 1024 * 1024


class ResearchError(ValueError):
    """An actionable acquisition or schema/integrity error."""


def sources():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]


def local_root(path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(DATA_ROOT.resolve()):
        raise ResearchError("Real data/output must stay inside the ignored .research-data directory.")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def hashes(path):
    sha256, sha1 = hashlib.sha256(), hashlib.sha1()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            sha256.update(chunk)
            sha1.update(chunk)
    return {"bytes": Path(path).stat().st_size, "sha256": sha256.hexdigest(), "sha1": sha1.hexdigest()}


def validate_file(path, spec):
    result = hashes(path)
    if result["bytes"] > spec.get("max_bytes", float("inf")):
        raise ResearchError(f"{spec['name']}: exceeds reviewed maximum size.")
    if spec.get("bytes") is not None and result["bytes"] != spec["bytes"]:
        raise ResearchError(f"{spec['name']}: unexpected byte count.")
    if spec.get("sha1") and result["sha1"] != spec["sha1"]:
        raise ResearchError(f"{spec['name']}: published SHA-1 mismatch.")
    return result


def download(spec, directory, byte_limit=64 * 1024 * 1024):
    directory = local_root(directory)
    if Path(spec["name"]).name != spec["name"] or any(c in spec["name"] for c in ("\\", "/", ":")):
        raise ResearchError("Source file name must be a safe basename.")
    if not spec["url"].startswith("https://"):
        raise ResearchError("Reviewed downloads require HTTPS.")
    target = directory / spec["name"]
    expected = spec.get("bytes")
    ceiling = min(byte_limit, spec.get("max_bytes", byte_limit))
    if expected is not None and expected > ceiling:
        raise ResearchError(f"{spec['name']}: {expected} bytes exceeds explicit transfer limit {ceiling}.")
    if target.exists():
        if target.stat().st_size > ceiling:
            raise ResearchError("Cached file exceeds explicit size guard.")
        return {**validate_file(target, spec), "name": spec["name"], "url": spec["url"], "cached": True}
    if shutil.disk_usage(directory).free < (expected or ceiling) + 128 * 1024 * 1024:
        raise ResearchError("Insufficient disk space for the guarded transfer and safety reserve.")
    partial = target.with_suffix(target.suffix + ".partial")
    if partial.exists():
        raise ResearchError(f"Unfinished transfer exists: {partial.name}. Inspect/remove that exact local file before retrying.")
    request = urllib.request.Request(spec["url"], headers={"User-Agent": "AthleteOS-research-data/1"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            length = response.headers.get("Content-Length")
            try:
                length = int(length) if length is not None else None
            except ValueError:
                raise ResearchError("Invalid remote Content-Length.") from None
            if length is not None and length > ceiling:
                raise ResearchError("Remote file exceeds the explicit transfer limit.")
            if length is not None and expected is not None and length != expected:
                raise ResearchError("Remote byte count changed; review official metadata before downloading.")
            total = 0
            with partial.open("xb") as stream:
                while True:
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > ceiling:
                        raise ResearchError("Transfer exceeded byte limit.")
                    if time.monotonic() - started > 900:
                        raise ResearchError("Transfer exceeded 15-minute time budget.")
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
        result = validate_file(partial, spec)
        if not result["bytes"]:
            raise ResearchError("Empty download.")
        if target.suffix == ".zip":
            with partial.open("rb") as stream:
                if stream.read(4) != b"PK\x03\x04":
                    raise ResearchError("Expected ZIP archive, not HTML or an access/login response.")
        partial.rename(target)
    except Exception:
        if partial.exists():
            partial.unlink()
        raise
    return {**result, "name": spec["name"], "url": spec["url"], "cached": False,
            "downloaded_at": datetime.now(timezone.utc).isoformat()}


def acquire(source_id, root=DATA_ROOT, allow_large=False):
    source = sources().get(source_id)
    if source_id not in {"runners", "pamap2"}:
        raise ResearchError("Only reviewed open runners/PAMAP2 acquisition is automated. FitRec needs an academic-use decision; Garmin is not a public dataset.")
    if source_id == "pamap2" and not allow_large:
        raise ResearchError("PAMAP2 is approximately 656.3 MB. Review disk/access terms and explicitly pass --allow-large.")
    directory = local_root(Path(root) / "raw" / source_id)
    old_files = {}
    if (directory / "acquisition.json").exists():
        old = json.loads((directory / "acquisition.json").read_text(encoding="utf-8"))
        old_files = {f["name"]: f for f in old["files"]}
    result = {"source": source_id, "license": source["license"], "citation": source["citation"],
              "landing_url": source["landing_url"], "version": source.get("version"),
              "scope": "Complete selected official files; no arbitrary row truncation.",
              "files": [download(spec, directory, 750000000 if allow_large else 64 * 1024 * 1024)
                        for spec in source["files"]]}
    for item in result["files"]:
        old_item = old_files.get(item["name"], {})
        if item["cached"] and old_item.get("sha256") == item["sha256"] and old_item.get("downloaded_at"):
            item["downloaded_at"] = old_item["downloaded_at"]
    (directory / "acquisition.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
