"""Registration and token compatibility checks for the migrated user API."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.security import hash_password, verify_password
from backend.database import Base
from backend.models import TokenRow, UserRow


PASSWORD = "testpassword"


def test_existing_pbkdf2_hash_remains_valid_without_django():
    encoded = "pbkdf2_sha256$1000000$fixedsalt$h8Jwb0kmHn1Oj+ycavQ1T4lr1ORMz+2h909uq58pDMk="
    assert verify_password("legacy-password", encoded)
    assert not verify_password("wrong-password", encoded)
    assert not verify_password("legacy-password", "invalid")


@pytest.fixture
def test_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'users.sqlite3'}")
    Base.metadata.create_all(engine)
    encoded = hash_password(PASSWORD)
    with Session(engine) as session:
        session.add_all([
            UserRow(id=1, username="existing", password=encoded),
            UserRow(id=2, username="staff", password=encoded, is_staff=True),
            UserRow(id=3, username="inactive", password=encoded, is_active=False),
            TokenRow(key="e" * 40, user_id=1),
        ])
        session.commit()
    yield engine
    engine.dispose()


def test_register_creates_user_and_token(client, test_engine):
    response = client.post("/api/user/register/", json={
        "username": "new_user", "password": PASSWORD, "password_confirm": PASSWORD,
    })
    assert response.status_code == 201
    assert response.json()["username"] == "new_user"
    assert len(response.json()["token"]) == 40
    with Session(test_engine) as session:
        user = session.scalar(select(UserRow).where(UserRow.username == "new_user"))
        assert user is not None
        assert user.password != PASSWORD
        assert verify_password(PASSWORD, user.password)
        assert not user.is_staff
        assert session.scalar(select(TokenRow).where(TokenRow.user_id == user.id)).key == response.json()["token"]
    assert client.post("/api/artists/", json={"name": "Muse"}, headers={
        "Authorization": f"Token {response.json()['token']}",
    }).status_code == 403


def test_register_rejects_duplicate_username(client):
    response = client.post("/api/user/register/", json={
        "username": "existing", "password": PASSWORD, "password_confirm": PASSWORD,
    })
    assert response.status_code == 400
    assert "username" in response.json()


def test_register_rejects_password_mismatch(client):
    response = client.post("/api/user/register/", json={
        "username": "new_user", "password": PASSWORD, "password_confirm": "different",
    })
    assert response.status_code == 400
    assert "non_field_errors" in response.json()


@pytest.mark.parametrize("payload", [
    {"username": "new_user", "password": PASSWORD},
    {"username": "bad name", "password": PASSWORD, "password_confirm": PASSWORD},
])
def test_register_rejects_invalid_input(client, payload):
    assert client.post("/api/user/register/", json=payload).status_code == 400


def test_login_reuses_existing_django_token(client):
    response = client.post("/api/user/login/", json={"username": "existing", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json() == {"token": "e" * 40, "username": "existing"}


@pytest.mark.parametrize("username,password", [
    ("unknown", PASSWORD), ("existing", "wrong"), ("inactive", PASSWORD),
])
def test_login_rejects_invalid_credentials(client, username, password):
    response = client.post("/api/user/login/", json={"username": username, "password": password})
    assert response.status_code == 400
    assert "non_field_errors" in response.json()


def test_login_issues_token_that_authorizes_artist_writes(client):
    login = client.post("/api/user/login/", json={"username": "staff", "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["token"]
    created = client.post("/api/artists/", json={"name": "Muse"}, headers={"Authorization": f"Token {token}"})
    assert created.status_code == 201
    assert created.json()["name"] == "Muse"


def test_logout_revokes_token(client):
    headers = {"Authorization": f"Token {'e' * 40}"}
    assert client.post("/api/user/logout/", headers=headers).status_code == 204
    assert client.post("/api/user/logout/", headers=headers).status_code == 401
    assert client.post("/api/artists/", json={"name": "Muse"}, headers=headers).status_code == 401


def test_logout_requires_token(client):
    assert client.post("/api/user/logout/").status_code == 401
