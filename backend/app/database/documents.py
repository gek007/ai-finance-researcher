"""Source document and chunk persistence.

Corpus writes use the service-role Supabase client because RLS only grants
authenticated users SELECT on `source_documents` and `document_chunks`.
SQLAlchemy models describe the schema for Alembic only.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from uuid import UUID

from supabase import Client

CHUNK_INSERT_BATCH_SIZE = 50
PAGE_LABEL_MAX_LENGTH = 128


def _clip_page_label(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:PAGE_LABEL_MAX_LENGTH]


def get_document_by_accession(
    client: Client, accession_number: str
) -> dict[str, Any] | None:
    response = (
        client.table("source_documents")
        .select("*")
        .eq("accession_number", accession_number)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def upsert_document(
    client: Client,
    *,
    ticker: str,
    company_name: str,
    filing_type: str,
    filing_date: date | None,
    fiscal_year: int | None,
    accession_number: str,
    source_url: str | None,
    markdown_content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ticker": ticker,
        "company_name": company_name,
        "filing_type": filing_type,
        "filing_date": filing_date.isoformat() if filing_date else None,
        "fiscal_year": fiscal_year,
        "accession_number": accession_number,
        "source_url": source_url,
        "markdown_content": markdown_content,
        "metadata": metadata or {},
    }

    existing = get_document_by_accession(client, accession_number)
    if existing:
        payload["id"] = existing["id"]
    else:
        payload["id"] = str(uuid.uuid4())

    response = (
        client.table("source_documents")
        .upsert(payload, on_conflict="accession_number")
        .execute()
    )
    return response.data[0]


def replace_document_chunks(
    client: Client,
    document_id: UUID | str,
    chunk_payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    doc_id = str(document_id)
    client.table("document_chunks").delete().eq("document_id", doc_id).execute()

    if not chunk_payloads:
        return []

    payloads = [
        {
            "id": str(uuid.uuid4()),
            "document_id": doc_id,
            "chunk_index": chunk["chunk_index"],
            "text": chunk["text"],
            "page_label": _clip_page_label(chunk.get("page_label")),
            "token_count": chunk.get("token_count"),
            "embedding": chunk["embedding"],
            "metadata": chunk.get("metadata") or {},
        }
        for chunk in chunk_payloads
    ]

    saved: list[dict[str, Any]] = []
    for batch_start in range(0, len(payloads), CHUNK_INSERT_BATCH_SIZE):
        batch = payloads[batch_start : batch_start + CHUNK_INSERT_BATCH_SIZE]
        response = client.table("document_chunks").insert(batch).execute()
        saved.extend(response.data)

    return saved
