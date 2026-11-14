# PostgreSQL and Docker Compose

Compose runs PostgreSQL 17, a one-shot Alembic migration, FastAPI, and Streamlit.
The application image uses Python 3.12 and runs as an unprivileged user. The
PostgreSQL service is available only inside the Compose network. API and demo
ports bind to the host's loopback interface.

## Start

Docker Desktop or Docker Engine with Compose must be running. From the
repository root, create a local environment file with a random password:

```sh
python -c 'from pathlib import Path; import secrets; p = Path(".env.compose"); p.open("x").write("POSTGRES_PASSWORD=" + secrets.token_hex(24) + "\n")'
docker compose --env-file .env.compose up -d --build
docker compose --env-file .env.compose ps -a
```

The creation command refuses to overwrite an existing file. `.env.compose`
is ignored by Git and excluded from the build context. Optional port settings
are shown in `.env.compose.example`; default ports are API 8001 and demo 8501.
The password may contain URL-special characters: the backend constructs the
SQLAlchemy connection URL from separate settings.

Compose waits for PostgreSQL's health check, then waits for Alembic to finish
successfully before starting the API. Streamlit waits for the API's catalog
health check. That check confirms database access, not model availability.

Open the demo at <http://127.0.0.1:8501> and API documentation at
<http://127.0.0.1:8001/docs>. A new PostgreSQL volume starts with an empty
catalog. The existing root `db.sqlite3` is not copied or migrated into it.

## Load the catalog and model

Prepare the sample and export `data/als-model.npz` on the host using the
[README commands](../README.md#track-catalog-and-recommendations). The API
mounts `./data` read-only at `/app/data`; raw data and artifacts are excluded
from the image. Import the matching pre-cutoff catalog into PostgreSQL:

```sh
docker compose --env-file .env.compose run --rm api \
  python -m scripts.import_catalog /app/data/sample-bucket-0-of-10.tsv \
  --cutoff 2009-01-01T00:00:00Z
```

Import does not overwrite existing metadata. The model is cached by the API;
after replacing it, run `docker compose --env-file .env.compose restart api`.
Until a matching artifact and catalog are available, recommendation requests
return `503`; the catalog and authentication routes remain available.

Regular users can register in the demo. To create a staff account, use the
trusted terminal command:

```sh
docker compose --env-file .env.compose run --rm api python -m scripts.create_staff
```

## Verify

The integration checks have passed locally with PostgreSQL 14.20 and Python
3.10. The Compose configuration has passed `docker compose config --quiet`.
The Docker image build and the PostgreSQL 17 container run have not yet been
verified: Docker Desktop was running but its daemon did not answer requests
on the development machine. Run the commands below once the engine is ready.

```sh
docker compose --env-file .env.compose config --quiet
docker compose --env-file .env.compose run --rm migrate python -m alembic check
docker compose --env-file .env.compose --profile test build tests
docker compose --env-file .env.compose --profile test run --rm tests
```

The test image includes development dependencies and tests; the runtime image
does not. Most tests keep using temporary SQLite databases. The opt-in
PostgreSQL checks create a unique schema, apply all migrations, check schema
agreement, and exercise authentication, artist/album writes, onboarding,
fallback, ALS inference, similar tracks, listens, exposures, and foreign keys.
The checks use a small synthetic model and drop only their own schema afterward.
They do not prove recommendation quality or production scalability.

To run PostgreSQL integration checks outside Docker, set `MUSIC_DATABASE_URL`
to a dedicated `postgresql+psycopg://...` connection and `MUSIC_TEST_POSTGRES=1`,
then run `python -m pytest tests/backend/test_postgres.py`. The role must be
allowed to create schemas. Without the opt-in flag, these checks are skipped.

## Persistence and troubleshooting

```sh
docker compose --env-file .env.compose logs --tail=100 migrate api
docker compose --env-file .env.compose down
```

`down` retains the named `postgres_data` volume, including application users,
catalog, and interactions. Changing the password in `.env.compose` does not
change the password of a previously initialized PostgreSQL volume. Do not
remove volumes to resolve a connection problem without first backing them up.
Images follow the Python 3.12 and PostgreSQL 17 release tags; they are not
locked to immutable digests or a complete dependency lockfile.

The startup dependencies follow Docker's
[Compose startup-order documentation](https://docs.docker.com/compose/how-tos/startup-order/).
The PostgreSQL volume path follows the
[official PostgreSQL image](https://hub.docker.com/_/postgres) layout for version 17.
