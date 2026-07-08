from unittest.mock import MagicMock, patch

from ingest.embeddings import _batch_texts, embed_texts


def test_batch_texts_splits_on_token_limit() -> None:
    texts = ["x" * 1_000_000, "small"]

    batches = _batch_texts(texts)

    assert len(batches) == 2
    assert batches[0] == ["x" * 1_000_000]
    assert batches[1] == ["small"]


def test_batch_texts_splits_on_item_limit() -> None:
    texts = ["a"] * 100

    batches = _batch_texts(texts)

    assert len(batches) == 2
    assert len(batches[0]) == 64
    assert len(batches[1]) == 36


def test_embed_texts_calls_openai_per_batch() -> None:
    client = MagicMock()
    client.embeddings.create.side_effect = [
        MagicMock(data=[MagicMock(embedding=[0.1])]),
        MagicMock(data=[MagicMock(embedding=[0.2])]),
    ]

    with patch("ingest.embeddings._batch_texts", return_value=[["one"], ["two"]]):
        vectors = embed_texts(["one", "two"], client=client)

    assert vectors == [[0.1], [0.2]]
    assert client.embeddings.create.call_count == 2
