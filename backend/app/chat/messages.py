"""Conversion between the AI SDK's UI message wire format and our storage shape.

`UIMessage` mirrors what the AI SDK's `useChat` sends/expects: a message id, a
role, and a list of typed parts (text, tool calls, sources, ...). We only need
to read `text` parts today; other part types round-trip untouched inside
`message_json` on the stored `ChatMessage` row via `model_dump()`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UIMessagePart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    text: str | None = None


class UIMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    role: Literal["user", "assistant", "system"]
    parts: list[UIMessagePart] = Field(default_factory=list)


def extract_text(message: UIMessage) -> str:
    return "".join(part.text or "" for part in message.parts if part.type == "text")
