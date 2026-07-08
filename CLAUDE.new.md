# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Document Copilot** — an internal chatbot that lets analysts query a corpus of SEC filings (10-Ks/10-Qs) in plain English and get sourced, citable answers. Fictional client: Driftwood Capital (see `docs/client-brief.md`). Full target architecture: `docs/architecture.md`. Build checklist / phase status: `docs/todo.md`.

@AGENTS.md
@backend/AGENTS.md
@frontend/AGENTS.md

## Commands

### Backend (run from `backend/`)

```bash
uv sync                                        # install deps
uv run uvicorn app.main:app --reload           # http://127.0.0.1:8000, health at /health
uv run ruff check app tests                    # lint
uv run ruff format app tests                   # format
uv run pytest                                  # full suite
uv run pytest -m "not integration"             # fast suite: no network/DB, must stay green
uv run pytest tests/chat/test_orchestrator.py::test_name   # single test
```

Alembic migrations (must use the **direct** Supabase connection string, not the pooler):

```bash
uv run alembic current                         # check DB revision (read-only)
uv run alembic upgrade head --sql > migration_preview.sql   # preview SQL, no changes
uv run alembic revision --autogenerate -m "describe change" # after editing app/database/models.py
uv run alembic upgrade head                    # apply (review the generated file first)
```

Ingestion (SEC filings → Supabase):

```bash
uv run data/download.py                        # from repo root: fetch sample 10-Ks into data/downloads/
uv run python -m ingest.run --manifest ../data/downloads/manifest.json --convert   # from backend/
uv run python -m ingest.run --manifest ../data/downloads/manifest.json --ticker AAPL --ticker MSFT
```

The repo-root `pytest.ini` also lets you run `pytest` from the repo root (`testpaths = backend/tests`).

### Frontend (run from `frontend/`)

```bash
pnpm install
pnpm dev              # http://127.0.0.1:5203
pnpm build             # tsc -b && vite build
pnpm lint
pnpm exec tsc --noEmit
```

There is no frontend test runner — none should be added (see `frontend/AGENTS.md`). Correctness is verified manually in the browser plus `tsc`/`eslint`.

## Architecture

Two paths through the system: a **live chat path** (Analyst → React SPA → FastAPI → Supabase/OpenAI) and an **ingestion path** (SEC filings → `backend/ingest/` scripts → Supabase), both converging on the same `document_chunks`/`source_documents` tables. The frontend is intentionally thin: it renders chat state and holds the Supabase session, but never calls OpenAI or Supabase's service-role key directly. FastAPI is authoritative for retrieval, grounding, LLM orchestration, and all privileged writes.

### Backend module map (`backend/app/`)

- `api/` — FastAPI routers. `auth.py` exposes `GET /me`; `chat.py` exposes thread CRUD and `POST /chat/stream`.
- `auth/dependencies.py` — `get_current_user` verifies the bearer token by calling Supabase Auth's `get_user` endpoint (not local JWT signature verification), then calls `ensure_profile` to create the `profiles` row on first request (`chat_threads.user_id` FKs to `profiles.id`).
- `chat/orchestrator.py` — coordinates one turn end-to-end: retrieve → run PydanticAI agent → validate grounding → **persist to Supabase → then stream**. Persist-before-stream is deliberate (see the comment in `stream_grounded_reply`): the full answer already exists, so streaming first would only create "saw the answer, refresh lost it" bugs.
- `chat/messages.py` — converts between the AI SDK's `UIMessage` wire format and internal types; only `text` parts are read today.
- `chat/streaming.py` — emits the Vercel AI SDK **UI Message Stream Protocol** over SSE (`data: <json>\n\n` frames, `data: [DONE]` terminator, `x-vercel-ai-ui-message-stream: v1` header) so `@ai-sdk/react`'s `useChat` can consume it directly.
- `assistant/` — the PydanticAI agent (`agent.py`) with bounded tools (`search_filings`, `read_chunk`, `read_surrounding_chunks` — no free-form SQL from the LLM), request-scoped `DocumentAgentDeps` (`deps.py`) that tracks every passage the agent has seen this turn, and the typed `GroundedAnswer`/`AnswerCitation` output models (`outputs.py`).
- `retrieval/` — `queries.py` runs raw parameterized SQL for `pgvector` cosine search and Postgres full-text search (`websearch_to_tsquery`); `fusion.py` combines both ranked lists with Reciprocal Rank Fusion (k=60); `retriever.py` ties embedding + both queries + fusion into `SourcePassage` results and also backs the `read_chunk`/`read_surrounding_chunks` tools.
- `grounding/validator.py` — the trust contract: an answer must either set `insufficient_evidence=True` with no citations, or include ≥1 citation whose `chunk_id` was actually retrieved/read by the agent's tools this turn (`DocumentAgentDeps.known_passages`). Anything else raises `GroundingError`, which the orchestrator turns into a stream error instead of a plausible-looking unsupported answer.
- `database/` — `models.py` (SQLAlchemy: `Profile`, `ChatThread`, `ChatMessage`, `MessageCitation`, `SourceDocument`, `DocumentChunk`), `supabase.py` (two clients: `get_admin_client()` uses the service-role key and bypasses RLS for privileged writes like citations; `get_user_client(token)` uses the anon key + the caller's bearer token so RLS applies), plus `chats.py`/`documents.py`/`profiles.py` persistence helpers.
- `config.py` — `pydantic-settings` `Settings`, the single source of env truth; fails fast on missing required vars.

### Frontend module map (`frontend/src/`)

- `lib/env.ts` — validates `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` at boot.
- `lib/supabase.ts` — browser Supabase client (auth only, anon key).
- `lib/http.ts` / `lib/api.ts` — `fetch` wrapper that injects the Supabase bearer token and produces typed `ApiError`s (with an `isNetworkError` flag distinguishing CORS/network failures from HTTP errors); `api.get/post/put/patch/delete` is the only way components should reach the backend.
- `lib/auth.tsx` / `lib/auth-context.ts` — session state.
- `pages/AuthPage.tsx`, `pages/DashboardPage.tsx`, `pages/chat/{ChatPage,NewChatPage}.tsx` — route-level components; chat pages use `@ai-sdk/react`'s `useChat` pointed at `${VITE_API_BASE_URL}/chat/stream`.
- `components/ui/` — shadcn primitives.

### Data model

`profiles` (1:1 with `auth.users`) → `chat_threads` → `chat_messages` → `message_citations` → `document_chunks` → `source_documents`. Chunks carry both an `embedding` (`pgvector`) and a generated `tsvector` for hybrid search; RLS restricts chat data to its owning user.

## Testing

- Backend tests mirror the module they test: `app/retrieval/retriever.py` → `tests/retrieval/test_retriever.py`.
- Tests marked `@pytest.mark.integration` require live Supabase/OpenAI credentials and are excluded from the fast suite (`pytest -m "not integration"`), which must stay green with no network/DB access.
- Prefer unit tests that mock at the service boundary (`QueryExecutor` protocol for DB, callables for embeddings) over integration tests.
