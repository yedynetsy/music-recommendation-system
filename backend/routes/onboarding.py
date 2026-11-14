"""Onboarding API routes."""


from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.security import authenticated_user
from backend.database import get_session
from backend.models import ArtistPreferenceRow, TrackRow, UserRow
from backend.schemas import ArtistChoice, ArtistChoiceResponse, CatalogArtistResponse

router = APIRouter(tags=["onboarding"])


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
