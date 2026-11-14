from datetime import datetime, timezone

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from recommendations.als import ALSConfig, fit_als
from recommendations.evaluation import split_events
from recommendations.lastfm import Listen
from recommendations.serving import ServingModel, save_artifact


CUTOFF = datetime(2009, 1, 2, tzinfo=timezone.utc)


def listen(user: str, track: str, day: int = 1) -> Listen:
    return Listen(user, datetime(2009, 1, day, tzinfo=timezone.utc),
                  track, "artist", "Artist", track)


def test_exported_artifact_supports_new_user_inference_without_user_ids(tmp_path):
    data = split_events([
        listen("historical_a", "a"), listen("historical_a", "a"),
        listen("historical_b", "a"), listen("historical_b", "b"),
        listen("historical_c", "b"), listen("historical_c", "c"),
        listen("historical_a", "future", 2),
    ], CUTOFF)
    config = ALSConfig(factors=3, iterations=2, threads=1, seed=7)
    trained = fit_als(data, config)
    artifact_path = tmp_path / "model.npz"
    version = save_artifact(artifact_path, trained, data, CUTOFF, config, "a" * 64)
    with np.load(artifact_path, allow_pickle=False) as artifact:
        assert not any("user" in key for key in artifact.files)
        assert artifact["track_ids"].tolist() == ["a", "b", "c"]
    serving = ServingModel.load(artifact_path)
    assert serving.model_version == version
    assert serving.infer_user_factor({}) is None
    assert serving.rank({}, 2) == ("popularity", ["a", "b"])
    assert serving.rank({"a": 2}, 3)[0] == "als"
    assert "a" not in serving.rank({"a": 2}, 3)[1]
    assert serving.rank({"unknown": 1}, 2)[0] == "popularity"

    row = csr_matrix((np.array([np.log1p(2)], dtype=np.float32),
                      ([0], [trained.track_ids.index("a")])),
                     shape=(1, len(trained.track_ids)))
    expected = trained.model.recalculate_user(0, row)
    np.testing.assert_allclose(serving.infer_user_factor({"a": 2}), expected,
                               rtol=1e-4, atol=1e-5)
    trained.model.item_factors[0, 0] += 0.1
    changed_version = save_artifact(tmp_path / "changed.npz", trained, data,
                                    CUTOFF, config, "a" * 64)
    assert changed_version != version


def test_artifact_rejects_wrong_version_and_duplicate_ids(tmp_path):
    model = ServingModel(["a"], np.array([[1.0]], dtype=np.float32),
                         np.array([1]), 10.0, 0.05, "v1", CUTOFF.isoformat())
    assert model.rank({}, 1) == ("popularity", ["a"])
    with pytest.raises(ValueError, match="unique"):
        ServingModel(["a", "a"], np.ones((2, 1)), np.ones(2),
                     10.0, 0.05, "v1", CUTOFF.isoformat())
    wrong = tmp_path / "wrong.npz"
    np.savez(wrong, format_version=np.array(99))
    with pytest.raises(ValueError, match="unsupported"):
        ServingModel.load(wrong)
