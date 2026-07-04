# Document Copilot — implementation checklist

Work top to bottom. Each phase unlocks the next.

## Backend or frontend first?

**Start with foundation + backend**, then bring the frontend in for a thin vertical slice as soon as auth exists.

| Layer | Why it comes when it does |
| ----- | ------------------------- |
| **Supabase + schema** | Auth, chats, documents, chunks, and retrieval all live here. Nothing real works without this. |
| **Backend** | Owns JWT verification, DB writes, retrieval, LLM, citations, and streaming. The frontend is intentionally thin. |
| **Frontend (early slice)** | Scaffold the SPA early, but wire login + chat UI only after the backend can verify tokens and return stub/streaming responses. |
| **Ingestion + RAG** | Backend-only until retrieval works; then connect the real agent to the chat path. |
| **Polish + deploy** | Citations UI, errors, Railway — after the core loop works locally. |

You do **not** need to finish the backend before touching the frontend. The sweet spot is: **schema → auth on both sides → stub `/chat/stream` → chat UI**, then finish ingestion/retrieval/agent on the backend while the UI grows around it.

Reference: [architecture.md](architecture.md) (Implementation Sequence), [backend-setup.md](guides/backend-setup.md), [frontend-setup.md](guides/frontend-setup.md), [supabase-setup.md](guides/supabase-setup.md).

---

## Phase 0 — Prerequisites

- [x] Install Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, pnpm (see [README](../README.md))
- [x] Create a Supabase project ([supabase-setup.md](guides/supabase-setup.md))
- [x] Save Project URL, anon key, service_role key, and **direct** database connection string
- [x] Create an OpenAI API key (needed from Phase 7 onward)
- [x] (Optional early) Run sample corpus download: `uv run data/download.py` from repo root

---

## Phase 1 — Scaffold both services

Minimal shells so `uv sync` / `pnpm dev` work. No product logic yet.

### Backend

- [x] Add dependencies per [backend-setup.md](guides/backend-setup.md) (`fastapi`, `uvicorn`, `pydantic-settings`, etc.)
- [x] Create `backend/app/main.py` with health route (`GET /health`)
- [x] Create `backend/app/config.py` — single settings module; fail fast on missing env
- [x] Copy `backend/.env.example` → `.env` and fill Supabase + OpenAI vars
- [x] Confirm: `uv run uvicorn app.main:app --reload` starts cleanly
- [x] Add `backend/README.md` with run, lint, and migration commands

### Frontend

