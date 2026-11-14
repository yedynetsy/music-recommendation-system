# Music Recommendation System

This project has a Django/DRF API for users, artists, and albums. A separate
FastAPI app now serves read-only artist catalog routes. The framework-independent
`recommendations` package contains the offline recommendation experiments.

## FastAPI artist catalog

The FastAPI app reads the existing `artists_artist` table through SQLAlchemy.
Django migrations still own that table, so run them before starting against a
fresh local database. From the repository root, with dependencies installed:

```sh
python -m uvicorn fastapi_app.main:app --port 8001
```

`GET /api/artists/` lists artists by name. `GET /api/artists/{id}/` returns one
artist or `404`. Both routes are public and return the same artist fields as
the Django API. The default database is the project's local `db.sqlite3`;
`MUSIC_DATABASE_URL` can override the SQLAlchemy connection URL. Only local
SQLite behavior has been verified. Django still serves artist writes and the
user and album routes. The FastAPI app is a separate process during migration.

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
python -m pytest recommendations
```

The existing Django tests require the project's development dependencies and
the local `.env` configuration.
