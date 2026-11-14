"""Contract checks for the first FastAPI catalog routes."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fastapi_app.main import ArtistRow, Base, app, get_session


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'artists.sqlite3'}")
    Base.metadata.create_all(engine)
    timestamp = datetime(2009, 1, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add_all([
            ArtistRow(id=2, name="Radiohead", bio="", created_at=timestamp, updated_at=timestamp),
            ArtistRow(id=1, name="Nirvana", bio="Rock band", created_at=timestamp, updated_at=timestamp),
        ])
        session.commit()

    def test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_list_artists_is_public_and_ordered(client):
    response = client.get("/api/artists/")
    assert response.status_code == 200
    assert [artist["name"] for artist in response.json()] == ["Nirvana", "Radiohead"]


def test_artist_detail_has_existing_api_fields(client):
    response = client.get("/api/artists/1/")
    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "name": "Nirvana",
        "bio": "Rock band",
        "created_at": "2009-01-01T00:00:00Z",
        "updated_at": "2009-01-01T00:00:00Z",
    }


def test_unknown_artist_returns_404(client):
    response = client.get("/api/artists/999/")
    assert response.status_code == 404
