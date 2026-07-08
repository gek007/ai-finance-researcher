import uuid
from datetime import date
from unittest.mock import MagicMock

from app.database import documents


def _client_with_select(data):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = data
    return client


def test_upsert_document_generates_id_for_new_filing() -> None:
    client = _client_with_select(None)
    client.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": "doc-1", "accession_number": "0000320193-24-000123"}
    ]

    documents.upsert_document(
        client,
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2024, 11, 1),
        fiscal_year=2024,
        accession_number="0000320193-24-000123",
        source_url="https://example.com",
        markdown_content="# Filing",
        metadata={"cik": "0000320193"},
    )

    payload = client.table.return_value.upsert.call_args[0][0]
    assert payload["ticker"] == "AAPL"
    assert payload["filing_date"] == "2024-11-01"
    assert payload["metadata"] == {"cik": "0000320193"}
    uuid.UUID(payload["id"])
    client.table.return_value.upsert.assert_called_with(
        payload, on_conflict="accession_number"
    )


def test_upsert_document_reuses_existing_id() -> None:
    existing_id = str(uuid.uuid4())
    client = _client_with_select({"id": existing_id})
    client.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": existing_id}
    ]

    documents.upsert_document(
        client,
        ticker="MSFT",
        company_name="Microsoft Corporation",
        filing_type="10-K",
        filing_date=None,
        fiscal_year=2024,
        accession_number="0000789019-24-000001",
        source_url=None,
        markdown_content="content",
    )

    payload = client.table.return_value.upsert.call_args[0][0]
    assert payload["id"] == existing_id


def test_replace_document_chunks_deletes_then_inserts() -> None:
    document_id = uuid.uuid4()
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "chunk-1"}
    ]

    chunk_payloads = [
        {
            "chunk_index": 0,
            "text": "Revenue grew.",
            "page_label": "Overview",
            "token_count": 2,
            "metadata": {"ticker": "AAPL"},
            "embedding": [0.1, 0.2],
        }
    ]

    documents.replace_document_chunks(client, document_id, chunk_payloads)

    client.table.return_value.delete.return_value.eq.assert_called_with(
        "document_id", str(document_id)
    )
    insert_payload = client.table.return_value.insert.call_args[0][0]
    assert insert_payload[0]["document_id"] == str(document_id)
    assert insert_payload[0]["chunk_index"] == 0
    assert insert_payload[0]["embedding"] == [0.1, 0.2]
    uuid.UUID(insert_payload[0]["id"])


def test_replace_document_chunks_inserts_in_batches() -> None:
    document_id = uuid.uuid4()
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "chunk-1"}
    ]

    chunk_payloads = [
        {
            "chunk_index": index,
            "text": f"chunk {index}",
            "page_label": None,
            "token_count": 1,
            "metadata": {},
            "embedding": [0.1],
        }
        for index in range(3)
    ]

    original_batch_size = documents.CHUNK_INSERT_BATCH_SIZE
    documents.CHUNK_INSERT_BATCH_SIZE = 2
    try:
        documents.replace_document_chunks(client, document_id, chunk_payloads)
    finally:
        documents.CHUNK_INSERT_BATCH_SIZE = original_batch_size

    assert client.table.return_value.insert.return_value.execute.call_count == 2
    first_batch = client.table.return_value.insert.call_args_list[0][0][0]
    second_batch = client.table.return_value.insert.call_args_list[1][0][0]
    assert len(first_batch) == 2
    assert len(second_batch) == 1


def test_replace_document_chunks_truncates_long_page_label() -> None:
    document_id = uuid.uuid4()
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "chunk-1"}
    ]

    long_label = "x" * 200
    documents.replace_document_chunks(
        client,
        document_id,
        [
            {
                "chunk_index": 0,
                "text": "text",
                "page_label": long_label,
                "token_count": 1,
                "metadata": {},
                "embedding": [0.1],
            }
        ],
    )

    insert_payload = client.table.return_value.insert.call_args[0][0]
    assert len(insert_payload[0]["page_label"]) == documents.PAGE_LABEL_MAX_LENGTH
