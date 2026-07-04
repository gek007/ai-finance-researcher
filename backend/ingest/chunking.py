"""Paragraph-aware Markdown chunking for SEC filings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CHUNK_SIZE_WORDS = 400
CHUNK_OVERLAP_WORDS = 50

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


@dataclass(frozen=True)
class ChunkDraft:
    chunk_index: int
    text: str
    page_label: str | None
    token_count: int
    metadata: dict[str, Any]


def chunk_markdown(
    markdown: str,
    filing_metadata: dict[str, Any],
    *,
    chunk_size_words: int = CHUNK_SIZE_WORDS,
    chunk_overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[ChunkDraft]:
    """Split Markdown into overlapping chunks while preserving paragraph boundaries."""
    segments = _segment_markdown(markdown)
    segments = _split_oversized_segments(segments, chunk_size_words)
    if not segments:
        return []

    chunks: list[ChunkDraft] = []
    buffer: list[_Segment] = []
    buffer_words = 0
    char_offset = 0

    def flush() -> None:
        nonlocal buffer, buffer_words, char_offset
        if not buffer:
            return

        text = "\n\n".join(segment.text for segment in buffer)
        section = _dominant_section(buffer)
        start_offset = buffer[0].char_start
        end_offset = buffer[-1].char_end
        metadata = {
            **filing_metadata,
            "section": section,
            "char_start": start_offset,
            "char_end": end_offset,
        }
        chunks.append(
            ChunkDraft(
                chunk_index=len(chunks),
                text=text,
                page_label=section,
                token_count=_word_count(text),
                metadata=metadata,
            )
        )

        if chunk_overlap_words <= 0:
            buffer = []
            buffer_words = 0
            return

        overlap: list[_Segment] = []
        overlap_words = 0
        for segment in reversed(buffer):
            overlap.insert(0, segment)
            overlap_words += segment.word_count
            if overlap_words >= chunk_overlap_words:
                break

        buffer = overlap
        buffer_words = sum(segment.word_count for segment in buffer)
        char_offset = buffer[0].char_start if buffer else end_offset

    for segment in segments:
        if buffer_words + segment.word_count > chunk_size_words and buffer:
            flush()

        buffer.append(segment)
        buffer_words += segment.word_count
        char_offset = segment.char_end

        if buffer_words >= chunk_size_words:
            flush()

    flush()
    return chunks


@dataclass(frozen=True)
class _Segment:
    text: str
    section: str | None
    char_start: int
    char_end: int
    word_count: int


def _segment_markdown(markdown: str) -> list[_Segment]:
    segments: list[_Segment] = []
    current_section: str | None = None
    cursor = 0

    for block in re.split(r"\n\s*\n", markdown.strip()):
        if not block.strip():
            continue

        section = current_section
        body = block
        for line in block.splitlines():
            match = _HEADING_RE.match(line.strip())
            if match:
                current_section = match.group(2).strip()
                section = current_section
                body = block
                break

        char_start = markdown.find(block, cursor)
        if char_start < 0:
            char_start = cursor
        char_end = char_start + len(block)
        cursor = char_end

        segments.append(
            _Segment(
                text=body.strip(),
                section=section,
                char_start=char_start,
                char_end=char_end,
                word_count=_word_count(body),
            )
        )

    return segments


def _split_oversized_segments(
    segments: list[_Segment], max_words: int
) -> list[_Segment]:
    expanded: list[_Segment] = []
    for segment in segments:
        words = segment.text.split()
        if len(words) <= max_words:
            expanded.append(segment)
            continue

        for start in range(0, len(words), max_words):
            piece = words[start : start + max_words]
            text = " ".join(piece)
            expanded.append(
                _Segment(
                    text=text,
                    section=segment.section,
                    char_start=segment.char_start,
                    char_end=segment.char_start + len(text),
                    word_count=len(piece),
                )
            )
    return expanded


def _dominant_section(segments: list[_Segment]) -> str | None:
    for segment in reversed(segments):
        if segment.section:
            return segment.section
    return None


def _word_count(text: str) -> int:
    return len(text.split())
