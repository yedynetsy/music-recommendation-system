"""Build recommendation responses and record exposures in one transaction."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import ExposureRow, ListenRow, TrackRow
from backend.schemas import RecommendationResponse, TrackResponse
from backend.services.onboarding import onboarding_seeds
from recommendations.inference import ServingModel


class RecommendationCatalogMismatch(Exception):
    """A model-ranked track is missing from the application catalog."""


class SimilarTrackUnavailable(Exception):
    def __init__(self, detail: str):
        self.detail = detail


def logged_response(session: Session, user_id: int, model: ServingModel,
                    source: str, track_ids: list[str]) -> RecommendationResponse:
    tracks = {track.mbid: track for track in session.scalars(
        select(TrackRow).where(TrackRow.mbid.in_(track_ids))
    )}
    if len(tracks) != len(track_ids):
        raise RecommendationCatalogMismatch
    now = datetime.now(timezone.utc)
    session.add_all([
        ExposureRow(user_id=user_id, track_mbid=track_id, rank=rank,
                    source=source, model_version=model.model_version, created_at=now)
        for rank, track_id in enumerate(track_ids, 1)
    ])
    session.commit()
    return RecommendationResponse(source=source, model_version=model.model_version,
                                  items=[TrackResponse.model_validate(tracks[track_id])
                                         for track_id in track_ids])


def recommend_for_user(session: Session, user_id: int, model: ServingModel,
                       limit: int) -> RecommendationResponse:
    listens = dict(session.execute(
        select(ListenRow.track_mbid, func.count(ListenRow.id))
        .where(ListenRow.user_id == user_id).group_by(ListenRow.track_mbid)
    ).all())
    known_listens = any(count > 0 and mbid in model.track_index
                        for mbid, count in listens.items())
    seeds = {} if known_listens else onboarding_seeds(session, user_id, model)
    source, track_ids = model.rank(listens if known_listens else seeds, limit)
    if seeds and source == "als":
        source = "onboarding"
    return logged_response(session, user_id, model, source, track_ids)


def recommend_similar(session: Session, user_id: int, model: ServingModel,
                      seed_id: str, limit: int) -> RecommendationResponse:
    if session.get(TrackRow, seed_id) is None:
        raise SimilarTrackUnavailable("Track not found.")
    if seed_id not in model.track_index:
        raise SimilarTrackUnavailable("Track is absent from the recommendation model.")
    return logged_response(session, user_id, model, "similar",
                           model.similar_tracks(seed_id, limit))
