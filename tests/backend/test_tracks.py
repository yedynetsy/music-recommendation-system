"""Track import and recommendation API contracts."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.database import Base
from backend.services.catalog_import import import_tracks
from backend.main import app
from backend.models import ExposureRow, ListenRow, TrackRow
from tests.backend.sample_data import ADMIN_HEADERS, USER_HEADERS
from backend.dependencies import get_serving_model, load_model
from tests.backend.sample_data import FIRST, SECOND, THIRD, FUTURE, CUTOFF, serving_model, add_tracks


def test_import_uses_only_training_metadata_and_preserves_duplicate_names(tmp_path):
    sample = tmp_path / "sample.tsv"
    sample.write_text(
        f"u\t2009-01-01T00:00:00Z\t\tArtist\t{FIRST}\tSame Name\n"
        f"u\t2009-01-01T00:00:01Z\t\tChanged Artist\t{FIRST}\tChanged Name\n"
        f"v\t2009-01-01T00:00:00Z\t\tOther Artist\t{SECOND}\tSame Name\n"
        f"u\t2009-01-02T00:00:00Z\t\tFuture Artist\t{FUTURE}\tFuture Track\n",
        encoding="utf-8",
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.sqlite3'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            first = import_tracks(sample, CUTOFF, session, batch_size=1)
            second = import_tracks(sample, CUTOFF, session, batch_size=1)
            assert first == {"training_events": 3, "distinct_tracks": 2, "inserted_tracks": 2}
            assert second["inserted_tracks"] == 0
            assert session.get(TrackRow, FIRST).name == "Same Name"
            assert session.get(TrackRow, FIRST).artist_name == "Artist"
            assert session.get(TrackRow, SECOND).name == "Same Name"
            assert session.get(TrackRow, FUTURE) is None
    finally:
        engine.dispose()


def test_catalog_is_public_and_uses_mbid_not_name(client, test_engine):
    add_tracks(test_engine)
    response = client.get("/api/tracks/?query=Same%20Name")
    assert response.status_code == 200
    assert {track["mbid"] for track in response.json()} == {FIRST, SECOND}
    assert client.get(f"/api/tracks/{FIRST}/").json()["artist_name"] == "Artist A"
    assert client.get(f"/api/tracks/{FUTURE}/").status_code == 404
    assert len(client.get("/api/tracks/?limit=1").json()) == 1


def test_app_listens_drive_new_user_als_and_exposures(client, test_engine):
    add_tracks(test_engine)
    app.dependency_overrides[get_serving_model] = serving_model
    assert client.get("/api/recommendations/").status_code == 401
    assert client.post(f"/api/tracks/{SECOND}/listens/").status_code == 401
    fallback = client.get("/api/recommendations/?limit=2", headers=USER_HEADERS)
    assert fallback.status_code == 200
    assert fallback.json()["source"] == "popularity"
    assert [item["mbid"] for item in fallback.json()["items"]] == [SECOND, FIRST]
    assert fallback.json()["model_version"] == "test-model"

    assert client.post(f"/api/tracks/{SECOND}/listens/", headers=USER_HEADERS).status_code == 201
    assert client.post(f"/api/tracks/{SECOND}/listens/", headers=USER_HEADERS).status_code == 201
    personalized = client.get("/api/recommendations/?limit=2", headers=USER_HEADERS)
    assert personalized.status_code == 200
    assert personalized.json()["source"] == "als"
    assert {item["mbid"] for item in personalized.json()["items"]} == {FIRST, THIRD}
    with Session(test_engine) as session:
        assert len(list(session.scalars(select(ListenRow).where(ListenRow.user_id == 2)))) == 2
        exposures = list(session.scalars(select(ExposureRow).order_by(ExposureRow.id)))
        assert [(row.rank, row.source) for row in exposures] == [
            (1, "popularity"), (2, "popularity"), (1, "als"), (2, "als")
        ]
        assert {row.user_id for row in exposures} == {2}
        assert {row.model_version for row in exposures} == {"test-model"}


def test_missing_model_or_catalog_metadata_is_explicit(client, test_engine, tmp_path, monkeypatch):
    add_tracks(test_engine)
    monkeypatch.setenv("MUSIC_MODEL_PATH", str(tmp_path / "absent.npz"))
    load_model.cache_clear()
    assert client.get("/api/recommendations/", headers=USER_HEADERS).status_code == 503
    app.dependency_overrides[get_serving_model] = serving_model
    with Session(test_engine) as session:
        session.delete(session.get(TrackRow, SECOND))
        session.commit()
    response = client.get("/api/recommendations/", headers=USER_HEADERS)
    assert response.status_code == 503
    with Session(test_engine) as session:
        assert session.scalar(select(ExposureRow.id)) is None


def test_new_app_users_have_separate_listening_profiles(client, test_engine):
    add_tracks(test_engine)
    app.dependency_overrides[get_serving_model] = serving_model
    assert client.post(f"/api/tracks/{FIRST}/listens/", headers=ADMIN_HEADERS).status_code == 201
    assert client.get("/api/recommendations/", headers=ADMIN_HEADERS).json()["source"] == "als"
    regular = client.get("/api/recommendations/?limit=1", headers=USER_HEADERS)
    assert regular.status_code == 200
    assert regular.json()["source"] == "popularity"
    assert regular.json()["items"][0]["mbid"] == SECOND
    with Session(test_engine) as session:
        assert session.scalar(select(ListenRow.id).where(ListenRow.user_id == 2)) is None


def test_similar_tracks_use_mbid_and_log_exposures(client, test_engine):
    add_tracks(test_engine)
    app.dependency_overrides[get_serving_model] = serving_model
    url = f"/api/tracks/{FIRST}/similar/?limit=2"
    assert client.get(url).status_code == 401
    response = client.get(url, headers=USER_HEADERS)
    assert response.status_code == 200
    assert response.json()["source"] == "similar"
    assert response.json()["model_version"] == "test-model"
    assert [item["mbid"] for item in response.json()["items"]] == [SECOND, THIRD]
    assert [item["name"] for item in response.json()["items"]] == ["Same Name", "Other"]
    with Session(test_engine) as session:
        rows = list(session.scalars(select(ExposureRow).order_by(ExposureRow.rank)))
        assert [(row.track_mbid, row.rank, row.source, row.user_id) for row in rows] == [
            (SECOND, 1, "similar", 2), (THIRD, 2, "similar", 2)
        ]
        assert session.scalar(select(ListenRow.id)) is None


def test_similar_tracks_reject_missing_seed_and_catalog_mismatch(client, test_engine):
    add_tracks(test_engine)
    app.dependency_overrides[get_serving_model] = serving_model
    assert client.get(f"/api/tracks/{FUTURE}/similar/", headers=USER_HEADERS).status_code == 404
    with Session(test_engine) as session:
        session.add(TrackRow(mbid=FUTURE, name="Unmodeled"))
        session.delete(session.get(TrackRow, SECOND))
        session.commit()
    assert client.get(f"/api/tracks/{FUTURE}/similar/", headers=USER_HEADERS).status_code == 404
    assert client.get(f"/api/tracks/{FIRST}/similar/", headers=USER_HEADERS).status_code == 503
    with Session(test_engine) as session:
        assert session.scalar(select(ExposureRow.id)) is None
