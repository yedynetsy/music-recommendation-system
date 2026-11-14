"""Track catalog, app listens, and logged recommendation serving."""

import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from recommendations.serving import ServingModel

from .auth import authenticated_user
from .database import get_session
from .models import ExposureRow, ListenRow, TrackRow, UserRow
from .schemas import ListenResponse, RecommendationResponse, TrackResponse


router = APIRouter(tags=["tracks"])
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "als-model.npz"


@lru_cache(maxsize=1)
def load_model(path: str) -> ServingModel:
    return ServingModel.load(Path(path))


def get_serving_model() -> ServingModel:
    path = Path(os.environ.get("MUSIC_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
    try:
        return load_model(str(path.resolve()))
    except (OSError, ValueError, KeyError) as error:
        raise HTTPException(503, detail="Recommendation model is unavailable.") from error


@router.get("/api/tracks/", response_model=list[TrackResponse])
def list_tracks(query: str | None = None, limit: int = Query(20, ge=1, le=100),
                offset: int = Query(0, ge=0),
                session: Session = Depends(get_session)) -> list[TrackRow]:
    statement = select(TrackRow)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(TrackRow.name.ilike(pattern),
                                        TrackRow.artist_name.ilike(pattern)))
    return list(session.scalars(statement.order_by(TrackRow.name, TrackRow.mbid)
                                .offset(offset).limit(limit)))


@router.get("/api/tracks/{track_mbid}/", response_model=TrackResponse)
def get_track(track_mbid: UUID, session: Session = Depends(get_session)) -> TrackRow:
    track = session.get(TrackRow, str(track_mbid))
    if track is None:
        raise HTTPException(404, detail="Track not found.")
    return track


@router.post("/api/tracks/{track_mbid}/listens/", response_model=ListenResponse,
             status_code=201)
def record_listen(track_mbid: UUID, user: UserRow = Depends(authenticated_user),
                  session: Session = Depends(get_session)) -> ListenRow:
    if session.get(TrackRow, str(track_mbid)) is None:
        raise HTTPException(404, detail="Track not found.")
    event = ListenRow(user_id=user.id, track_mbid=str(track_mbid),
                      created_at=datetime.now(timezone.utc))
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("/api/recommendations/", response_model=RecommendationResponse)
def recommend_tracks(limit: int = Query(10, ge=1, le=50),
                     user: UserRow = Depends(authenticated_user),
                     model: ServingModel = Depends(get_serving_model),
                     session: Session = Depends(get_session)) -> RecommendationResponse:
    listens = dict(session.execute(
        select(ListenRow.track_mbid, func.count(ListenRow.id))
        .where(ListenRow.user_id == user.id).group_by(ListenRow.track_mbid)
    ).all())
    source, track_ids = model.rank(listens, limit)
    tracks = {track.mbid: track for track in session.scalars(
        select(TrackRow).where(TrackRow.mbid.in_(track_ids))
    )}
    if len(tracks) != len(track_ids):
        raise HTTPException(503, detail="Recommendation model and track catalog differ.")
    now = datetime.now(timezone.utc)
    session.add_all([
        ExposureRow(user_id=user.id, track_mbid=track_id, rank=rank,
                    source=source, model_version=model.model_version, created_at=now)
        for rank, track_id in enumerate(track_ids, 1)
    ])
    session.commit()
    return RecommendationResponse(source=source, model_version=model.model_version,
                                  items=[TrackResponse.model_validate(tracks[track_id])
                                         for track_id in track_ids])
