"""Rank fusion for hybrid search results."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")
RRF_K = 60


@dataclass(frozen=True)
class FusedResult[T]:
    item: T
    score: float


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[T]],
    *,
    key: Callable[[T], Hashable],
    limit: int,
    k: int = RRF_K,
) -> list[FusedResult[T]]:
    items: dict[Hashable, T] = {}
    scores: dict[Hashable, float] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            item_key = key(item)
            items.setdefault(item_key, item)
            scores[item_key] = scores.get(item_key, 0.0) + 1 / (k + rank)

    ranked = sorted(scores.items(), key=lambda entry: entry[1], reverse=True)
    return [
        FusedResult(item=items[item_key], score=score)
        for item_key, score in ranked[:limit]
    ]
