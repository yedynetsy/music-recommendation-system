"""Run with: python -m recommendations.benchmark SAMPLE.tsv --cutoff 2009-01-01T00:00:00Z"""

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .evaluation import evaluate_popularity
from .lastfm import read_listens


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the popularity baseline")
    parser.add_argument("sample", type=Path)
    parser.add_argument("--cutoff", required=True, help="UTC timestamp, e.g. 2009-01-01T00:00:00Z")
    parser.add_argument("-k", type=int, default=10)
    args = parser.parse_args()
    try:
        cutoff = datetime.fromisoformat(args.cutoff.replace("Z", "+00:00"))
    except ValueError as exc:
        parser.error(f"invalid cutoff: {exc}")
    if cutoff.tzinfo is None:
        parser.error("cutoff must include a timezone")
    result = evaluate_popularity(read_listens(args.sample), cutoff, args.k)
    print(json.dumps({"cutoff": cutoff.isoformat(), "k": args.k, **asdict(result)}, sort_keys=True))


if __name__ == "__main__":
    main()
