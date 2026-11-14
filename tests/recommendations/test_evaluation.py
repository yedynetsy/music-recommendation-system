from datetime import datetime, timezone

import pytest

from recommendations.evaluation import evaluate_popularity, ndcg_at_k, recall_at_k
from recommendations.lastfm import Listen


def listen(user: str, day: int, track: str) -> Listen:
    return Listen(user, datetime(2009, 1, day, tzinfo=timezone.utc), track, "artist", "Artist", track)


def test_metrics_use_unique_hits_and_correct_denominators():
    assert recall_at_k(["a", "a", "b"], {"a", "b", "c"}, 3) == pytest.approx(2 / 3)
    assert ndcg_at_k(["x", "a", "b"], {"a", "b"}, 2) == pytest.approx(
        (1 / 1.584962500721156) / (1 + 1 / 1.584962500721156)
    )
    assert ndcg_at_k(["a", "a", "b"], {"a", "b"}, 3) < 1


def test_global_cutoff_prevents_future_popularity_and_catalog_leakage():
    events = [
        listen("u", 1, "heard"), listen("other", 1, "target"),
        listen("other", 2, "target"), listen("other", 2, "alternate"),
        listen("u", 3, "target"), listen("u", 3, "heard"),
        listen("u", 3, "future_only"),
        listen("new_user", 3, "target"),
        listen("other", 3, "future_only"),
    ]
    result = evaluate_popularity(events, datetime(2009, 1, 3, tzinfo=timezone.utc), k=1)
    assert result.users == 1
    assert result.cold_users == 1
    assert result.users_without_targets == 1  # other has only previously heard/new tracks
    assert result.recall == 1
    assert result.ndcg == 1


def test_no_evaluable_users_is_explicit():
    result = evaluate_popularity([listen("new", 2, "x")], datetime(2009, 1, 2, tzinfo=timezone.utc))
    assert result.users == 0
    assert result.cold_users == 1
    assert result.recall == 0


def test_cutoff_requires_timezone():
    with pytest.raises(ValueError):
        evaluate_popularity([], datetime(2009, 1, 1))
