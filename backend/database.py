"""Database connection shared by the migrated API routes."""

import os
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


database_url = os.environ.get(
    "MUSIC_DATABASE_URL",
    f"sqlite:///{Path(__file__).resolve().parent.parent / 'db.sqlite3'}",
)
engine = create_engine(database_url)
SessionFactory = sessionmaker(bind=engine)


def get_session() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session
