from sqlalchemy.engine import make_url

from backend.database import configured_database_url


def test_explicit_database_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("MUSIC_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("MUSIC_POSTGRES_HOST", "db")
    assert configured_database_url() == "sqlite:///:memory:"


def test_postgres_components_preserve_special_password_characters(monkeypatch):
    monkeypatch.delenv("MUSIC_DATABASE_URL", raising=False)
    monkeypatch.setenv("MUSIC_POSTGRES_HOST", "db")
    monkeypatch.setenv("MUSIC_POSTGRES_PASSWORD", "test/@:#?%password")
    monkeypatch.delenv("MUSIC_POSTGRES_PORT", raising=False)
    url = make_url(configured_database_url())
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "test/@:#?%password"
    assert url.host == "db"
    assert url.port == 5432
