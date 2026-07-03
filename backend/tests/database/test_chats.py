import uuid
from unittest.mock import MagicMock

from app.database import chats


def _client_with_data(data):
    """A fake Supabase client where every fluent-builder chain ending in
    `.execute()` returns the given data, regardless of which chain was called.
    """
    client = MagicMock()
    client.table.return_value.select.return_value.order.return_value.execute.return_value.data = data
    client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = data
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = data
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = data
    client.table.return_value.insert.return_value.execute.return_value.data = data
    return client


def test_list_threads_orders_by_updated_at_desc() -> None:
    rows = [{"id": str(uuid.uuid4()), "title": "A"}]
    client = _client_with_data(rows)

    result = chats.list_threads(client)

    assert result == rows
    client.table.assert_called_with("chat_threads")
    client.table.return_value.select.return_value.order.assert_called_with(
        "updated_at", desc=True
    )


def test_create_thread_includes_generated_id_and_owner() -> None:
    user_id = uuid.uuid4()
    client = _client_with_data([{"id": "new-id", "title": "New chat"}])

    chats.create_thread(client, user_id, title="New chat")

    payload = client.table.return_value.insert.call_args[0][0]
    assert payload["user_id"] == str(user_id)
    assert payload["title"] == "New chat"
    assert uuid.UUID(payload["id"])  # generated client-side, must be a valid UUID


def test_get_thread_returns_none_when_missing() -> None:
    client = _client_with_data(None)

    result = chats.get_thread(client, uuid.uuid4())

    assert result is None


def test_get_thread_returns_row_when_found() -> None:
    thread_id = uuid.uuid4()
    row = {"id": str(thread_id), "title": "New chat"}
    client = _client_with_data(row)

    result = chats.get_thread(client, thread_id)

    assert result == row


def test_append_message_uses_next_sort_order_and_generates_id() -> None:
    thread_id = uuid.uuid4()
    client = _client_with_data(
        [{"sort_order": 2}]
    )  # existing max sort_order in the thread
    client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "row-1"}
    ]

    chats.append_message(client, thread_id, role="user", content="hi")

    payload = client.table.return_value.insert.call_args[0][0]
    assert payload["thread_id"] == str(thread_id)
    assert payload["sort_order"] == 3
    assert payload["content"] == "hi"
    assert uuid.UUID(payload["id"])


def test_append_message_uses_provided_message_id() -> None:
    thread_id = uuid.uuid4()
    message_id = uuid.uuid4()
    client = _client_with_data([])  # no prior messages -> sort_order 0
    client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": str(message_id)}
    ]

    chats.append_message(
        client,
        thread_id,
        role="assistant",
        content="stub reply",
        message_id=message_id,
    )

    payload = client.table.return_value.insert.call_args[0][0]
    assert payload["id"] == str(message_id)
    assert payload["sort_order"] == 0


def test_touch_thread_updates_timestamp() -> None:
    thread_id = uuid.uuid4()
    client = MagicMock()

    chats.touch_thread(client, thread_id)

    client.table.assert_called_with("chat_threads")
    update_call = client.table.return_value.update.call_args[0][0]
    assert "updated_at" in update_call
    client.table.return_value.update.return_value.eq.assert_called_with(
        "id", str(thread_id)
    )
