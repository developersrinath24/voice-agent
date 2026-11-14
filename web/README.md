# Web client

Single-screen demo: the knowledge base on the left, the assistant on the right.
Ask a question, then click any citation to jump to the exact section the answer
was drawn from.

```bash
cp .env.example .env.local     # then set API_BASE_URL
npm install
npm run dev                    # http://localhost:3000
```

The FastAPI backend must be running too (`uv run uvicorn app.main:app --reload`
from the repository root).

## Why there is a proxy

The browser never calls the backend directly. Every request goes to a route
handler in `app/api/*`, which adds `X-API-Key` and forwards it.

That is the whole point: the browser must not hold the shared secret. A
`NEXT_PUBLIC_API_KEY` would be bundled into client JavaScript and readable by
anyone who opens devtools, which is the same as having no key at all. It also
means the browser only talks to its own origin, so there is no CORS to configure.

`API_BASE_URL` and `BACKEND_API_KEY` are server-only. They are read in
`lib/backend.ts`, which is imported only from route handlers.

## Environment

| Variable | Where | Purpose |
| --- | --- | --- |
| `API_BASE_URL` | server | FastAPI base URL. Defaults to `http://127.0.0.1:8000`. |
| `BACKEND_API_KEY` | server | Sent as `X-API-Key`. Leave empty if the backend has no `API_KEY`. |

## How a turn works

```text
document pane  <- GET /api/documents -> FastAPI /documents (files ingestion reads)
question       -> POST /api/chat     -> FastAPI /chat -> retrieve -> ground -> answer
answer         -> text + cited sections + cosine scores
citation click -> select that document, scroll to the section, flash it
```

`session_id` is kept in React state and sent with the next turn, so "and on
Saturday?" resolves against the previous exchange.

There is no voice layer in this client. `/voice/turn` still exists on the API —
it transcribes with ElevenLabs Scribe and speaks with Flash v2.5 — but the demo
does not call it, so opening the page costs no ElevenLabs credits.

## Layout

```text
app/
  page.tsx                single-screen shell, emergency footer
  api/documents/route.ts  proxy to /documents (the reading pane)
  api/chat/route.ts       proxy to /chat
  api/health/route.ts     proxy to /health, drives the connection dot
components/
  Workspace.tsx           document list + viewer + chat, mobile tabs, citation jumps
  DocumentNav.tsx         desktop column, mobile scroll strip
  DocumentViewer.tsx      markdown rendering, scroll-to-section, flash highlight
  ChatPanel.tsx           transcript, composer, examples, session state, errors
  TurnList.tsx            message bubbles, grounded badge, clickable citations
lib/
  backend.ts              server-only fetch helper (adds the API key)
  http.ts                 turns a FastAPI `detail` into a readable error
  types.ts                response shapes mirroring the backend schemas
```

The knowledge base is rendered with `react-markdown` + `remark-gfm` (the source
files contain markdown tables and bold labels) and styled with the Tailwind
typography plugin.

## Deploying

Vercel, root directory `web`, with the two environment variables set to the
public HTTPS API and its key.

## Limits worth knowing

- **Scores are cosine similarity** from `bge-small-en-v1.5`, not calibrated
  probabilities. They appear in citation tooltips so a viewer can see how close
  the match was.
- **The reading pane shows the files, not the vectors.** Both come from the same
  loader, so they agree — but if you edit `knowledge_base/` and do not re-ingest,
  the answer may be older than the page.
- **`/documents` is unauthenticated** by design: read-only, fictional, and the
  point of the demo. Everything with a database write or a model call needs the
  key.
- **One screen.** Panels scroll independently; below `lg` the documents and the
  assistant become tabs.
