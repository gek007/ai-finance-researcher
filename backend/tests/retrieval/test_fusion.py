from dataclasses import dataclass

from app.retrieval.fusion import reciprocal_rank_fusion


@dataclass(frozen=True)
class Hit:
    chunk_id: str


def test_reciprocal_rank_fusion_boosts_hits_seen_in_multiple_lists() -> None:
    fused = reciprocal_rank_fusion(
        [
            [Hit("a"), Hit("b")],
            [Hit("b"), Hit("c")],
        ],
        key=lambda hit: hit.chunk_id,
        limit=3,
    )

    assert [result.item.chunk_id for result in fused] == ["b", "a", "c"]
    assert fused[0].score > fused[1].score


def test_reciprocal_rank_fusion_respects_limit() -> None:
    fused = reciprocal_rank_fusion(
        [[Hit("a"), Hit("b"), Hit("c")]],
        key=lambda hit: hit.chunk_id,
        limit=2,
    )

    assert [result.item.chunk_id for result in fused] == ["a", "b"]
