"""Artist MBID onboarding and the empty-model-coverage fallback."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi_app.main import app
from fastapi_app.models import ArtistPreferenceRow, ExposureRow, ListenRow, TrackRow
from fastapi_app.tests.test_artists import ADMIN_HEADERS, USER_HEADERS, client, test_engine
from fastapi_app.tests.test_tracks import (FIRST, SECOND, THIRD, FUTURE, add_tracks,
                                           serving_model)
from fastapi_app.tracks import get_serving_model


ARTIST_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ARTIST_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def add_artist_mbids(engine):
    add_tracks(engine)
    with Session(engine) as session:
        session.get(TrackRow, FIRST).artist_mbid = ARTIST_A
        session.get(TrackRow, SECOND).artist_mbid = ARTIST_B
        session.add(TrackRow(mbid=FUTURE, name="Other", artist_mbid=ARTIST_A,
                             artist_name="Artist A"))
        session.commit()


def test_artist_search_uses_mbid_and_choices_are_private(client, test_engine):
    add_artist_mbids(test_engine)
    result = client.get("/api/onboarding/artists/search/?query=Artist")
    assert result.status_code == 200
    assert {row["mbid"] for row in result.json()} == {ARTIST_A, ARTIST_B}
    assert client.put("/api/onboarding/artists/", json={"artist_mbids": [ARTIST_A]}).status_code == 401
    saved = client.put("/api/onboarding/artists/", json={"artist_mbids": [ARTIST_A]},
                       headers=USER_HEADERS)
    assert saved.json() == {"artist_mbids": [ARTIST_A]}
    assert client.get("/api/onboarding/artists/", headers=USER_HEADERS).json() == saved.json()
    assert client.get("/api/onboarding/artists/", headers=ADMIN_HEADERS).json() == {"artist_mbids": []}
    assert client.put("/api/onboarding/artists/", json={"artist_mbids": [ARTIST_B]},
                      headers=USER_HEADERS).json() == {"artist_mbids": [ARTIST_B]}
    with Session(test_engine) as session:
        assert session.scalars(select(ArtistPreferenceRow.artist_mbid)).all() == [ARTIST_B]
        assert session.scalar(select(ListenRow.id)) is None


def test_invalid_or_unknown_artist_choice_preserves_saved_choices(client, test_engine):
    add_artist_mbids(test_engine)
    client.put("/api/onboarding/artists/", json={"artist_mbids": [ARTIST_A]},
               headers=USER_HEADERS)
    for ids in ([ARTIST_B, ARTIST_B], ["not-an-mbid"], [THIRD]):
        assert client.put("/api/onboarding/artists/", json={"artist_mbids": ids},
                          headers=USER_HEADERS).status_code == 422
    assert client.get("/api/onboarding/artists/", headers=USER_HEADERS).json() == {
        "artist_mbids": [ARTIST_A]}
    assert client.put("/api/onboarding/artists/", json={"artist_mbids": []},
                      headers=USER_HEADERS).json() == {"artist_mbids": []}


def test_onboarding_recommendations_and_fallback(client, test_engine):
    add_artist_mbids(test_engine)
    app.dependency_overrides[get_serving_model] = serving_model
    client.put("/api/onboarding/artists/", json={"artist_mbids": [ARTIST_A]},
               headers=USER_HEADERS)
    result = client.get("/api/recommendations/?limit=2", headers=USER_HEADERS)
    assert result.status_code == 200
    assert result.json()["source"] == "onboarding"
    assert FIRST not in [item["mbid"] for item in result.json()["items"]]
    with Session(test_engine) as session:
        assert session.scalar(select(ListenRow.id)) is None
        assert {row.source for row in session.scalars(select(ExposureRow))} == {"onboarding"}
    assert client.post(f"/api/tracks/{SECOND}/listens/", headers=USER_HEADERS).status_code == 201
    assert client.get("/api/recommendations/", headers=USER_HEADERS).json()["source"] == "als"

    client.put("/api/onboarding/artists/", json={"artist_mbids": [ARTIST_A]},
               headers=ADMIN_HEADERS)
    with Session(test_engine) as session:
        session.get(TrackRow, FIRST).artist_mbid = None
        session.commit()
    fallback = client.get("/api/recommendations/?limit=1", headers=ADMIN_HEADERS)
    assert fallback.json()["source"] == "popularity"
    assert fallback.json()["items"][0]["mbid"] == SECOND
