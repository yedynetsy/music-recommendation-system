"""Tracks API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.database import get_session
from backend.models import TrackRow
from backend.schemas import TrackResponse

router = APIRouter(tags=["tracks"])


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
