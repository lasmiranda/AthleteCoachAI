"""Run `python -m research_data --help`; standard-library-only research utilities."""

import argparse
import csv
import json
import urllib.error
import zipfile

from research_data.acquire import DATA_ROOT, ResearchError, acquire, sources
from research_data.prepare import prepare_runners
from research_data.pamap2 import prepare_pamap2
from research_data.verify import verify_prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sources", help="Print reviewed source manifest; does not download records.")
    get = commands.add_parser("acquire", help="Acquire reviewed open files into ignored local storage.")
    get.add_argument("source", choices=("runners", "pamap2"))
    get.add_argument("--root", default=str(DATA_ROOT))
    get.add_argument("--allow-large", action="store_true", help="Explicitly allow PAMAP2's approximately 656.3 MB transfer.")
    prepare = commands.add_parser("prepare-runners", help="Prepare both subject-disjoint and purged temporal benchmarks.")
    prepare.add_argument("--approach", choices=("day", "week"), default="day")
    prepare.add_argument("--root", default=str(DATA_ROOT))
    prepare.add_argument("--output", help="New directory inside .research-data; existing runs are never overwritten.")
    pamap = commands.add_parser("prepare-pamap2", help="Prepare nonoverlapping Protocol-only sensor windows; requires the full authorized ZIP.")
    pamap.add_argument("--root", default=str(DATA_ROOT))
    pamap.add_argument("--output", help="New directory inside .research-data.")
    verify = commands.add_parser("verify", help="Recompute train transforms and verify hashes, table alignment and split leakage.")
    verify.add_argument("directory", help="Prepared run directory inside .research-data.")
    args = parser.parse_args()
    try:
        if args.command == "sources":
            result = sources()
        elif args.command == "acquire":
            result = acquire(args.source, args.root, args.allow_large)
        elif args.command == "prepare-runners":
            result = prepare_runners(args.approach, args.root, args.output)
        elif args.command == "prepare-pamap2":
            result = prepare_pamap2(args.root, args.output)
        else:
            result = verify_prepared(args.directory)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ResearchError, OSError, urllib.error.URLError, csv.Error, zipfile.BadZipFile, UnicodeError, json.JSONDecodeError) as error:
        parser.exit(1, f"Research data error: {error}\n")


if __name__ == "__main__":
    main()
