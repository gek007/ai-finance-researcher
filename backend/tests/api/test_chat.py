import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_module
from app.auth.dependencies import CurrentUser, get_current_user
from app.main import app

USER_ID = uuid.uuid4()
NOW = datetime.now(UTC).isoformat()


def _thread_row(thread_id: uuid.UUID | None = None, title: str = "New chat") -> dict:
    return {
        "id": str(thread_id or uuid.uuid4()),
        "title": title,
        "created_at": NOW,
        "updated_at": NOW,
    }


def _message_row(role: str, content: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "message_json": None,
        "created_at": NOW,
    }


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=USER_ID, email="analyst@driftwood.test", access_token="fake-token"
    )
    monkeypatch.setattr(chat_module, "get_user_client", lambda token: object())
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_list_threads_returns_serialized_rows(client, monkeypatch) -> None:
    rows = [_thread_row(), _thread_row()]
    monkeypatch.setattr(chat_module.chats, "list_threads", lambda c: rows)

    response = client.get("/chat/threads")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_create_thread_returns_created_thread(client, monkeypatch) -> None:
    row = _thread_row(title="Apple 10-K questions")
    monkeypatch.setattr(
        chat_module.chats, "create_thread", lambda c, user_id, title: row
    )

    response = client.post("/chat/threads", json={"title": "Apple 10-K questions"})

    assert response.status_code == 201
    assert response.json()["title"] == "Apple 10-K questions"


def test_get_thread_returns_404_when_not_found_or_not_owned(client, monkeypatch) -> None:
    monkeypatch.setattr(chat_module.chats, "get_thread", lambda c, thread_id: None)

    response = client.get(f"/chat/threads/{uuid.uuid4()}")

    assert response.status_code == 404


def test_get_thread_returns_thread_with_messages(client, monkeypatch) -> None:
    thread_id = uuid.uuid4()
    row = _thread_row(thread_id)
    messages = [_message_row("user", "Hi"), _message_row("assistant", "Hello")]
    monkeypatch.setattr(chat_module.chats, "get_thread", lambda c, tid: row)
    monkeypatch.setattr(chat_module.chats, "list_messages", lambda c, tid: messages)

    response = client.get(f"/chat/threads/{thread_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["thread"]["id"] == str(thread_id)
    assert len(body["messages"]) == 2


def test_stream_returns_404_for_unowned_thread(client, monkeypatch) -> None:
    monkeypatch.setattr(chat_module.chats, "get_thread", lambda c, tid: None)

    response = client.post(
        "/chat/stream",
        json={
            "threadId": str(uuid.uuid4()),
            "messages": [
                {"id": "msg_1", "role": "user", "parts": [{"type": "text", "text": "Hi"}]}
            ],
        },
    )

    assert response.status_code == 404


def test_stream_returns_422_when_last_message_is_not_from_user(
    client, monkeypatch
) -> None:
    thread_id = uuid.uuid4()
    monkeypatch.setattr(
        chat_module.chats, "get_thread", lambda c, tid: _thread_row(thread_id)
    )

    response = client.post(
        "/chat/stream",
        json={
            "threadId": str(thread_id),
            "messages": [
                {
                    "id": "msg_1",
                    "role": "assistant",
                    "parts": [{"type": "text", "text": "Hi"}],
                }
            ],
        },
    )

    assert response.status_code == 422


def test_stream_returns_ui_message_stream_response(client, monkeypatch) -> None:
    thread_id = uuid.uuid4()
    monkeypatch.setattr(
        chat_module.chats, "get_thread", lambda c, tid: _thread_row(thread_id)
    )
    monkeypatch.setattr(
        chat_module.chats, "append_message", lambda *args, **kwargs: _message_row(
            kwargs.get("role", "user"), kwargs.get("content", "")
        )
    )
    monkeypatch.setattr(chat_module.chats, "touch_thread", lambda *args, **kwargs: None)

    response = client.post(
        "/chat/stream",
        json={
            "threadId": str(thread_id),
            "messages": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "parts": [{"type": "text", "text": "What was AAPL revenue?"}],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert "text/event-stream" in response.headers["content-type"]
    assert "data: [DONE]" in response.text
