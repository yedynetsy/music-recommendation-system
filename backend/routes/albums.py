"""Album catalog routes backed by the existing Django tables."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.security import require_admin
from backend.database import get_session
from backend.models import AlbumRow, ArtistRow
from backend.schemas import AlbumPatch, AlbumResponse, AlbumWrite


router = APIRouter(prefix="/api/albums", tags=["albums"])


class UnknownArtistError(Exception):
    """The supplied artist ID is absent from the catalog."""


def find_album(session: Session, album_id: int) -> AlbumRow:
    album = session.scalar(
        select(AlbumRow).options(joinedload(AlbumRow.artist)).where(AlbumRow.id == album_id)
    )
    if album is None:
        raise HTTPException(404, detail="Not found.")
    return album


def checked_artist_id(session: Session, artist_id: int) -> int:
    if session.get(ArtistRow, artist_id) is None:
        raise UnknownArtistError
    return artist_id


@router.get("/", response_model=list[AlbumResponse])
def list_albums(session: Session = Depends(get_session)) -> list[AlbumRow]:
    return list(session.scalars(
        select(AlbumRow).options(joinedload(AlbumRow.artist))
        .order_by(AlbumRow.name, AlbumRow.id)
    ))


@router.post("/", response_model=AlbumResponse, status_code=201,
             dependencies=[Depends(require_admin)])
def create_album(payload: AlbumWrite, session: Session = Depends(get_session)) -> AlbumRow:
    now = datetime.now(timezone.utc)
    album = AlbumRow(
        name=payload.name,
        description=payload.description,
        release_date=payload.release_date,
        artist_id=checked_artist_id(session, payload.artist),
        created_at=now,
        updated_at=now,
    )
    session.add(album)
    session.commit()
    session.refresh(album)
    return album


@router.get("/{album_id}/", response_model=AlbumResponse)
def get_album(album_id: int, session: Session = Depends(get_session)) -> AlbumRow:
    return find_album(session, album_id)


@router.put("/{album_id}/", response_model=AlbumResponse,
            dependencies=[Depends(require_admin)])
def replace_album(album_id: int, payload: AlbumWrite,
                  session: Session = Depends(get_session)) -> AlbumRow:
    album = find_album(session, album_id)
    album.name = payload.name
    album.artist_id = checked_artist_id(session, payload.artist)
    if "description" in payload.model_fields_set:
        album.description = payload.description
    if "release_date" in payload.model_fields_set:
        album.release_date = payload.release_date
    album.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(album)
    return album


@router.patch("/{album_id}/", response_model=AlbumResponse,
              dependencies=[Depends(require_admin)])
def update_album(album_id: int, payload: AlbumPatch,
                 session: Session = Depends(get_session)) -> AlbumRow:
    album = find_album(session, album_id)
    changes = payload.model_dump(exclude_unset=True)
    if "artist" in changes:
        album.artist_id = checked_artist_id(session, changes.pop("artist"))
    for field, value in changes.items():
        setattr(album, field, value)
    if payload.model_fields_set:
        album.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(album)
    return album


@router.delete("/{album_id}/", status_code=204,
               dependencies=[Depends(require_admin)])
def delete_album(album_id: int, session: Session = Depends(get_session)) -> Response:
    session.delete(find_album(session, album_id))
    session.commit()
    return Response(status_code=204)
