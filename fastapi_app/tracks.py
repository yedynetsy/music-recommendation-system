"""Track catalog, app listens, and logged recommendation serving."""

import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from recommendations.serving import ServingModel

from .auth import authenticated_user
from .database import get_session
from .models import ArtistPreferenceRow, ExposureRow, ListenRow, TrackRow, UserRow
from .schemas import (ArtistChoice, ArtistChoiceResponse, CatalogArtistResponse,
                      ListenResponse, RecommendationResponse, TrackResponse)


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


@router.get("/api/tracks/{track_mbid}/similar/", response_model=RecommendationResponse)
def similar_tracks(track_mbid: UUID, limit: int = Query(10, ge=1, le=50),
                   user: UserRow = Depends(authenticated_user),
                   model: ServingModel = Depends(get_serving_model),
                   session: Session = Depends(get_session)) -> RecommendationResponse:
    seed_id = str(track_mbid)
    if session.get(TrackRow, seed_id) is None:
        raise HTTPException(404, detail="Track not found.")
    if seed_id not in model.track_index:
        raise HTTPException(404, detail="Track is absent from the recommendation model.")
    track_ids = model.similar_tracks(seed_id, limit)
    tracks = {track.mbid: track for track in session.scalars(
        select(TrackRow).where(TrackRow.mbid.in_(track_ids))
    )}
    if len(tracks) != len(track_ids):
        raise HTTPException(503, detail="Recommendation model and track catalog differ.")
    now = datetime.now(timezone.utc)
    session.add_all([
        ExposureRow(user_id=user.id, track_mbid=track_id, rank=rank,
                    source="similar", model_version=model.model_version, created_at=now)
        for rank, track_id in enumerate(track_ids, 1)
    ])
    session.commit()
    return RecommendationResponse(source="similar", model_version=model.model_version,
                                  items=[TrackResponse.model_validate(tracks[track_id])
                                         for track_id in track_ids])


@router.get("/api/onboarding/artists/search/", response_model=list[CatalogArtistResponse])
def search_catalog_artists(query: str = Query(min_length=1),
                           limit: int = Query(20, ge=1, le=50),
                           session: Session = Depends(get_session)) -> list[CatalogArtistResponse]:
    rows = session.execute(
        select(TrackRow.artist_mbid, func.min(TrackRow.artist_name))
        .where(TrackRow.artist_mbid.is_not(None), TrackRow.artist_name.is_not(None),
               TrackRow.artist_name.ilike(f"%{query}%"))
        .group_by(TrackRow.artist_mbid)
        .order_by(func.min(TrackRow.artist_name), TrackRow.artist_mbid).limit(limit)
    )
    return [CatalogArtistResponse(mbid=mbid, name=name) for mbid, name in rows]


@router.get("/api/onboarding/artists/", response_model=ArtistChoiceResponse)
def get_artist_choices(user: UserRow = Depends(authenticated_user),
                       session: Session = Depends(get_session)) -> ArtistChoiceResponse:
    ids = session.scalars(select(ArtistPreferenceRow.artist_mbid)
                          .where(ArtistPreferenceRow.user_id == user.id)
                          .order_by(ArtistPreferenceRow.artist_mbid)).all()
    return ArtistChoiceResponse(artist_mbids=list(ids))


@router.put("/api/onboarding/artists/", response_model=ArtistChoiceResponse)
def set_artist_choices(payload: ArtistChoice, user: UserRow = Depends(authenticated_user),
                       session: Session = Depends(get_session)) -> ArtistChoiceResponse:
    ids = sorted(str(mbid) for mbid in payload.artist_mbids)
    if ids:
        found = set(session.scalars(select(TrackRow.artist_mbid)
                                    .where(TrackRow.artist_mbid.in_(ids)).distinct()))
        if found != set(ids):
            raise HTTPException(422, detail="Artist MBID is absent from the track catalog.")
    session.execute(delete(ArtistPreferenceRow).where(ArtistPreferenceRow.user_id == user.id))
    session.add_all(ArtistPreferenceRow(user_id=user.id, artist_mbid=mbid) for mbid in ids)
    session.commit()
    return ArtistChoiceResponse(artist_mbids=ids)


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


@router.get("/api/recommendations/", response_model=RecommendationResponse)
def recommend_tracks(limit: int = Query(10, ge=1, le=50),
                     user: UserRow = Depends(authenticated_user),
                     model: ServingModel = Depends(get_serving_model),
                     session: Session = Depends(get_session)) -> RecommendationResponse:
    listens = dict(session.execute(
        select(ListenRow.track_mbid, func.count(ListenRow.id))
        .where(ListenRow.user_id == user.id).group_by(ListenRow.track_mbid)
    ).all())
    known_listens = any(count > 0 and mbid in model.track_index
                        for mbid, count in listens.items())
    seeds = {} if known_listens else onboarding_seeds(session, user.id, model)
    source, track_ids = model.rank(listens if known_listens else seeds, limit)
    if seeds and source == "als":
        source = "onboarding"
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
