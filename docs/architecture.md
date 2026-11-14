# Architecture

The project has three runtime parts: the FastAPI backend, a framework-independent
recommendation package, and a Streamlit demonstration that calls the backend
through HTTP.

## Backend

`backend/main.py` creates the app, registers routers, and installs exception
handlers. `backend/routes/` defines HTTP parameters, authentication dependencies,
and response schemas for authentication, artists, albums, tracks, listens,
onboarding, and recommendations.

`backend/services/` contains application workflows: catalog import, staff account
creation, artist seed selection, and recommendation serving. Recommendation
serving combines the user's app listens or onboarding seeds with the fixed model,
checks catalog coverage, and commits recommendation exposures. Service errors
are translated into HTTP responses by `backend/exception_handlers.py`.

`backend/database.py` provides SQLAlchemy sessions, `models.py` defines database
tables, and `schemas.py` defines Pydantic request/response contracts.
`security.py` handles password hashes, tokens, and access checks.
`dependencies.py` caches the artifact loaded for recommendation requests.

The default database remains `db.sqlite3` at the repository root. The default
model remains `data/als-model.npz`. `MUSIC_DATABASE_URL` and `MUSIC_MODEL_PATH`
override these paths. Existing table names, Alembic revisions, API URLs, and
artifact format are preserved by the source reorganization.

Compose uses separate `MUSIC_POSTGRES_HOST`, `MUSIC_POSTGRES_PORT` (default
5432), `MUSIC_POSTGRES_USER`, `MUSIC_POSTGRES_DB`, and `MUSIC_POSTGRES_PASSWORD`
settings to construct a psycopg URL. An explicit `MUSIC_DATABASE_URL` takes
precedence. See [containers.md](containers.md) for startup, migrations,
persistence, and the PostgreSQL integration checks.

## Recommendation package

- `lastfm.py`: streaming Last.fm event reader and deterministic user sampling.
- `als.py`: sparse training matrix and implicit-feedback ALS fitting.
- `evaluation.py`: temporal splitting, candidate policy, and ranking metrics.
- `artifacts.py`: save/load item factors, metadata, and model version.
- `inference.py`: infer an app user's factor, rank tracks, and find similar items.

This package does not import the backend, SQLAlchemy, or Streamlit. Application
users and historical Last.fm listeners have separate identities and events.
See [evaluation.md](evaluation.md) for the offline protocol and limitations.

## Demo and commands

`demo/app.py` presents the Streamlit UI; `demo/api_client.py` makes bounded HTTP
requests and reports errors. The demo accesses data and models through the API.

Commands run from the repository root:

```sh
python -m scripts.prepare_sample --help
python -m scripts.evaluate_popularity --help
python -m scripts.compare_models --help
python -m scripts.export_model --help
python -m scripts.import_catalog --help
python -m scripts.create_staff
python -m uvicorn backend.main:app --port 8001
python -m streamlit run demo/app.py --server.address 127.0.0.1
```

These replace the earlier `fastapi_app`, `music_demo`, and shorter CLI module
paths. Recommendation artifact I/O is available from `recommendations.artifacts`
and `ServingModel` from `recommendations.inference`.

## Tests

`tests/backend/`, `tests/recommendations/`, and `tests/demo/` group checks by the
component they exercise. `tests/conftest.py` supplies common database/client
fixtures; authentication tests override the database fixture for their own
accounts. `tests/backend/sample_data.py` contains small shared catalog/model
examples. Tests do not import fixtures or helpers from other test modules.
