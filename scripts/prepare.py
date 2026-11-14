"""Run with: python -m scripts.prepare SOURCE.tsv OUTPUT.tsv"""

import argparse
import json
from pathlib import Path

from recommendations.lastfm import prepare_sample


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a deterministic Last.fm 1K user sample")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--bucket-count", type=int, default=100)
    parser.add_argument("--bucket", type=int, default=0)
    args = parser.parse_args()
    counts = prepare_sample(args.source, args.destination, args.bucket_count, args.bucket)
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
