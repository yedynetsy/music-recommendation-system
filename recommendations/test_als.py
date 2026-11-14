from datetime import datetime, timezone

import numpy as np
import pytest

from recommendations.als import ALSConfig, fit_als, training_matrix
from recommendations.evaluation import evaluate_rankings, split_events
from recommendations.lastfm import Listen


CUTOFF = datetime(2009, 1, 2, tzinfo=timezone.utc)


def listen(user: str, track: str, day: int = 1) -> Listen:
    return Listen(user, datetime(2009, 1, day, tzinfo=timezone.utc),
                  track, "artist", "Artist", track)


def test_training_matrix_uses_only_past_listens_and_diminishing_repeat_weight():
    data = split_events([
        listen("u", "a"), listen("u", "a"), listen("u", "b"),
        listen("v", "c"), listen("u", "future", 2),
    ], CUTOFF)
    matrix, users, tracks = training_matrix(data)
    assert tracks == ["a", "b", "c"]
    assert matrix.shape == (2, 3)
    assert matrix.nnz == 3
    assert matrix[users["u"], tracks.index("a")] == pytest.approx(np.log1p(2))
    assert matrix[users["u"], tracks.index("b")] == pytest.approx(np.log1p(1))
    assert data.future["u"] == {"future"}


def test_als_recommendations_respect_known_catalog_and_seen_filter():
    data = split_events([
        listen("u", "a"), listen("u", "a"),
        listen("v", "a"), listen("v", "b"),
        listen("w", "b"), listen("w", "c"),
        listen("u", "b", 2), listen("cold", "a", 2),
    ], CUTOFF)
    model = fit_als(data, ALSConfig(factors=3, iterations=2, threads=1, seed=7))
    ranked = model.recommend("u", 10)
    assert set(ranked) == {"b", "c"}
    assert "a" not in ranked
    result = evaluate_rankings(data, 2, model.recommend)
    assert result.users == 1
    assert result.cold_users == 1
    assert 0 <= result.recall <= 1
    assert 0 <= result.ndcg <= 1


def test_evaluation_rejects_items_outside_shared_candidate_set():
    data = split_events([listen("u", "seen"), listen("v", "target"),
                         listen("u", "target", 2)], CUTOFF)
    with pytest.raises(ValueError, match="outside the candidate set"):
        evaluate_rankings(data, 1, lambda user, k: ["seen"])
    with pytest.raises(ValueError, match="outside the candidate set"):
        evaluate_rankings(data, 1, lambda user, k: ["future_only"])


def test_als_needs_training_data():
    data = split_events([listen("u", "future", 2)], CUTOFF)
    with pytest.raises(ValueError, match="at least one"):
        fit_als(data)
