"""Train and export a reproducible offline model for the API."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from recommendations.als import ALSConfig, fit_als
from recommendations.evaluation import split_events
from recommendations.lastfm import read_listens
from recommendations.serving import save_artifact


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export ALS factors for API inference")
    parser.add_argument("sample", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cutoff", required=True)
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
    if cutoff.tzinfo is None or args.sample.resolve() == args.output.resolve():
        parser.error("cutoff needs a timezone and output must differ from sample")
    data = split_events(read_listens(args.sample), cutoff)
    model = fit_als(data, config)
    version = save_artifact(args.output, model, data, cutoff, config, file_sha256(args.sample))
    print(json.dumps({"model_version": version, "cutoff": cutoff.isoformat(),
                      "tracks": len(model.track_ids), "training_users": len(data.history),
                      "training_pairs": len(data.train_counts),
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
