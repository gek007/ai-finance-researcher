from app.chat.messages import UIMessage, extract_text


def test_extract_text_joins_text_parts_only() -> None:
    message = UIMessage.model_validate(
        {
            "id": "msg_1",
            "role": "user",
            "parts": [
                {"type": "text", "text": "Hello "},
                {"type": "tool-call", "toolName": "search_filings"},
                {"type": "text", "text": "world"},
            ],
        }
    )

    assert extract_text(message) == "Hello world"


def test_extract_text_returns_empty_string_when_no_parts() -> None:
    message = UIMessage.model_validate({"id": "msg_1", "role": "user", "parts": []})

    assert extract_text(message) == ""
