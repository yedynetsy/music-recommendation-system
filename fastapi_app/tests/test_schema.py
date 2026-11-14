"""The API must start from Alembic's schema without a legacy framework."""

import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from fastapi_app.create_staff import create_staff
from fastapi_app.database import get_session
from fastapi_app.main import app
from fastapi_app.models import UserRow


def test_fresh_migration_supports_catalog_and_authentication(tmp_path, monkeypatch):
    database = tmp_path / "catalog.sqlite3"
    url = f"sqlite:///{database}"
    project_root = Path(__file__).resolve().parent.parent.parent
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=project_root,
        env={**os.environ, "MUSIC_DATABASE_URL": url},
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"users_user", "authtoken_token", "artists_artist", "albums_album",
                "alembic_version"} <= tables
        assert "django_session" not in tables

        monkeypatch.setattr("fastapi_app.create_staff.SessionFactory", lambda: Session(engine))
        create_staff("staff", "password")
        with pytest.raises(ValueError, match="already exists"):
            create_staff("staff", "password")
        with Session(engine) as session:
            assert session.query(UserRow).filter_by(username="staff", is_staff=True).count() == 1

        def migrated_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = migrated_session
        with TestClient(app) as client:
            login = client.post("/api/user/login/", json={
                "username": "staff", "password": "password"
            })
            assert login.status_code == 200
            headers = {"Authorization": f"Token {login.json()['token']}"}
            artist = client.post("/api/artists/", json={"name": "New Artist"}, headers=headers)
            assert artist.status_code == 201
            album = client.post("/api/albums/", json={
                "name": "New Album", "artist": artist.json()["id"]
            }, headers=headers)
            assert album.status_code == 201
            assert client.get(f"/api/albums/{album.json()['id']}/").json()[
                "artist_detail"]["name"] == "New Artist"
            assert client.post("/api/user/logout/", headers=headers).status_code == 204
            assert client.delete(f"/api/albums/{album.json()['id']}/", headers=headers).status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
