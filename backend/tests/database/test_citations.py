import uuid
from unittest.mock import MagicMock

from app.database import chats


def test_append_citations_inserts_indexed_rows() -> None:
    message_id = uuid.uuid4()
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "c1"},
        {"id": "c2"},
    ]

    result = chats.append_citations(
        client,
        message_id,
        [
            {"chunk_id": "chunk-1", "quote": "Revenue grew"},
            {"chunk_id": "chunk-2", "quote": None},
        ],
    )

    assert result == [{"id": "c1"}, {"id": "c2"}]
    client.table.assert_called_with("message_citations")
    payloads = client.table.return_value.insert.call_args[0][0]
    assert payloads[0]["message_id"] == str(message_id)
    assert payloads[0]["chunk_id"] == "chunk-1"
    assert payloads[0]["citation_index"] == 0
    assert payloads[0]["quote"] == "Revenue grew"
    assert payloads[1]["citation_index"] == 1
    assert uuid.UUID(payloads[0]["id"])
    assert uuid.UUID(payloads[1]["id"])


def test_append_citations_returns_empty_for_no_citations() -> None:
    client = MagicMock()

    assert chats.append_citations(client, uuid.uuid4(), []) == []
    client.table.assert_not_called()
