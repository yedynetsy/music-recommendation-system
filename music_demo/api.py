"""HTTP client for the Streamlit demo; no database or model access."""

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class APIError(Exception):
    status_code: int | None
    message: str

    def __str__(self) -> str:
        return self.message


class MusicAPI:
    def __init__(self, base_url: str, token: str | None = None,
                 transport: httpx.BaseTransport | None = None):
        try:
            url = httpx.URL(base_url)
        except httpx.InvalidURL as error:
            raise APIError(None, "Вкажіть коректну адресу API.") from error
        if url.scheme not in {"http", "https"} or not url.host:
            raise APIError(None, "Адреса API має починатися з http:// або https://.")
        self.base_url = base_url.rstrip("/") + "/"
        self.token = token
        self.transport = transport

    def request(self, method: str, path: str, *, params: dict | None = None,
                payload: dict | None = None) -> Any:
        headers = {"Authorization": f"Token {self.token}"} if self.token else {}
        try:
            with httpx.Client(base_url=self.base_url, timeout=10.0,
                              transport=self.transport) as client:
                response = client.request(method, path.lstrip("/"), params=params,
                                          json=payload, headers=headers)
        except httpx.RequestError as error:
            raise APIError(None, f"API недоступний: {error}") from error
        if response.is_error:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            if isinstance(detail, dict):
                detail = detail.get("detail", detail)
            raise APIError(response.status_code, f"HTTP {response.status_code}: {detail}")
        return response.json() if response.content else None

    def login(self, username: str, password: str) -> dict:
        return self.request("POST", "api/user/login/",
                            payload={"username": username, "password": password})

    def register(self, username: str, password: str) -> dict:
        return self.request("POST", "api/user/register/", payload={
            "username": username, "password": password, "password_confirm": password})

    def logout(self) -> None:
        self.request("POST", "api/user/logout/")

    def search_artists(self, query: str) -> list[dict]:
        return self.request("GET", "api/onboarding/artists/search/",
                            params={"query": query, "limit": 20})

    def artist_choices(self) -> list[str]:
        return self.request("GET", "api/onboarding/artists/")["artist_mbids"]

    def save_artist_choices(self, mbids: list[str]) -> list[str]:
        return self.request("PUT", "api/onboarding/artists/",
                            payload={"artist_mbids": mbids})["artist_mbids"]

    def search_tracks(self, query: str) -> list[dict]:
        return self.request("GET", "api/tracks/", params={"query": query, "limit": 20})

    def listen(self, mbid: str) -> dict:
        return self.request("POST", f"api/tracks/{mbid}/listens/")

    def recommendations(self, limit: int = 10) -> dict:
        return self.request("GET", "api/recommendations/", params={"limit": limit})

    def similar(self, mbid: str, limit: int = 10) -> dict:
        return self.request("GET", f"api/tracks/{mbid}/similar/", params={"limit": limit})
