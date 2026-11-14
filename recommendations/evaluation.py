"""Global temporal holdout and popularity baseline."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import log2
from typing import Callable, Iterable

from .lastfm import Listen


@dataclass(frozen=True)
class Evaluation:
    users: int
    cold_users: int
    users_without_targets: int
    recall: float
    ndcg: float


@dataclass(frozen=True)
class EvaluationData:
    train_counts: Counter[tuple[str, str]]
    popularity: Counter[str]
    history: dict[str, set[str]]
    future: dict[str, set[str]]


def recall_at_k(ranked: Iterable[str], relevant: set[str], k: int) -> float:
    if k < 1 or not relevant:
        raise ValueError("k and relevant must be nonempty")
    return len(set(list(ranked)[:k]) & relevant) / len(relevant)


def ndcg_at_k(ranked: Iterable[str], relevant: set[str], k: int) -> float:
    if k < 1 or not relevant:
        raise ValueError("k and relevant must be nonempty")
    seen: set[str] = set()
    dcg = 0.0
    for rank, track_id in enumerate(list(ranked)[:k], 1):
        if track_id in relevant and track_id not in seen:
            dcg += 1 / log2(rank + 1)
        seen.add(track_id)
    ideal = sum(1 / log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
    return dcg / ideal


def split_events(events: Iterable[Listen], cutoff: datetime) -> EvaluationData:
    """Collect only pre-cutoff training signals and distinct holdout targets."""
    if cutoff.tzinfo is None:
        raise ValueError("cutoff must have a timezone")
    train_counts: Counter[tuple[str, str]] = Counter()
    popularity: Counter[str] = Counter()
    history: dict[str, set[str]] = defaultdict(set)
    future: dict[str, set[str]] = defaultdict(set)
    for event in events:
        if not event.track_id:
            continue
        if event.timestamp < cutoff:
            train_counts[event.user_id, event.track_id] += 1
            popularity[event.track_id] += 1
            history[event.user_id].add(event.track_id)
        else:
            future[event.user_id].add(event.track_id)
    return EvaluationData(train_counts, popularity, dict(history), dict(future))


def evaluate_rankings(data: EvaluationData, k: int,
                      recommend: Callable[[str, int], Iterable[str]]) -> Evaluation:
    """Score a ranker on the shared new-to-user, known-catalog task."""
    if k < 1:
        raise ValueError("k must be positive")
    catalog = set(data.popularity)
    recalls: list[float] = []
    ndcgs: list[float] = []
    cold_users = 0
    users_without_targets = 0
    for user_id, future_tracks in data.future.items():
        if user_id not in data.history:
            cold_users += 1
            continue
        relevant = (future_tracks & catalog) - data.history[user_id]
        if not relevant:
            users_without_targets += 1
            continue
        recommendations = list(recommend(user_id, k))[:k]
        if any(track_id not in catalog or track_id in data.history[user_id]
               for track_id in recommendations):
            raise ValueError("ranker returned a track outside the candidate set")
        recalls.append(recall_at_k(recommendations, relevant, k))
        ndcgs.append(ndcg_at_k(recommendations, relevant, k))
    return Evaluation(
        users=len(recalls), cold_users=cold_users,
        users_without_targets=users_without_targets,
        recall=sum(recalls) / len(recalls) if recalls else 0.0,
        ndcg=sum(ndcgs) / len(ndcgs) if ndcgs else 0.0,
    )


def evaluate_popularity_data(data: EvaluationData, k: int = 10) -> Evaluation:
    """Rank pre-cutoff tracks by event count for every warm user."""
    catalog = set(data.popularity)
    ranked_catalog = sorted(catalog, key=lambda track_id: (-data.popularity[track_id], track_id))

    def recommend(user_id: str, limit: int) -> list[str]:
        return [track_id for track_id in ranked_catalog
                if track_id not in data.history[user_id]][:limit]

    return evaluate_rankings(data, k, recommend)


def evaluate_popularity(events: Iterable[Listen], cutoff: datetime, k: int = 10) -> Evaluation:
    """Evaluate popularity using the global pre-cutoff training catalog."""
    return evaluate_popularity_data(split_events(events, cutoff), k)
