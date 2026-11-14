"""Smoke-test the local Streamlit journey with an in-memory API stand-in."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

import demo.api_client


ARTIST = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TRACK = "11111111-1111-4111-8111-111111111111"


def test_demo_login_onboarding_recommendation_and_listen(monkeypatch):
    calls = []

    class FakeAPI:
        def __init__(self, base_url, token=None):
            self.token = token

        def login(self, username, password):
            calls.append(("login", username))
            return {"token": "t" * 40, "username": username}

        def artist_choices(self):
            return []

        def search_artists(self, query):
            return [{"mbid": ARTIST, "name": "Artist"}]

        def save_artist_choices(self, mbids):
            calls.append(("artists", mbids))
            return mbids

        def recommendations(self, limit=10):
            calls.append(("recommendations", self.token))
            return {"source": "onboarding", "model_version": "test", "items": [
                {"mbid": TRACK, "name": "Track", "artist_name": "Artist"}]}

        def listen(self, mbid):
            calls.append(("listen", mbid))
            return {"track_mbid": mbid}

    monkeypatch.setattr(demo.api_client, "MusicAPI", FakeAPI)
    app_path = Path(__file__).resolve().parents[2] / "demo" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=10).run()
    assert not app.exception
    app.text_input(key="login_name").set_value("demo")
    app.text_input(key="login_password").set_value("secret")
    app.button(key="FormSubmitter:login_form-Увійти").click().run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Рекомендації", "Виконавці", "Каталог"]

    app.text_input(key="artist_query").set_value("Artist")
    app.button(key="FormSubmitter:artist_search_form-Знайти виконавців").click().run()
    assert not app.exception
    app.multiselect(key="artist_selection").set_value([ARTIST]).run()
    app.button(key="save_artists").click().run()
    app.button(key="get_recommendations").click().run()
    assert not app.exception
    assert ("artists", [ARTIST]) in calls
    assert ("recommendations", "t" * 40) in calls
    app.button(key=f"recommendation_listen_{TRACK}").click().run()
    assert ("listen", TRACK) in calls
    assert not app.exception
