"""Import a pre-cutoff track catalog from a prepared sample."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from fastapi_app.database import SessionFactory
from fastapi_app.import_tracks import import_tracks


def main() -> None:
    parser = argparse.ArgumentParser(description="Import pre-cutoff tracks into the API catalog")
    parser.add_argument("sample", type=Path)
    parser.add_argument("--cutoff", required=True)
    args = parser.parse_args()
    try:
        cutoff = datetime.fromisoformat(args.cutoff.replace("Z", "+00:00"))
    except ValueError as error:
        parser.error(str(error))
    with SessionFactory() as session:
        counts = import_tracks(args.sample, cutoff, session)
    print(json.dumps({"cutoff": cutoff.isoformat(), **counts}, sort_keys=True))


if __name__ == "__main__":
    main()
