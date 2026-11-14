"""Contract checks for the migrated FastAPI artist routes."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fastapi_app.database import Base, get_session
from fastapi_app.main import app
from fastapi_app.models import AlbumRow, ArtistRow, TokenRow, UserRow


ADMIN_HEADERS = {"Authorization": f"Token {'a' * 40}"}
USER_HEADERS = {"Authorization": f"Token {'u' * 40}"}


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


def test_admin_can_create_artist(client):
    response = client.post("/api/artists/", json={"name": "  Muse  "}, headers=ADMIN_HEADERS)
    assert response.status_code == 201
    assert response.json()["name"] == "Muse"
    assert response.json()["bio"] == ""
    assert client.get(f"/api/artists/{response.json()['id']}/").status_code == 200


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    [({}, 401), (USER_HEADERS, 403), ({"Authorization": "Token invalid"}, 401),
     ({"Authorization": f"Token {'i' * 40}"}, 401)],
)
def test_create_requires_active_admin_token(client, headers, expected_status):
    response = client.post("/api/artists/", json={"name": "Muse"}, headers=headers)
    assert response.status_code == expected_status
    assert [artist["name"] for artist in client.get("/api/artists/").json()] == ["Nirvana", "Radiohead"]


def test_authentication_precedes_body_validation(client):
    assert client.post("/api/artists/", json={}).status_code == 401


def test_put_updates_name_without_erasing_omitted_bio(client):
    response = client.put("/api/artists/1/", json={"name": "New name"}, headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "New name"
    assert response.json()["bio"] == "Rock band"
    assert response.json()["updated_at"] != "2009-01-01T00:00:00Z"


def test_patch_updates_only_supplied_field(client):
    response = client.patch("/api/artists/1/", json={"bio": "New bio"}, headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "Nirvana"
    assert response.json()["bio"] == "New bio"


@pytest.mark.parametrize("payload", [{}, {"name": "   "}, {"name": "Muse", "bio": None}])
def test_invalid_artist_payload_returns_400(client, payload):
    response = client.post("/api/artists/", json=payload, headers=ADMIN_HEADERS)
    assert response.status_code == 400
    if "name" not in payload:
        assert "name" in response.json()


def test_invalid_update_payload_returns_400(client):
    assert client.put("/api/artists/1/", json={}, headers=ADMIN_HEADERS).status_code == 400
    assert client.patch("/api/artists/1/", json={"name": None}, headers=ADMIN_HEADERS).status_code == 400
    assert client.get("/api/artists/1/").json()["name"] == "Nirvana"


def test_update_requires_admin_and_existing_artist(client):
    assert client.put("/api/artists/1/", json={"name": "New"}).status_code == 401
    assert client.patch("/api/artists/1/", json={"bio": "New"}, headers=USER_HEADERS).status_code == 403
    assert client.put("/api/artists/999/", json={"name": "New"}, headers=ADMIN_HEADERS).status_code == 404
    assert client.patch("/api/artists/999/", json={"bio": "New"}, headers=ADMIN_HEADERS).status_code == 404


def test_delete_requires_admin(client):
    assert client.delete("/api/artists/1/").status_code == 401
    assert client.delete("/api/artists/1/", headers=USER_HEADERS).status_code == 403
    assert client.get("/api/artists/1/").status_code == 200


def test_admin_can_delete_artist(client):
    response = client.delete("/api/artists/1/", headers=ADMIN_HEADERS)
    assert response.status_code == 204
    assert client.get("/api/artists/1/").status_code == 404


def test_delete_unknown_artist_returns_404(client):
    assert client.delete("/api/artists/999/", headers=ADMIN_HEADERS).status_code == 404


def test_artist_with_albums_cannot_be_deleted(client, test_engine):
    # The test database is isolated, so this checks the same protection as Django PROTECT.
    with Session(test_engine) as session:
        session.add(AlbumRow(id=1, artist_id=1))
        session.commit()
    response = client.delete("/api/artists/1/", headers=ADMIN_HEADERS)
    assert response.status_code == 409
    assert client.get("/api/artists/1/").status_code == 200
