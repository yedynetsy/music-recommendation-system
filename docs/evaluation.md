# Evaluation protocol

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
python -m scripts.evaluate_popularity data/sample.tsv \
  --cutoff 2009-01-01T00:00:00Z -k 10
```

Choose and record the cutoff before comparing models. The output includes
the number of eligible warm users, cold users, users without eligible targets,
and macro Recall@K and NDCG@K.

`scripts.compare_models` reads the sample once and applies this exact split
and candidate policy to both popularity and implicit-feedback ALS:

```sh
OPENBLAS_NUM_THREADS=1 python -m scripts.compare_models \
  data/sample-bucket-0-of-10.tsv --cutoff 2009-01-01T00:00:00Z -k 10
```

ALS uses a sparse user-track matrix of **pre-cutoff** listen counts. A listened
track is positive implicit feedback, not an explicit like. The input weight is
`log1p(listen_count)`, and `implicit` scales it by `alpha=10`; unseen pairs
have confidence 1. The logarithm limits the influence of repeated plays.
Default parameters are 32 factors, regularization 0.05, 10 iterations, two
CPU threads, and seed 42. They were fixed for this exploratory run, not tuned
on the holdout. Ranking excludes tracks heard by that user in training. ALS
cannot score a track absent from the training catalog or a user without
training history; cold users remain outside the warm-user macro average.

### Measured Last.fm 1K comparison

The following run used the original Last.fm 1K archive from the dataset record
above (archive MD5 `a79a6808f54f73354789a9fb02cb1e41`; event TSV MD5
`64747b21563e3d2aa95751e0ddc46b68`). The cutoff was
`2009-01-01T00:00:00Z`, with `K=10`. To reproduce the reported sample:

```sh
python -m scripts.prepare_sample \
  data/lastfm-dataset-1K/userid-timestamp-artid-artname-traid-traname.tsv \
  data/sample-bucket-0-of-10.tsv --bucket-count 10 --bucket 0
python -m scripts.evaluate_popularity data/sample-bucket-0-of-10.tsv \
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
| Recall@10, popularity / ALS | 0.00051577 / 0.00119092 |
| NDCG@10, popularity / ALS | 0.01111683 / 0.03257785 |
| Training users / tracks / distinct pairs | 114 / 254,730 / 455,528 |
| ALS fit time / comparison peak memory | 2.8 s / 342 MB |

An initial 1-of-100 bucket sample had only 7 evaluable users and scored zero
on both metrics. The 1-of-10 bucket was used to increase the evaluable group,
not to select a better score. These are exploratory offline results, not a
claim of recommendation quality. ALS ranked above popularity on this sample,
but both absolute scores are low. These metrics apply only to this particular
new-to-user, known-catalog protocol. The comparison does not establish online
quality, statistical significance, or new-user performance. One sampled event
has a 2010 timestamp despite the dataset
description's earlier end date; it was not silently removed. On the development
Mac, sample preparation took 48.5 seconds. The current popularity-only
benchmark took about 6 seconds and peaked at 220 MB of resident memory.
The ALS comparison took about 9.7 seconds end to end,
including 2.8 seconds for fitting, and peaked at 342 MB. These measurements
apply to this sample and machine only. The API uses the offline item factors
for new-user inference; the offline evaluation metrics do not measure this
new-user path.
