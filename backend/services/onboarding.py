"""Translate chosen artist MBIDs into a bounded model seed profile."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.models import ArtistPreferenceRow, TrackRow
from recommendations.inference import ServingModel

def onboarding_seeds(session: Session, user_id: int, model: ServingModel) -> dict[str, int]:
    """Choose up to three known, popular tracks per selected artist."""
    artist_ids = session.scalars(select(ArtistPreferenceRow.artist_mbid)
                                 .where(ArtistPreferenceRow.user_id == user_id)).all()
    if not artist_ids:
        return {}
    best: dict[str, list[tuple[int, str]]] = {mbid: [] for mbid in artist_ids}
    for artist_mbid, track_mbid in session.execute(
        select(TrackRow.artist_mbid, TrackRow.mbid)
        .where(TrackRow.artist_mbid.in_(artist_ids)).execution_options(yield_per=1000)
    ):
        index = model.track_index.get(track_mbid)
        if index is None:
            continue
        tracks = best[artist_mbid]
        tracks.append((int(model.popularity[index]), track_mbid))
        tracks.sort(key=lambda item: (-item[0], item[1]))
        del tracks[3:]
    return {track_mbid: 1 for tracks in best.values() for _, track_mbid in tracks}
