"""Listens API routes."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.security import authenticated_user
from backend.database import get_session
from backend.models import ListenRow, TrackRow, UserRow
from backend.schemas import ListenResponse

router = APIRouter(tags=["listens"])


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
