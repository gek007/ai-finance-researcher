from ingest.chunking import CHUNK_SIZE_WORDS, chunk_markdown


def test_chunk_markdown_splits_on_paragraphs_and_tracks_section() -> None:
    markdown = """# Risk Factors

First paragraph about market risk and competition in the industry.

Second paragraph describing regulatory exposure and supply chain issues.

# Financial Statements

Revenue increased year over year across all major product segments.
"""

    chunks = chunk_markdown(
        markdown,
        {
            "ticker": "AAPL",
            "accession_number": "0000320193-24-000006",
        },
        chunk_size_words=20,
        chunk_overlap_words=5,
    )

    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert "market risk" in chunks[0].text
    assert chunks[0].metadata["ticker"] == "AAPL"
    assert chunks[0].metadata["section"] == "Risk Factors"
    assert chunks[0].page_label == "Risk Factors"
    assert chunks[0].token_count > 0
    assert "char_start" in chunks[0].metadata
    assert "char_end" in chunks[0].metadata


def test_chunk_markdown_returns_empty_for_blank_input() -> None:
    assert chunk_markdown("", {"ticker": "MSFT"}) == []


def test_chunk_markdown_respects_default_size() -> None:
    words = " ".join(f"word{i}" for i in range(CHUNK_SIZE_WORDS + 50))
    markdown = f"# Overview\n\n{words}"

    chunks = chunk_markdown(markdown, {"ticker": "MSFT"})

    assert len(chunks) >= 2
