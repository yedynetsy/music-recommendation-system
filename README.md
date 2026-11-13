# Music Recommendation System

This project currently has a Django/DRF API for users, artists, and albums.
The framework-independent `recommendations` package begins the offline
recommendation pipeline. The API has not yet been migrated to FastAPI.

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
training counts or the catalog. The result is a popularity baseline only:
there are no measured Last.fm scores yet because the dataset is not included
in this repository. Run a local measurement with:

```sh
python -m recommendations.benchmark data/sample.tsv \
  --cutoff 2009-01-01T00:00:00Z -k 10
```

Choose and record the cutoff before comparing models. The output includes
the number of eligible warm users, cold users, users without eligible targets,
and macro Recall@K and NDCG@K. ALS is a later step.

## Tests

```sh
python -m pytest recommendations
```

The existing Django tests require the project's development dependencies and
the local `.env` configuration.
