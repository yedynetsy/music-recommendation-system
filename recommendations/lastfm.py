"""Streaming reader and deterministic development sample for Last.fm 1K."""

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Listen:
    user_id: str
    timestamp: datetime
    track_id: str
    artist_id: str
    artist_name: str
    track_name: str


def read_listens(path: Path) -> Iterator[Listen]:
    """Read the original six-column TSV without loading it into memory."""
    with path.open(encoding="utf-8", newline="") as source:
        for line_number, row in enumerate(csv.reader(source, delimiter="\t"), 1):
            if len(row) != 6:
                raise ValueError(f"line {line_number}: expected six TSV columns")
            user_id, raw_time, artist_id, artist_name, track_id, track_name = row
            try:
                timestamp = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"line {line_number}: invalid timestamp") from exc
            if not user_id or timestamp.tzinfo is None:
                raise ValueError(f"line {line_number}: missing user or timezone")
            yield Listen(
                user_id=user_id,
                timestamp=timestamp.astimezone(timezone.utc),
                track_id=track_id,
                artist_id=artist_id,
                artist_name=artist_name,
                track_name=track_name,
            )


def user_bucket(user_id: str, bucket_count: int) -> int:
    if bucket_count < 1:
        raise ValueError("bucket_count must be positive")
    digest = hashlib.sha256(user_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % bucket_count


def prepare_sample(source: Path, destination: Path, bucket_count: int, bucket: int) -> dict[str, int]:
    """Select complete user histories by stable hash and retain MBID tracks."""
    if not 0 <= bucket < bucket_count:
        raise ValueError("bucket must be in [0, bucket_count)")
    if source.resolve() == destination.resolve():
        raise ValueError("source and destination must differ")
    counts = {"source_events": 0, "selected_events": 0, "missing_track_mbid": 0, "written_events": 0}
    with destination.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        for event in read_listens(source):
            counts["source_events"] += 1
            if user_bucket(event.user_id, bucket_count) != bucket:
                continue
            counts["selected_events"] += 1
            if not event.track_id:
                counts["missing_track_mbid"] += 1
                continue
            writer.writerow((event.user_id, event.timestamp.isoformat().replace("+00:00", "Z"),
                             event.artist_id, event.artist_name, event.track_id, event.track_name))
            counts["written_events"] += 1
    return counts
