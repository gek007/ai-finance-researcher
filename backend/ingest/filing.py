"""Ingest a single filing: chunk, embed, and persist."""

from __future__ import annotations

from supabase import Client

from app.database import documents as document_db
from ingest.chunking import chunk_markdown
from ingest.embeddings import embed_texts
from ingest.manifest import FilingRecord


def ingest_filing(client: Client, record: FilingRecord) -> dict[str, int | str]:
    if not record.markdown_path.is_file():
        raise FileNotFoundError(f"Markdown not found: {record.markdown_path}")

    markdown = record.markdown_path.read_text(encoding="utf-8")
    filing_metadata = {
        "ticker": record.ticker,
        "company_name": record.company_name,
        "filing_type": record.filing_type,
        "filing_date": record.filing_date.isoformat() if record.filing_date else None,
        "fiscal_year": record.fiscal_year,
        "accession_number": record.accession_number,
    }

    chunks = chunk_markdown(markdown, filing_metadata)
    embeddings = embed_texts([chunk.text for chunk in chunks])

    document = document_db.upsert_document(
        client,
        ticker=record.ticker,
        company_name=record.company_name,
        filing_type=record.filing_type,
        filing_date=record.filing_date,
        fiscal_year=record.fiscal_year,
        accession_number=record.accession_number,
        source_url=record.source_url,
        markdown_content=markdown,
        metadata=record.metadata,
    )

    chunk_payloads = [
        {
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "page_label": chunk.page_label,
            "token_count": chunk.token_count,
            "metadata": chunk.metadata,
            "embedding": embedding,
        }
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    saved_chunks = document_db.replace_document_chunks(
        client, document["id"], chunk_payloads
    )

    return {
        "chunks": len(saved_chunks),
        "document_id": document["id"],
    }
