"""Database connection shared by the migrated API routes."""

import os
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def configured_database_url() -> str | URL:
    if url := os.environ.get("MUSIC_DATABASE_URL"):
        return url
    if host := os.environ.get("MUSIC_POSTGRES_HOST"):
        return URL.create(
            "postgresql+psycopg", host=host,
            port=int(os.environ.get("MUSIC_POSTGRES_PORT", "5432")),
            username=os.environ.get("MUSIC_POSTGRES_USER", "music"),
            password=os.environ["MUSIC_POSTGRES_PASSWORD"],
            database=os.environ.get("MUSIC_POSTGRES_DB", "music"),
        )
    return f"sqlite:///{Path(__file__).resolve().parent.parent / 'db.sqlite3'}"


database_url = configured_database_url()
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)


def get_session() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session
