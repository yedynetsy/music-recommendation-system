"""Fixtures shared by backend contract tests."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.database import Base, get_session
from backend.main import app
from backend.models import ArtistRow, TokenRow, UserRow


@pytest.fixture
def test_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'artists.sqlite3'}")
    Base.metadata.create_all(engine)
    timestamp = datetime(2009, 1, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add_all([
            ArtistRow(id=2, name="Radiohead", bio="", created_at=timestamp, updated_at=timestamp),
            ArtistRow(id=1, name="Nirvana", bio="Rock band", created_at=timestamp, updated_at=timestamp),
            UserRow(id=1, username="admin", is_staff=True, is_active=True),
            UserRow(id=2, username="regular", is_staff=False, is_active=True),
            UserRow(id=3, username="inactive", is_staff=True, is_active=False),
            TokenRow(key="a" * 40, user_id=1),
            TokenRow(key="u" * 40, user_id=2),
            TokenRow(key="i" * 40, user_id=3),
        ])
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def client(test_engine):
    def test_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
