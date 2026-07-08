# Phase 9 — Citations + trust UI (frontend)

## Context

Phases 1–8 are done: the backend already retrieves passages, runs the grounded
agent, validates citations, and streams a plain-text answer. Phase 9 makes
those answers *verifiable* in the UI — the actual point of this product for
analysts. Right now `ChatPage.tsx` throws away everything except message text:
`textFromUiMessage()` drops any non-`'text'` part, so the citation data the
backend already computes is silently discarded. There's also no thread
sidebar (`chatApi.listThreads()` is defined but never called), no rename
capability (missing on both frontend and backend), and chat errors collapse
into one generic red box.

Two backend-touching gaps surfaced during investigation that block a good
Phase 9 implementation, so this phase isn't 100% frontend-only:

1. **Citation delivery timing.** `orchestrator.py` computes the full grounded
   answer, validates it, and persists it — *before* it starts streaming text
   to the client (streaming is purely a visual chunking effect over an
   already-known answer). So citations are known up front, but
   `stream_text_events()` is called without `source_parts`, meaning citations
   never reach the client during the live stream — only on the next
   `GET /chat/threads/{id}` load. I checked whether to fix this by streaming
   `source` parts live, but the installed `ai` package (`v5.0.209`) validates
   incoming SSE chunks against a strict zod schema that only recognizes
   `source-url` / `source-document` part types with fixed fields
   (`sourceId`, `mediaType`, `title`) — the backend's current ad-hoc
   `{"type": "source", "sourceType": "document", ...}` shape would fail that
   validation and break the live stream. **Decision: don't stream citations
   live.** Instead, refetch the thread once the stream finishes
   (`useChat`'s `onFinish`) and swap in the persisted message, which already
   carries the full parts array — this is safe because `getThread()` results
   are assigned to state directly and never pass through the strict
   stream-chunk validator.
2. **Non-conformant source part shape.** Since we're touching
   `_assistant_message_json()` anyway, normalize its `"source"` parts to the
   real AI SDK v5 shape (`type: "source-document"`, `sourceId`, `mediaType`,
   `title`, with our extra excerpt/passage data tucked into
   `providerMetadata`, which is expressly meant for this). This lets the
   frontend use the SDK's own `SourceDocumentUIPart` type instead of
   hand-rolled duck-typing, and removes the landmine for whoever tries to
   enable live streaming later.

Everything else (sidebar, rename, error triage, insufficient-evidence
detection) is implementable with what already exists, following patterns
already in the codebase (`DashboardPage.formatError`, `http.ts`'s `ApiError`,
`components.json`'s `radix-nova` shadcn style, `button.tsx`'s `cva` pattern).

## Backend changes

**`backend/app/chat/orchestrator.py`**
- In `_assistant_message_json()`, change each citation's part to:
  ```python
  {
      "type": "source-document",
      "sourceId": passage.chunk_id,
      "mediaType": "text/plain",
      "title": f"{ticker} {filing_type} ({filing_date or fiscal_year or 'n/a'})",
      "providerMetadata": {
          "excerpt": citation.quote or passage.text[:280],
          "passage": _passage_for_json(passage),
      },
  }
  ```
  (`citations` array and `insufficient_evidence` flag at the top level stay as-is — they're already exactly what the frontend needs.)

**`backend/app/database/chats.py`**
- Add `rename_thread(client, thread_id, title) -> dict | None`: updates
  `title` + `updated_at` on `chat_threads`, mirroring `touch_thread`'s style.

**`backend/app/api/chat.py`**
- Add `UpdateThreadRequest(BaseModel)` with `title: str = Field(min_length=1, max_length=200)`.
- Add `PATCH /chat/threads/{thread_id}` — reuses `_get_owned_thread` for the
  404/ownership check, calls `chats.rename_thread`, returns `ThreadResponse`.

**`backend/tests/api/test_chat.py`**
- Add a rename test following the existing `monkeypatch` + `TestClient`
  pattern (happy path + 404-for-unowned-thread, mirroring
  `test_get_thread_returns_404_when_not_found_or_not_owned`).

No changes to `streaming.py`, the stream protocol, or `/chat/stream`'s
request/response contract.

## Frontend changes

**New types — `frontend/src/lib/citations.ts`**
- `SourcePassage` type (12 fields: `chunk_id`, `document_id`, `chunk_index`,
  `text`, `ticker`, `company_name`, `filing_type`, `filing_date`,
  `fiscal_year`, `accession_number`, `page_label`, `source_url`) matching
  `_passage_for_json`.
- `PersistedCitation { chunk_id, quote, passage }`.
- `AssistantExtras` — the extra fields the backend rides along on persisted
  `UIMessage` objects: `citations?: PersistedCitation[]`,
  `insufficient_evidence?: boolean`.
- A type guard `isSourceDocumentPart(part)` for `type === 'source-document'`,
  reading `providerMetadata.passage` / `.excerpt`.

**`frontend/src/lib/api.ts`**
- Add `renameThread: (threadId: string, title: string) => api.patch<ChatThread>(...)`.

**`frontend/src/lib/errors.ts` (new)**
- Extract `DashboardPage.tsx`'s `formatError` into a shared
  `describeApiError(error: unknown): string` (network → "Could not reach the
  backend...", `status === 401` → "session rejected...", `ApiError` other →
  `error.message`, plain `Error` → `error.message` as-is since in-stream
  `errorText` from the backend is already human-readable). Update
  `DashboardPage.tsx` to import it instead of its local copy.
- Use this in `ChatPage.tsx` for both `useChat`'s `error` and the thread-load
  error, so network/401/stream errors render distinct messages instead of one
  flat box.

**`ChatPage.tsx`**
- `authenticatedFetch` (the transport's custom fetch): after the FastAPI
  `fetch`, check `response.ok` and throw `new ApiError(...)` the same way
  `http.ts:request` does, so pre-stream failures (401 from `get_current_user`,
  404 unowned thread, 422 bad payload, network failure) become classifiable
  `ApiError`s in `useChat`'s `error`, not opaque `Error`s.
- On `useChat({ onFinish })`, refetch `chatApi.getThread(threadId)` and
  `setMessages(detail.messages.map(toUiMessage))` — this is how citations
  (and `insufficient_evidence`) actually arrive in the UI, per the timing
  decision above.
- `MessageBubble`: stop discarding non-text parts. Render the joined text
  parts, then render one citation `Badge` per `source-document` part (`[1]`,
  `[2]`, ...), each opening a `Popover` with company (`ticker`/
  `company_name`), filing (`filing_type` + `accession_number`), date
  (`filing_date` or `fiscal_year`), page/section (`page_label`), and excerpt.
  For a finished assistant message (not the currently-streaming one) with
  zero `source-document` parts, render an `Alert`-style "Insufficient
  evidence in the corpus for this answer" banner instead of citation badges,
  keyed off `message.insufficient_evidence` (falls back to "no sources"
  check only if that field is absent, e.g. a message not yet refetched).

**New shadcn primitives** (via `pnpm dlx shadcn@latest add badge popover alert` from `frontend/`, matching the existing `radix-nova` style in `components.json`; hand-roll following `button.tsx`'s `cva` + `data-slot` + `cn()` pattern if the CLI can't reach the registry):
- `src/components/ui/badge.tsx`
- `src/components/ui/popover.tsx`
- `src/components/ui/alert.tsx`

**Thread sidebar — new `ChatLayout`**
- `frontend/src/pages/chat/ChatLayout.tsx` (new): renders a persistent
  `<aside>` (`ThreadSidebar`) + `<Outlet/>`, wraps both chat routes.
- `frontend/src/pages/chat/ThreadSidebar.tsx` (new): calls
  `chatApi.listThreads()` on mount and whenever the route's `threadId`
  changes (covers new-thread creation and switching); renders each thread as
  a `NavLink` to `/chat/:id` (active state highlighted); a "New chat" link to
  `/chat`; per-row rename via a pencil icon that swaps the title for a text
  input, committing on blur/Enter via `chatApi.renameThread` and updating
  local state optimistically.
- `frontend/src/App.tsx`: nest the two chat routes under `ChatLayout`:
  ```tsx
  <Route path="/chat" element={<ProtectedRoute><ChatLayout /></ProtectedRoute>}>
    <Route index element={<NewChatPage />} />
    <Route path=":threadId" element={<ChatPage />} />
  </Route>
  ```

## Out of scope / left as-is

- No changes to `/chat/stream`'s request/response contract or the SSE
  protocol — citations remain a post-stream refetch, not a live event.
- No mobile-specific sidebar collapse beyond basic responsive width (matches
  the app's current minimal responsive-design effort elsewhere).
- No confidence score UI — `GroundedAnswer` only has the boolean
  `insufficient_evidence`, nothing to build a richer indicator from.

## Verification

- Backend: `uv run pytest backend/tests/api/test_chat.py` (new rename test
  green; existing stream/thread tests unaffected since the part-shape change
  isn't asserted anywhere today).
- Frontend: `pnpm exec tsc --noEmit`, `pnpm lint`.
- Manual, via `pnpm dev` + backend running locally:
  - Sign in → sidebar lists existing threads → open one → citation badges
    appear after the stream finishes → click a badge → popover shows
    company/filing/date/page/excerpt.
  - Ask a question the corpus can't support → "Insufficient evidence" banner
    renders instead of citation badges.
  - Rename a thread from the sidebar → persists across reload.
  - Stop the backend and send a message → network error message distinct
    from a deliberately-expired-session 401 message.
