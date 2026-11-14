# Music Recommendation System

The backend is a FastAPI catalog and token-authentication API backed by
SQLAlchemy and Alembic. The framework-independent `recommendations` package
contains the offline recommendation experiments.

## Backend setup

Install the project and development dependencies, then create a fresh database
from the repository root:

```sh
python -m pip install -e '.[dev]'
python -m alembic upgrade head
python -m fastapi_app.create_staff
python -m uvicorn fastapi_app.main:app --port 8001
```

The default URL is `sqlite:///db.sqlite3` in the repository root. Set
`MUSIC_DATABASE_URL` for another SQLite database or PostgreSQL; both Alembic
and the API use it. The app never creates tables automatically. The initial
Alembic revision creates only users, tokens, artists, and albums. It retains
the old table names so existing local catalog data and PBKDF2-SHA256 password
hashes remain readable. The password verifier supports that hash format;
accounts using a different legacy hash algorithm require a password reset.

An existing database created by the previous backend already has these tables.
Back it up and inspect its schema before running `python -m alembic stamp head`
once; `upgrade head` is for a fresh database. The stamp records the baseline
without recreating tables. The old local `db.sqlite3` is ignored by Git and is
not modified by this repository change.

## Catalog and authentication

`POST /api/user/register/` creates a user and returns a token (`201`).
`POST /api/user/login/` returns a token for valid credentials (`200`), reusing
an existing token. `POST /api/user/logout/` revokes that token (`204`). These
routes accept JSON request bodies. Registering creates a regular user; catalog
writes require a staff account. No public endpoint grants staff access.
The local `create_staff` command prompts for a username and hidden password;
run it after the migration to create the first staff account.

`GET /api/artists/` lists artists by name. `GET /api/artists/{id}/` returns one
artist or `404`. Both routes are public. `POST /api/artists/` and `PUT`, `PATCH`,
and `DELETE /api/artists/{id}/` require an active staff user's token in the
`Authorization: Token <key>` header.
Invalid artist input returns `400`; deleting an artist with albums returns
`409` and keeps the artist.

`GET /api/albums/` lists albums by name and `GET /api/albums/{id}/` returns an
album with both `artist` (ID) and `artist_detail` (artist object). Both are
public. `POST /api/albums/` and `PUT`, `PATCH`, and `DELETE` on
`/api/albums/{id}/` require an active staff user's token. Creating an album
requires a name and an existing artist ID; description and release date are
optional. Invalid input or an unknown artist returns `400`, and an unknown
album returns `404`. Updates retain optional fields when omitted; send
`release_date: null` to clear a date. SQLite behavior has been tested locally;
PostgreSQL has not yet been verified.

## Last.fm 1K development sample

Obtain `lastfm-dataset-1K.tar.gz` from the [dataset record](https://zenodo.org/records/6090214)
and extract `userid-timestamp-artid-artname-traid-traname.tsv` locally. Do not
commit the source file, sample, or model outputs. The dataset is available for
non-commercial use and requires a reference to [Last.fm](https://www.last.fm/).

```sh
python -m recommendations.prepare \
  data/lastfm-1k/userid-timestamp-artid-artname-traid-traname.tsv \
  data/sample.tsv --bucket-count 100 --bucket 0
```

The command streams the six-column TSV, selects complete user histories by a
stable SHA-256 bucket, retains track MusicBrainz IDs as keys, and prints event
counts. The default selects roughly 1% of users, but the actual size depends
on their listening activity. Rows without a track MusicBrainz ID are dropped
and counted; matching names would conflate different recordings. Artist and
track names remain descriptive metadata, not identifiers. No albums, explicit
likes/dislikes, or audio features are available as training signals here.

## Evaluation protocol (first baseline)

`evaluate_popularity(events, cutoff, k)` uses a single UTC-aware cutoff:
events before it form training data; events at or after it form the holdout.
Popularity is the count of training events per track. The candidate set for
each user is the training catalog minus tracks that user heard in training.
The test targets are distinct held-out tracks in that candidate set. This is
therefore a **new-to-user** task; repeated listening is excluded from targets.
Users with no training history are counted as cold users and excluded from
the warm-user macro average. Users with no eligible target are also counted
separately. Recall@K and NDCG@K average equally over eligible users.

The shared global cutoff prevents future events from any user from entering
training counts or the catalog. Run a local measurement with:

```sh
python -m recommendations.benchmark data/sample.tsv \
  --cutoff 2009-01-01T00:00:00Z -k 10
```

Choose and record the cutoff before comparing models. The output includes
the number of eligible warm users, cold users, users without eligible targets,
and macro Recall@K and NDCG@K. ALS is a later step.

### Measured Last.fm 1K baseline

The following run used the original Last.fm 1K archive from the dataset record
above (archive MD5 `a79a6808f54f73354789a9fb02cb1e41`; event TSV MD5
`64747b21563e3d2aa95751e0ddc46b68`). The cutoff was
`2009-01-01T00:00:00Z`, with `K=10`. To reproduce the reported sample:

```sh
python -m recommendations.prepare \
  data/lastfm-dataset-1K/userid-timestamp-artid-artname-traid-traname.tsv \
  data/sample-bucket-0-of-10.tsv --bucket-count 10 --bucket 0
python -m recommendations.benchmark data/sample-bucket-0-of-10.tsv \
  --cutoff 2009-01-01T00:00:00Z -k 10
```

| Measure | Result |
| --- | ---: |
| Source events | 19,150,868 |
| Selected events (bucket 0 of 10) | 2,543,302 |
| Selected events without track MBID | 342,750 (13.5%) |
| Events in sample after filtering | 2,200,552 |
| Sample users | 117 |
| Training / holdout events | 1,931,776 / 268,776 |
| Evaluable warm users / cold users / users without targets | 94 / 3 / 11 |
| Recall@10 | 0.00051577 |
| NDCG@10 | 0.01111683 |

An initial 1-of-100 bucket sample had only 7 evaluable users and scored zero
on both metrics. The 1-of-10 bucket was used to increase the evaluable group,
not to select a better score. These are exploratory offline results, not a
claim of recommendation quality. The metrics apply to this particular
new-to-user, known-catalog protocol and popularity ranking; ALS has not yet
been measured. One sampled event has a 2010 timestamp despite the dataset
description's earlier end date; it was not silently removed. On the development
Mac, sample preparation took 48.5 seconds, the benchmark took 6.5 seconds,
and the benchmark process peaked at approximately 210 MB of resident memory.
These measurements apply to this sample and machine only.

## Tests

```sh
python -m pytest
```
