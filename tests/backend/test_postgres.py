"""Opt-in checks against migrated PostgreSQL, isolated in a disposable schema."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import database_url, get_session
from backend.dependencies import get_serving_model
from backend.main import app
from backend.models import ExposureRow, ListenRow, TrackRow, UserRow
from backend.services.accounts import create_staff
from tests.backend.sample_data import FIRST, SECOND, serving_model, add_tracks


pytestmark = pytest.mark.skipif(
    os.environ.get("MUSIC_TEST_POSTGRES") != "1",
    reason="Set MUSIC_TEST_POSTGRES=1 with a PostgreSQL connection to run integration checks",
)


@pytest.fixture(scope="module")
def postgres_engine():
    url = make_url(database_url)
    assert url.get_backend_name() == "postgresql"
    schema = "test_" + uuid4().hex
    admin_engine = create_engine(url)
    engine = None
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        isolated_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
        env = {**os.environ, "MUSIC_DATABASE_URL": isolated_url.render_as_string(hide_password=False)}
        root = Path(__file__).resolve().parents[2]
        for arguments in [("upgrade", "head"), ("check",)]:
            result = subprocess.run([sys.executable, "-m", "alembic", *arguments],
                                    cwd=root, env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
        engine = create_engine(isolated_url)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def test_postgres_auth_catalog_and_recommendation_flow(postgres_engine, monkeypatch):
    def session_dependency():
        with Session(postgres_engine) as session:
            yield session

    monkeypatch.setattr("backend.services.accounts.SessionFactory", lambda: Session(postgres_engine))
    create_staff("pg_staff", "test-password")
    add_tracks(postgres_engine)
    artist_mbid = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    with Session(postgres_engine) as session:
        session.get(TrackRow, FIRST).artist_mbid = artist_mbid
        session.commit()
    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_serving_model] = serving_model
    try:
        with TestClient(app) as client:
            staff = client.post("/api/user/login/", json={
                "username": "pg_staff", "password": "test-password"})
            assert staff.status_code == 200
            staff_headers = {"Authorization": "Token " + staff.json()["token"]}
            artist = client.post("/api/artists/", json={"name": "PostgreSQL artist"}, headers=staff_headers)
            assert artist.status_code == 201
            album = client.post("/api/albums/", json={
                "name": "PostgreSQL album", "artist": artist.json()["id"],
                "release_date": "2009-01-01"}, headers=staff_headers)
            assert album.status_code == 201
            assert album.json()["release_date"] == "2009-01-01"
            assert client.delete(f"/api/artists/{artist.json()['id']}/", headers=staff_headers).status_code == 409
            registration = client.post("/api/user/register/", json={
                "username": "pg_user", "password": "test-password", "password_confirm": "test-password"})
            assert registration.status_code == 201
            headers = {"Authorization": "Token " + registration.json()["token"]}
            assert client.get("/api/recommendations/", headers=headers).json()["source"] == "popularity"
            choice = client.put("/api/onboarding/artists/", json={"artist_mbids": [artist_mbid]}, headers=headers)
            assert choice.status_code == 200
            assert client.get("/api/recommendations/", headers=headers).json()["source"] == "onboarding"
            listen = client.post(f"/api/tracks/{SECOND}/listens/", headers=headers)
            assert listen.status_code == 201
            assert listen.json()["created_at"].endswith("Z")
            ranking = client.get("/api/recommendations/", headers=headers)
            assert ranking.status_code == 200 and ranking.json()["source"] == "als"
            assert SECOND not in [item["mbid"] for item in ranking.json()["items"]]
            assert client.get(f"/api/tracks/{FIRST}/similar/", headers=headers).status_code == 200
            assert client.post("/api/user/logout/", headers=headers).status_code == 204
            assert client.get("/api/recommendations/", headers=headers).status_code == 401
        with Session(postgres_engine) as session:
            user_id = session.scalar(select(UserRow.id).where(UserRow.username == "pg_user"))
            assert session.scalar(select(func.count(ListenRow.id)).where(ListenRow.user_id == user_id)) == 1
            sources = set(session.scalars(select(ExposureRow.source).where(ExposureRow.user_id == user_id)))
            assert sources == {"als", "onboarding", "popularity", "similar"}
    finally:
        app.dependency_overrides.clear()


def test_postgres_enforces_listen_foreign_keys(postgres_engine):
    with Session(postgres_engine) as session:
        session.add(ListenRow(user_id=-1, track_mbid=FIRST,
                              created_at=datetime.now(timezone.utc)))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
