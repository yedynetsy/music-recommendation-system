"""FastAPI routes during the incremental Django migration."""

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import require_admin
from .database import get_session
from .models import AlbumRow, ArtistRow
from .schemas import ArtistPatch, ArtistResponse, ArtistWrite
from .users import router as user_router


app = FastAPI(title="Music Recommendation API")
app.include_router(user_router)


@app.exception_handler(RequestValidationError)
async def input_validation_error(request: Request, error: RequestValidationError):
    is_migrated_route = request.url.path.startswith(("/api/artists/", "/api/user/"))
    if request.method not in {"POST", "PUT", "PATCH"} or not is_migrated_route:
        return await request_validation_exception_handler(request, error)
    details: dict[str, list[str]] = {}
    for issue in error.errors():
        field = str(issue["loc"][-1]) if len(issue["loc"]) > 1 else "non_field_errors"
        details.setdefault(field, []).append(issue["msg"])
    return JSONResponse(status_code=400, content=details)


def find_artist(session: Session, artist_id: int) -> ArtistRow:
    artist = session.get(ArtistRow, artist_id)
    if artist is None:
        raise HTTPException(404, detail="Not found.")
    return artist


@app.get("/api/artists/", response_model=list[ArtistResponse])
def list_artists(session: Session = Depends(get_session)) -> list[ArtistRow]:
    return list(session.scalars(select(ArtistRow).order_by(ArtistRow.name, ArtistRow.id)))


@app.post("/api/artists/", response_model=ArtistResponse, status_code=201,
          dependencies=[Depends(require_admin)])
def create_artist(payload: ArtistWrite, session: Session = Depends(get_session)) -> ArtistRow:
    now = datetime.now(timezone.utc)
    artist = ArtistRow(name=payload.name, bio=payload.bio if payload.bio is not None else "",
                       created_at=now, updated_at=now)
    session.add(artist)
    session.commit()
    session.refresh(artist)
    return artist


@app.get("/api/artists/{artist_id}/", response_model=ArtistResponse)
def get_artist(artist_id: int, session: Session = Depends(get_session)) -> ArtistRow:
    return find_artist(session, artist_id)


@app.put("/api/artists/{artist_id}/", response_model=ArtistResponse,
         dependencies=[Depends(require_admin)])
def replace_artist(artist_id: int, payload: ArtistWrite,
                   session: Session = Depends(get_session)) -> ArtistRow:
    artist = find_artist(session, artist_id)
    artist.name = payload.name
    if "bio" in payload.model_fields_set:
        artist.bio = payload.bio
    artist.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(artist)
    return artist


@app.patch("/api/artists/{artist_id}/", response_model=ArtistResponse,
           dependencies=[Depends(require_admin)])
def update_artist(artist_id: int, payload: ArtistPatch,
                  session: Session = Depends(get_session)) -> ArtistRow:
    artist = find_artist(session, artist_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(artist, field, value)
    if payload.model_fields_set:
        artist.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(artist)
    return artist


@app.delete("/api/artists/{artist_id}/", status_code=204,
            dependencies=[Depends(require_admin)])
def delete_artist(artist_id: int, session: Session = Depends(get_session)) -> Response:
    artist = find_artist(session, artist_id)
    has_albums = session.scalar(select(AlbumRow.id).where(AlbumRow.artist_id == artist_id).limit(1))
    if has_albums is not None:
        raise HTTPException(409, detail="Artist has albums.")
    session.delete(artist)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(409, detail="Artist has related records.") from error
    return Response(status_code=204)
