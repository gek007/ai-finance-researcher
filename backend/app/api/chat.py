from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from supabase import Client

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.messages import UIMessage
from app.chat.orchestrator import stream_grounded_reply
from app.chat.streaming import STREAM_HEADERS
from app.database import chats
from app.database.supabase import get_user_client

router = APIRouter(prefix="/chat", tags=["chat"])


class ThreadResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class CreateThreadRequest(BaseModel):
    title: str = chats.DEFAULT_THREAD_TITLE


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    message_json: dict | None
    created_at: datetime


class ThreadDetailResponse(BaseModel):
    thread: ThreadResponse
    messages: list[MessageResponse]


class ChatStreamRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thread_id: UUID = Field(alias="threadId")
    messages: list[UIMessage]


async def _get_owned_thread(client: Client, thread_id: UUID) -> dict:
    thread = await run_in_threadpool(chats.get_thread, client, thread_id)
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )
    return thread


@router.get("/threads")
async def list_threads(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ThreadResponse]:
    client = get_user_client(current_user.access_token)
    threads = await run_in_threadpool(chats.list_threads, client)
    return [ThreadResponse.model_validate(thread) for thread in threads]


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def create_thread(
    payload: CreateThreadRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ThreadResponse:
    client = get_user_client(current_user.access_token)
    thread = await run_in_threadpool(
        chats.create_thread, client, current_user.id, payload.title
    )
    return ThreadResponse.model_validate(thread)


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> ThreadDetailResponse:
    client = get_user_client(current_user.access_token)
    thread = await _get_owned_thread(client, thread_id)
    messages = await run_in_threadpool(chats.list_messages, client, thread_id)
    return ThreadDetailResponse(
        thread=ThreadResponse.model_validate(thread),
        messages=[MessageResponse.model_validate(message) for message in messages],
    )


@router.post("/stream")
async def stream_chat(
    payload: ChatStreamRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    client = get_user_client(current_user.access_token)
    await _get_owned_thread(client, payload.thread_id)

    if not payload.messages or payload.messages[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The last message must be from the user",
        )

    return StreamingResponse(
        stream_grounded_reply(
            client,
            current_user.id,
            payload.thread_id,
            payload.messages[-1],
        ),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )
