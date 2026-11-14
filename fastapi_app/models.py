"""Existing Django table columns needed by the migrated API routes."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


primary_id = BigInteger().with_variant(Integer, "sqlite")


class ArtistRow(Base):
    __tablename__ = "artists_artist"

    id: Mapped[int] = mapped_column(primary_id, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    bio: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserRow(Base):
    __tablename__ = "users_user"

    id: Mapped[int] = mapped_column(primary_id, primary_key=True)
    password: Mapped[str] = mapped_column(String(128), default="")
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    username: Mapped[str] = mapped_column(String(150), unique=True)
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    date_joined: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TokenRow(Base):
    __tablename__ = "authtoken_token"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AlbumRow(Base):
    __tablename__ = "albums_album"

    id: Mapped[int] = mapped_column(primary_id, primary_key=True)
    artist_id: Mapped[int] = mapped_column(BigInteger)
