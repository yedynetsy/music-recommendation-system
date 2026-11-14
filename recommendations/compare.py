"""Compare the fixed popularity and ALS models on one temporal holdout."""

import argparse
import json
import resource
import sys
from dataclasses import asdict
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from .als import ALSConfig, fit_als
from .evaluation import evaluate_popularity_data, evaluate_rankings, split_events
from .lastfm import read_listens


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare popularity and implicit ALS")
    parser.add_argument("sample", type=Path)
    parser.add_argument("--cutoff", required=True, help="UTC timestamp, e.g. 2009-01-01T00:00:00Z")
    parser.add_argument("-k", type=int, default=10)
    parser.add_argument("--factors", type=int, default=32)
    parser.add_argument("--regularization", type=float, default=0.05)
    parser.add_argument("--alpha", type=float, default=10.0)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        cutoff = datetime.fromisoformat(args.cutoff.replace("Z", "+00:00"))
        config = ALSConfig(args.factors, args.regularization, args.alpha,
                           args.iterations, args.threads, args.seed)
    except ValueError as error:
        parser.error(str(error))
    if cutoff.tzinfo is None or args.k < 1:
        parser.error("cutoff must include a timezone and k must be positive")

    data = split_events(read_listens(args.sample), cutoff)
    popularity = evaluate_popularity_data(data, args.k)
    started = perf_counter()
    model = fit_als(data, config)
    training_seconds = perf_counter() - started
    als = evaluate_rankings(data, args.k, model.recommend)
    if (popularity.users, popularity.cold_users, popularity.users_without_targets) != (
        als.users, als.cold_users, als.users_without_targets
    ):
        raise RuntimeError("models were evaluated on different user groups")
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mb = peak_rss / (1024 * 1024 if sys.platform == "darwin" else 1024)
    print(json.dumps({
        "cutoff": cutoff.isoformat(), "k": args.k,
        "training_users": len(data.history), "training_tracks": len(data.popularity),
        "training_pairs": len(data.train_counts), "config": asdict(config),
        "implicit_version": version("implicit"),
        "popularity": asdict(popularity), "als": asdict(als),
        "als_training_seconds": round(training_seconds, 3),
        "peak_rss_mb": round(peak_rss_mb, 1),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
