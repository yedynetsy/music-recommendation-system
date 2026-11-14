"""Check the demo's HTTP contract and failure handling without a server."""

import httpx
import pytest

from music_demo.api import APIError, MusicAPI


TOKEN = "t" * 40


def test_demo_calls_api_with_token_and_mbid():
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path == "/api/user/login/":
            return httpx.Response(200, json={"token": TOKEN, "username": "demo"})
        if request.url.path == "/api/user/logout/":
            return httpx.Response(204)
        return httpx.Response(200, json={"items": [], "artist_mbids": []})

    transport = httpx.MockTransport(respond)
    guest = MusicAPI("http://example.test/", transport=transport)
    assert guest.login("demo", "secret")["token"] == TOKEN
    assert calls[0].headers.get("authorization") is None
    assert calls[0].read() == b'{"username":"demo","password":"secret"}'

    user = MusicAPI("http://example.test", TOKEN, transport=transport)
    user.save_artist_choices(["artist-mbid"])
    user.listen("track-mbid")
    user.similar("track-mbid", 5)
    user.recommendations(10)
    assert all(request.headers["authorization"] == f"Token {TOKEN}" for request in calls[1:])
    assert [request.url.path for request in calls[1:]] == [
        "/api/onboarding/artists/", "/api/tracks/track-mbid/listens/",
        "/api/tracks/track-mbid/similar/", "/api/recommendations/",
    ]
    assert calls[1].read() == b'{"artist_mbids":["artist-mbid"]}'
    assert calls[3].url.params["limit"] == "5"
    assert user.logout() is None


def test_demo_reports_api_errors():
    transport = httpx.MockTransport(lambda request: httpx.Response(
        503, json={"detail": "Recommendation model is unavailable."}))
    with pytest.raises(APIError, match="HTTP 503: Recommendation model is unavailable"):
        MusicAPI("http://example.test", transport=transport).recommendations()


def test_demo_reports_connection_errors():
    def fail(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(APIError, match="API недоступний"):
        MusicAPI("http://example.test", transport=httpx.MockTransport(fail)).search_tracks("x")


def test_demo_rejects_invalid_api_address():
    with pytest.raises(APIError, match="http://"):
        MusicAPI("localhost:8001")
