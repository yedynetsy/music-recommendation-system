"""Global temporal holdout and popularity baseline."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import log2
from typing import Iterable

from .lastfm import Listen


@dataclass(frozen=True)
class Evaluation:
    users: int
    cold_users: int
    users_without_targets: int
    recall: float
    ndcg: float


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


def evaluate_popularity(events: Iterable[Listen], cutoff: datetime, k: int = 10) -> Evaluation:
    """Evaluate new-to-user tracks using only pre-cutoff catalog and counts."""
    if cutoff.tzinfo is None or k < 1:
        raise ValueError("cutoff must have a timezone and k must be positive")
    popularity: Counter[str] = Counter()
    history: dict[str, set[str]] = defaultdict(set)
    future: dict[str, set[str]] = defaultdict(set)
    for event in events:
        if not event.track_id:
            continue
        if event.timestamp < cutoff:
            popularity[event.track_id] += 1
            history[event.user_id].add(event.track_id)
        else:
            future[event.user_id].add(event.track_id)

    catalog = set(popularity)
    ranked_catalog = sorted(catalog, key=lambda track_id: (-popularity[track_id], track_id))
    recalls: list[float] = []
    ndcgs: list[float] = []
    cold_users = 0
    users_without_targets = 0
    for user_id, future_tracks in future.items():
        if user_id not in history:
            cold_users += 1
            continue
        candidates = catalog - history[user_id]
        relevant = future_tracks & candidates
        if not relevant:
            users_without_targets += 1
            continue
        recommendations = [track_id for track_id in ranked_catalog if track_id in candidates][:k]
        recalls.append(recall_at_k(recommendations, relevant, k))
        ndcgs.append(ndcg_at_k(recommendations, relevant, k))
    return Evaluation(
        users=len(recalls), cold_users=cold_users,
        users_without_targets=users_without_targets,
        recall=sum(recalls) / len(recalls) if recalls else 0.0,
        ndcg=sum(ndcgs) / len(ndcgs) if ndcgs else 0.0,
    )
