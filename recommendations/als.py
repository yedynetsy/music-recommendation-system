"""Sparse implicit-feedback ALS trained only on pre-cutoff listen counts."""

from dataclasses import dataclass

import numpy as np
from implicit.cpu.als import AlternatingLeastSquares
from scipy.sparse import csr_matrix
from threadpoolctl import threadpool_limits

from .evaluation import EvaluationData


@dataclass(frozen=True)
class ALSConfig:
    factors: int = 32
    regularization: float = 0.05
    alpha: float = 10.0
    iterations: int = 10
    threads: int = 2
    seed: int = 42

    def __post_init__(self) -> None:
        if self.factors < 1 or self.iterations < 1 or self.threads < 1:
            raise ValueError("factors, iterations, and threads must be positive")
        if self.regularization <= 0 or self.alpha <= 0:
            raise ValueError("regularization and alpha must be positive")


def training_matrix(data: EvaluationData) -> tuple[csr_matrix, dict[str, int], list[str]]:
    """Build a sparse user-track matrix with log-scaled repeat counts."""
    user_ids = sorted(data.history)
    track_ids = sorted(data.popularity)
    user_index = {user_id: index for index, user_id in enumerate(user_ids)}
    track_index = {track_id: index for index, track_id in enumerate(track_ids)}
    size = len(data.train_counts)
    rows = np.empty(size, dtype=np.int32)
    columns = np.empty(size, dtype=np.int32)
    weights = np.empty(size, dtype=np.float32)
    for position, ((user_id, track_id), count) in enumerate(data.train_counts.items()):
        rows[position] = user_index[user_id]
        columns[position] = track_index[track_id]
        weights[position] = np.log1p(count)
    matrix = csr_matrix((weights, (rows, columns)),
                        shape=(len(user_ids), len(track_ids)), dtype=np.float32)
    matrix.sort_indices()
    return matrix, user_index, track_ids


@dataclass
class ALSRecommender:
    model: AlternatingLeastSquares
    user_items: csr_matrix
    user_index: dict[str, int]
    track_ids: list[str]

    def recommend(self, user_id: str, k: int) -> list[str]:
        if k < 1:
            raise ValueError("k must be positive")
        index = self.user_index[user_id]
        unseen = len(self.track_ids) - self.user_items[index].nnz
        if unseen == 0:
            return []
        with threadpool_limits(limits=1, user_api="blas"):
            item_ids, _ = self.model.recommend(
                index, self.user_items[index], N=min(k, unseen),
                filter_already_liked_items=True,
            )
        return [self.track_ids[item_id] for item_id in item_ids if item_id >= 0]


def fit_als(data: EvaluationData, config: ALSConfig = ALSConfig()) -> ALSRecommender:
    """Fit a fixed-parameter CPU model; absent pairs have confidence one."""
    user_items, user_index, track_ids = training_matrix(data)
    if not user_items.nnz:
        raise ValueError("ALS needs at least one pre-cutoff listen")
    model = AlternatingLeastSquares(
        factors=config.factors, regularization=config.regularization,
        alpha=config.alpha, iterations=config.iterations,
        num_threads=config.threads, random_state=config.seed,
    )
    with threadpool_limits(limits=1, user_api="blas"):
        model.fit(user_items, show_progress=False)
    return ALSRecommender(model, user_items, user_index, track_ids)
