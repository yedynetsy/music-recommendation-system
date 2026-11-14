"""Alembic configuration for the standalone catalog schema."""

from alembic import context
from sqlalchemy import create_engine

from fastapi_app.database import Base, database_url
from fastapi_app import models  # noqa: F401 - register mapped tables


target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations_online()
