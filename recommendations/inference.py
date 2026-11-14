"""New-user inference and item similarity using fixed ALS item factors."""

from dataclasses import dataclass
from typing import Mapping
import numpy as np
from threadpoolctl import threadpool_limits


@dataclass
class ServingModel:
    track_ids: list[str]
    item_factors: np.ndarray
    popularity: np.ndarray
    alpha: float
    regularization: float
    model_version: str
    cutoff: str

    def __post_init__(self) -> None:
        if not self.track_ids or len(self.track_ids) != len(set(self.track_ids)):
            raise ValueError("artifact needs unique track IDs")
        if self.item_factors.ndim != 2 or self.item_factors.shape[0] != len(self.track_ids):
            raise ValueError("artifact has mismatched item factors")
        if self.popularity.shape != (len(self.track_ids),):
            raise ValueError("artifact has mismatched popularity")
        if self.alpha <= 0 or self.regularization <= 0 or not np.isfinite(self.item_factors).all():
            raise ValueError("artifact contains invalid factors or parameters")
        self.track_index = {track_id: index for index, track_id in enumerate(self.track_ids)}
        factors = self.item_factors.astype(np.float64)
        self.gram = factors.T @ factors
        self.item_norms = np.linalg.norm(self.item_factors, axis=1)
        self.popular_order = np.lexsort((np.asarray(self.track_ids), -self.popularity))

    def infer_user_factor(self, listens: Mapping[str, int]) -> np.ndarray | None:
        """Solve one new profile from app listens using fixed item factors."""
        known = {self.track_index[track_id]: count for track_id, count in listens.items()
                 if count > 0 and track_id in self.track_index}
        if not known:
            return None
        matrix = self.gram.copy()
        matrix.flat[::matrix.shape[0] + 1] += self.regularization
        vector = np.zeros(matrix.shape[0], dtype=np.float64)
        for item_index, count in known.items():
            confidence = self.alpha * np.log1p(count)
            factor = self.item_factors[item_index].astype(np.float64)
            matrix += (confidence - 1) * np.outer(factor, factor)
            vector += confidence * factor
        return np.linalg.solve(matrix, vector)

    def rank(self, listens: Mapping[str, int], k: int) -> tuple[str, list[str]]:
        """Use an inferred user factor, or popularity with no known listens."""
        if k < 1:
            raise ValueError("k must be positive")
        known = {self.track_index[track_id] for track_id, count in listens.items()
                 if count > 0 and track_id in self.track_index}
        if not known:
            return "popularity", [self.track_ids[index] for index in self.popular_order[:k]]
        user_factor = self.infer_user_factor(listens)
        assert user_factor is not None
        with threadpool_limits(limits=1, user_api="blas"):
            scores = self.item_factors @ user_factor.astype(np.float32)
        scores[list(known)] = -np.inf
        order = np.argsort(-scores, kind="stable")[:min(k, len(self.track_ids) - len(known))]
        return "als", [self.track_ids[index] for index in order]

    def similar_tracks(self, track_id: str, k: int) -> list[str]:
        """Rank known tracks by cosine similarity of their ALS item factors."""
        if k < 1:
            raise ValueError("k must be positive")
        index = self.track_index.get(track_id)
        if index is None:
            raise KeyError(track_id)
        seed_norm = self.item_norms[index]
        if seed_norm == 0:
            return []
        with threadpool_limits(limits=1, user_api="blas"):
            scores = self.item_factors @ self.item_factors[index]
        valid = (self.item_norms > 0)
        valid[index] = False
        candidates = np.flatnonzero(valid)
        similarity = scores[candidates] / (self.item_norms[candidates] * seed_norm)
        order = np.lexsort((np.asarray(self.track_ids)[candidates], -similarity))
        return [self.track_ids[candidates[position]] for position in order[:k]]