- [x] Scaffold Vite + React + TS per [frontend-setup.md](guides/frontend-setup.md)
- [x] Add Tailwind + shadcn/ui baseline
- [x] Create `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [x] Copy `frontend/.env.example` → `.env`
- [x] Confirm: `pnpm dev` serves the app

---

## Phase 2 — Database schema (backend)

Schema before auth/chat — everything persists here.

- [x] Init Alembic (`uv run alembic init alembic`); wire `env.py` to SQLAlchemy metadata + `settings.database_url`
- [x] Add SQLAlchemy models in `app/database/models.py`:
  - [x] `profiles`
  - [x] `chat_threads`, `chat_messages`, `message_citations`
  - [x] `source_documents`, `document_chunks` (embedding + `tsvector` columns)
- [x] Generate and **review** initial migration; add explicit ops for:
  - [x] `create extension if not exists vector`
  - [x] HNSW index on embeddings, GIN on full-text / metadata
  - [x] RLS policies
- [x] Apply: `uv run alembic upgrade head` against Supabase direct connection
- [x] Add `app/database/supabase.py` — user-scoped and service-role clients

---

## Phase 3 — Auth bridge (backend + frontend)

Both sides in the same sprint — neither is useful alone.

### Backend

- [x] `app/auth/dependencies.py` — verify `Authorization: Bearer <token>` via Supabase Auth
- [x] Expose `get_current_user` FastAPI dependency
- [x] Add protected probe route (e.g. `GET /me`) to prove JWT flow

### Frontend

- [x] `src/lib/supabase.ts` — browser Supabase client
- [x] Email sign-in / sign-up pages (Supabase Auth only)
- [x] Session persistence + sign-out
- [x] `src/lib/http.ts` — fetch wrapper with bearer token injection
- [x] Confirm: logged-in user can hit backend `/me` successfully

---

## Phase 4 — Chat API skeleton (backend)

Thread CRUD + streaming stub before real LLM work.

- [x] `app/database/chats.py` — create/list/load threads and messages (user-scoped)
- [x] REST routes: list threads, create thread, load thread + messages
- [x] `POST /chat/stream` — accept AI SDK message shape; stream a **stubbed** assistant reply
- [x] `app/chat/streaming.py` — emit AI SDK-compatible stream events
- [x] Persist user + assistant messages after stream completes
- [x] Configure CORS (`ALLOWED_ORIGINS`) for local frontend origin

---

## Phase 5 — Chat UI vertical slice (frontend)

Prove the full browser → FastAPI → DB loop.

- [x] `src/lib/api.ts` — thread list, create, load history
- [x] Chat route + layout (`src/pages/chat/*`)
- [x] Integrate Vercel AI SDK `useChat` pointed at `${API}/chat/stream` with Supabase token headers
- [x] Basic message list + input + streaming indicator
- [x] Empty state for new thread
- [x] Frontend checks: `pnpm exec tsc --noEmit`, `pnpm lint`, Vite app loads, unauthenticated `/chat` redirects to `/auth`
- [ ] Confirm: sign in → new thread → send message → see stub stream → reload → history persists

---

## Phase 6 — Ingestion pipeline (backend)

Get real SEC filings into Supabase. Can run in parallel with Phase 5 if using stub chat.

- [x] `backend/ingest/` — parse downloaded filings to normalized Markdown (`convert_html_to_markdown.py`, via docling; spot-checked tables convert correctly)
- [x] Chunking strategy (size, overlap, metadata: ticker, filing type, date, section) — `ingest/chunking.py` (400 words / 50 overlap, paragraph-aware)
- [x] Embedding generation (OpenAI) + write `document_chunks` + `source_documents` — `ingest/embeddings.py`, `app/database/documents.py`
- [x] Populate Postgres `tsvector` for full-text search — generated column on insert; no separate ingest step
- [x] Ingest script CLI (e.g. `uv run python -m ingest.run --manifest ../data/downloads/manifest.json`)
- [x] Confirm: corpus ingested — 25 sample 10-K filings (AAPL, MSFT, NVDA, AMZN, GOOGL) in `source_documents` + `document_chunks` (batched chunk inserts; `page_label` clipped to 128 chars)

---

## Phase 7 — Retrieval (backend)

Hybrid search before the agent.

- [x] `app/retrieval/queries.py` — pgvector semantic search + Postgres full-text search
- [x] `app/retrieval/fusion.py` — Reciprocal Rank Fusion in Python
- [x] `app/retrieval/retriever.py` — query → ranked `SourcePassage` list
- [x] Unit tests for fusion ranking and query assembly (mock DB)
- [ ] Confirm: test query returns relevant chunks from ingested corpus

---

## Phase 8 — LLM agent + grounding (backend)

Replace stub stream with grounded answers.

- [ ] `app/assistant/` — PydanticAI agent, deps, typed `GroundedAnswer` output, `instructions.md`
- [ ] Agent tools: `search_filings`, `read_chunk`, `read_surrounding_chunks` (no free-form SQL)
- [ ] `app/chat/orchestrator.py` — one turn: retrieve → agent → validate → stream → persist
- [ ] `app/grounding/validator.py` — every citation maps to a retrieved passage
- [ ] Wire `/chat/stream` to orchestrator
- [ ] Unit tests for citation validation and grounding failures
- [ ] Confirm: real question returns cited answer from corpus (curl or frontend)

---

## Phase 9 — Citations + trust UI (frontend)

Make answers verifiable for analysts.

- [ ] Citation badges on assistant messages
- [ ] Source passage panel (company, filing, date, page/section, excerpt)
- [ ] “Insufficient evidence” empty / error state when corpus cannot support an answer
- [ ] Distinguish network, 401, and server errors in the chat UI
- [ ] Thread sidebar (list, rename title, open existing)

---

## Phase 10 — Quality, ops, deploy

- [ ] Backend: structured logging (`structlog`), sensible error responses per [architecture.md](architecture.md)
- [ ] Backend tests: `pytest -m "not integration"` green in CI
- [ ] Integration tests (optional, marked) for retrieval + one end-to-end chat turn
- [ ] Railway: backend service (Uvicorn) + frontend static build
- [ ] Production env vars on Railway; Supabase Auth redirect URLs updated
- [ ] Smoke test deployed app: sign in → ask corpus question → citations render

---

## Phase 11 — Done when (acceptance)

Use [client-brief.md](client-brief.md) example questions as manual QA:

- [ ] Analyst can sign in with email
- [ ] Chat history is per-user and persists
- [ ] Answers cite specific filings and passages
- [ ] System says clearly when evidence is missing (no hallucinated citations)
- [ ] No service-role key or OpenAI key in the browser bundle
- [ ] At least one client-brief question answered correctly with citations

---

## Suggested weekly pacing (solo)

| Week | Focus |
| ---- | ----- |
| 1 | Phases 0–3 — Supabase, scaffold, schema, auth |
| 2 | Phases 4–5 — stub chat end-to-end in the browser |
| 3 | Phase 6 — ingest sample corpus |
| 4 | Phases 7–8 — retrieval + agent |
| 5 | Phases 9–11 — citations UI, hardening, deploy |

Adjust pace as needed; Phases 6–7 are the longest backend work.
