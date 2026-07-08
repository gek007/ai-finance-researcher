"""OpenAI embedding generation for document chunks."""

from __future__ import annotations

from openai import OpenAI

from app.config import settings

MAX_BATCH_ITEMS = 64
MAX_TOKENS_PER_REQUEST = 250_000


def _estimate_tokens(text: str) -> int:
    return max(len(text) // 4, 1)


def _batch_texts(texts: list[str]) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0

    for text in texts:
        tokens = _estimate_tokens(text)
        if current and (
            len(current) >= MAX_BATCH_ITEMS
            or current_tokens + tokens > MAX_TOKENS_PER_REQUEST
        ):
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(text)
        current_tokens += tokens

    if current:
        batches.append(current)

    return batches


def embed_texts(texts: list[str], client: OpenAI | None = None) -> list[list[float]]:
    if not texts:
        return []

    openai_client = client or OpenAI(api_key=settings.openai_api_key)
    vectors: list[list[float]] = []

    for batch in _batch_texts(texts):
        response = openai_client.embeddings.create(
            model=settings.openai_embedding_model,
            input=batch,
            dimensions=settings.openai_embedding_dimensions,
        )
        vectors.extend(item.embedding for item in response.data)

    return vectors
