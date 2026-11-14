"""Contract checks for albums on the existing Django tables."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

from fastapi_app.models import AlbumRow
from fastapi_app.test_artists import ADMIN_HEADERS, USER_HEADERS, client, test_engine


@pytest.fixture
def album(test_engine):
    timestamp = datetime(2009, 1, 1, tzinfo=timezone.utc)
    with Session(test_engine) as session:
        session.add(AlbumRow(
            id=1, name="Nevermind", description="Second studio album",
            release_date=date(1991, 9, 24), artist_id=1,
            created_at=timestamp, updated_at=timestamp,
        ))
        session.commit()


def test_album_detail_matches_django_response(client, album):
    response = client.get("/api/albums/1/")
    assert response.status_code == 200
    assert response.json() == {
        "id": 1, "name": "Nevermind", "description": "Second studio album",
        "release_date": "1991-09-24", "artist": 1,
        "artist_detail": {
            "id": 1, "name": "Nirvana", "bio": "Rock band",
            "created_at": "2009-01-01T00:00:00Z",
            "updated_at": "2009-01-01T00:00:00Z",
        },
        "created_at": "2009-01-01T00:00:00Z",
        "updated_at": "2009-01-01T00:00:00Z",
    }


def test_album_list_is_public_and_ordered(client, album, test_engine):
    with Session(test_engine) as session:
        session.add(AlbumRow(
            name="Aaa Album", artist_id=2,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        ))
        session.commit()
    response = client.get("/api/albums/")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Aaa Album", "Nevermind"]
    assert response.json()[0]["artist_detail"]["name"] == "Radiohead"


def test_admin_can_create_album_with_optional_fields(client):
    response = client.post("/api/albums/", json={"name": "  In Utero  ", "artist": 1},
                           headers=ADMIN_HEADERS)
    assert response.status_code == 201
    assert response.json()["name"] == "In Utero"
    assert response.json()["description"] == ""
    assert response.json()["release_date"] is None
    assert response.json()["artist_detail"]["id"] == 1
    assert client.get(f"/api/albums/{response.json()['id']}/").status_code == 200


@pytest.mark.parametrize(
    ("headers", "status"),
    [({}, 401), (USER_HEADERS, 403), ({"Authorization": "Token invalid"}, 401),
     ({"Authorization": f"Token {'i' * 40}"}, 401)],
)
def test_album_writes_require_active_admin(client, album, headers, status):
    assert client.post("/api/albums/", json={"name": "New", "artist": 1},
                       headers=headers).status_code == status
    assert client.patch("/api/albums/1/", json={"name": "New"},
                        headers=headers).status_code == status
    assert client.delete("/api/albums/1/", headers=headers).status_code == status
    assert client.get("/api/albums/1/").json()["name"] == "Nevermind"


def test_authentication_precedes_album_body_validation(client):
    assert client.post("/api/albums/", json={}).status_code == 401


@pytest.mark.parametrize("payload,field", [
    ({"artist": 1}, "name"),
    ({"name": "Album"}, "artist"),
    ({"name": "Album", "artist": 999}, "artist"),
    ({"name": "  ", "artist": 1}, "name"),
    ({"name": "Album", "artist": 1, "release_date": "invalid"}, "release_date"),
])
def test_invalid_album_returns_400(client, payload, field):
    response = client.post("/api/albums/", json=payload, headers=ADMIN_HEADERS)
    assert response.status_code == 400
    assert field in response.json()


def test_put_updates_required_fields_and_preserves_omitted_optional_fields(client, album):
    response = client.put("/api/albums/1/", json={"name": "New title", "artist": 2},
                          headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "New title"
    assert response.json()["artist"] == 2
    assert response.json()["artist_detail"]["name"] == "Radiohead"
    assert response.json()["description"] == "Second studio album"
    assert response.json()["release_date"] == "1991-09-24"
    assert response.json()["updated_at"] != "2009-01-01T00:00:00Z"


def test_patch_changes_only_supplied_fields_and_can_clear_date(client, album):
    response = client.patch("/api/albums/1/", json={"release_date": None},
                            headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert response.json()["release_date"] is None
    assert response.json()["name"] == "Nevermind"
    assert client.patch("/api/albums/1/", json={"artist": 2},
                        headers=ADMIN_HEADERS).json()["artist_detail"]["name"] == "Radiohead"


def test_invalid_updates_leave_album_unchanged(client, album):
    assert client.put("/api/albums/1/", json={"name": "New"},
                      headers=ADMIN_HEADERS).status_code == 400
    assert client.patch("/api/albums/1/", json={"artist": 999},
                        headers=ADMIN_HEADERS).status_code == 400
    assert client.patch("/api/albums/1/", json={"name": None},
                        headers=ADMIN_HEADERS).status_code == 400
    assert client.get("/api/albums/1/").json()["name"] == "Nevermind"


def test_admin_can_delete_album_and_missing_album_is_404(client, album):
    assert client.delete("/api/albums/1/", headers=ADMIN_HEADERS).status_code == 204
    assert client.get("/api/albums/1/").status_code == 404
    assert client.delete("/api/albums/1/", headers=ADMIN_HEADERS).status_code == 404
