# Backend (FastAPI)

Python API for auth, chat, retrieval, and LLM orchestration. Agent conventions: [AGENTS.md](AGENTS.md). Full setup: [docs/guides/backend-setup.md](../docs/guides/backend-setup.md).

## First-time setup

```bash
cd backend
cp .env.example .env   # fill in Supabase + OpenAI values
uv sync
```

Config lives in `app/config.py` (`settings`). Missing env vars fail at startup.

## Run locally

```bash
cd backend
uv run uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000  
- Health: http://127.0.0.1:8000/health  

Alternative (same port, no auto-reload):

```bash
uv run python app/main.py
```

Change port: add `--port 8765` to the uvicorn command.

## Dev commands

```bash
uv run ruff check app
uv run ruff format app
uv run pytest
```

## Database migrations

Alembic manages schema changes. Config reads `DATABASE_URL` from `app/config.py` via `alembic/env.py`.

**Use the direct Supabase Postgres URL** (`db.<ref>.supabase.co`), not the pooler.

### Current migration

| Revision | Description |
| -------- | ----------- |
| `157a7db1f8b8` | Initial schema — profiles, chats, citations, documents, chunks, pgvector, RLS |

### Workflow (review before apply)

From `backend/`:

```bash
# 1. Check what revision the DB is on (read-only)
uv run alembic current

# 2. List migration history
uv run alembic history

# 3. Preview SQL that would run — does NOT change the database
uv run alembic upgrade head --sql > migration_preview.sql

# 4. Apply when you are ready
uv run alembic upgrade head
```

After changing SQLAlchemy models:

```bash
uv run alembic revision --autogenerate -m "describe change"
# review backend/alembic/versions/<file>.py, then upgrade head
```

### What the initial migration creates

- Tables: `profiles`, `chat_threads`, `chat_messages`, `message_citations`, `source_documents`, `document_chunks`
- `vector` extension + HNSW index on embeddings
- Generated `search_vector` (`tsvector`) + GIN indexes
- RLS policies (users own chats; authenticated users read corpus)
- FK from `profiles.id` → `auth.users.id`

## Add a dependency

```bash
uv add <package>
uv add --dev <package>   # pytest, ruff, etc.
```

## Ingestion

From repo root, download sample filings:

```bash
uv run data/download.py
```

From `backend/`, convert HTML to Markdown and ingest into Supabase:

```bash
uv run python -m ingest.run --manifest ../data/downloads/manifest.json --convert
```

Limit to specific tickers:

```bash
uv run python -m ingest.run --manifest ../data/downloads/manifest.json --ticker AAPL --ticker MSFT
```

Requires `OPENAI_API_KEY`, Supabase service-role credentials, and applied migrations. After ingest, verify chunks exist (Supabase SQL editor):

```sql
select count(*) from document_chunks dc
join source_documents sd on sd.id = dc.document_id
where sd.ticker in ('AAPL', 'MSFT');
```
