"""Import pre-cutoff Last.fm track metadata without matching artist names."""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from recommendations.lastfm import read_listens

from .models import TrackRow


def import_tracks(sample: Path, cutoff: datetime, session: Session,
                  batch_size: int = 500) -> dict[str, int]:
    if cutoff.tzinfo is None or batch_size < 1:
        raise ValueError("cutoff needs a timezone and batch size must be positive")
    seen: set[str] = set()
    batch: dict[str, TrackRow] = {}
    counts = {"training_events": 0, "distinct_tracks": 0, "inserted_tracks": 0}

    def flush() -> None:
        if not batch:
            return
        existing = set(session.scalars(
            select(TrackRow.mbid).where(TrackRow.mbid.in_(batch))
        ))
        new_rows = [row for mbid, row in batch.items() if mbid not in existing]
        session.add_all(new_rows)
        session.commit()
        counts["inserted_tracks"] += len(new_rows)
        batch.clear()

    for event in read_listens(sample):
        if event.timestamp >= cutoff or not event.track_id:
            continue
        counts["training_events"] += 1
        try:
            canonical_mbid = str(UUID(event.track_id))
        except ValueError as error:
            raise ValueError(f"invalid track MBID: {event.track_id}") from error
        if canonical_mbid != event.track_id:
            raise ValueError(f"noncanonical track MBID: {event.track_id}")
        if canonical_mbid in seen:
            continue
        seen.add(canonical_mbid)
        batch[canonical_mbid] = TrackRow(
            mbid=canonical_mbid, name=event.track_name or None,
            artist_mbid=event.artist_id or None,
            artist_name=event.artist_name or None,
        )
        if len(batch) >= batch_size:
            flush()
    flush()
    counts["distinct_tracks"] = len(seen)
    return counts


if __name__ == "__main__":
    from scripts.import_tracks import main

    main()
