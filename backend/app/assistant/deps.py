"""Request-scoped dependencies for the document assistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.retrieval.retriever import SourcePassage

RetrievePassages = Callable[[str], list[SourcePassage]]
ReadChunk = Callable[[str], SourcePassage | None]
ReadSurroundingChunks = Callable[[str, int, int], list[SourcePassage]]


@dataclass
class DocumentAgentDeps:
    user_id: str
    thread_id: str
    retrieve_passages: RetrievePassages
    read_chunk: ReadChunk
    read_surrounding_chunks: ReadSurroundingChunks
    known_passages: dict[str, SourcePassage] = field(default_factory=dict)

    def remember(self, passages: list[SourcePassage]) -> list[SourcePassage]:
        for passage in passages:
            self.known_passages[passage.chunk_id] = passage
        return passages
