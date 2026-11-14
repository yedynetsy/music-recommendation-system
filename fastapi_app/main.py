"""Read-only artist catalog backed by the existing Django artist table."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import BigInteger, DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ArtistRow(Base):
    __tablename__ = "artists_artist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    bio: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArtistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    bio: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        # Django stores UTC datetimes without an offset in local SQLite.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


database_url = os.environ.get(
    "MUSIC_DATABASE_URL",
    f"sqlite:///{Path(__file__).resolve().parent.parent / 'db.sqlite3'}",
)
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)


def get_session() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session


app = FastAPI(title="Music Recommendation API")


@app.get("/api/artists/", response_model=list[ArtistResponse])
def list_artists(session: Session = Depends(get_session)) -> list[ArtistRow]:
    return list(session.scalars(select(ArtistRow).order_by(ArtistRow.name, ArtistRow.id)))


@app.get("/api/artists/{artist_id}/", response_model=ArtistResponse)
def get_artist(artist_id: int, session: Session = Depends(get_session)) -> ArtistRow:
    artist = session.get(ArtistRow, artist_id)
    if artist is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return artist
