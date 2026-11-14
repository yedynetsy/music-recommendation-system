"""Request validation and response shapes for the API routes."""

from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


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


class ArtistWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    bio: str | None = None

    @model_validator(mode="after")
    def reject_null_bio(self):
        if "bio" in self.model_fields_set and self.bio is None:
            raise ValueError("bio cannot be null")
        return self


class ArtistPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    bio: str | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AlbumResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    release_date: date | None
    artist: int = Field(validation_alias="artist_id")
    artist_detail: ArtistResponse = Field(validation_alias="artist")
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class AlbumWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    release_date: date | None = None
    artist: int

    @model_validator(mode="after")
    def reject_null_description(self):
        if self.description is None:
            raise ValueError("description cannot be null")
        return self


class AlbumPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    release_date: date | None = None
    artist: int | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in self.model_fields_set & {"name", "description", "artist"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class RegisterInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1)
    password_confirm: str = Field(min_length=1)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = unicodedata.normalize("NFKC", value)
        if len(value) > 150 or re.fullmatch(r"[\w.@+-]+", value) is None:
            raise ValueError("Enter a valid username.")
        return value

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match.")
        return self


class LoginInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    token: str
    username: str


class TrackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mbid: str
    name: str | None
    artist_mbid: str | None
    artist_name: str | None


class ListenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track_mbid: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class RecommendationResponse(BaseModel):
    source: Literal["als", "popularity", "onboarding"]
    model_version: str
    items: list[TrackResponse]


class ArtistChoice(BaseModel):
    artist_mbids: list[UUID] = Field(max_length=10)

    @field_validator("artist_mbids")
    @classmethod
    def unique_artists(cls, values: list[UUID]) -> list[UUID]:
        if len(values) != len(set(values)):
            raise ValueError("artist MBIDs must be unique")
        return values


class ArtistChoiceResponse(BaseModel):
    artist_mbids: list[str]


class CatalogArtistResponse(BaseModel):
    mbid: str
    name: str
