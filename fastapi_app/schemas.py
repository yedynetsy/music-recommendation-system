"""Artist request validation and response shape."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


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
