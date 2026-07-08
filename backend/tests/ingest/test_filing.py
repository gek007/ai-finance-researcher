from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from ingest.filing import ingest_filing
from ingest.manifest import FilingRecord


def test_ingest_filing_chunks_embeds_and_persists(tmp_path: Path) -> None:
    markdown_path = tmp_path / "filing.md"
    markdown_path.write_text(
        "# Risk Factors\n\nMarket risk paragraph.\n\nAnother risk paragraph.\n",
        encoding="utf-8",
    )
    record = FilingRecord(
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2024, 11, 1),
        fiscal_year=2024,
        accession_number="0000320193-24-000123",
        source_url="https://example.com",
        markdown_path=markdown_path,
        metadata={"cik": "0000320193"},
    )
    client = MagicMock()

    with (
        patch("ingest.filing.embed_texts", return_value=[[0.1, 0.2]]),
        patch(
            "ingest.filing.document_db.upsert_document",
            return_value={"id": "doc-1"},
        ) as upsert_mock,
        patch(
            "ingest.filing.document_db.replace_document_chunks",
            return_value=[{"id": "chunk-1"}],
        ) as replace_mock,
    ):
        result = ingest_filing(client, record)

    assert result == {"chunks": 1, "document_id": "doc-1"}
    upsert_mock.assert_called_once()
    replace_mock.assert_called_once()
    chunk_payloads = replace_mock.call_args[0][2]
    assert chunk_payloads[0]["text"]
    assert chunk_payloads[0]["embedding"] == [0.1, 0.2]
