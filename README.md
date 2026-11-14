# GP Clinic — Voice AI Assistant

A voice-first assistant for a GP (general practice) clinic. It answers patient
questions from a curated clinic knowledge base using retrieval-augmented
generation, and stores every conversation so it can be reviewed later.

Built as a learning project, with the goal of being deployable and defensible in
a technical interview.

## Status

| Phase | Scope | State |
| --- | --- | --- |
| 0 | Repo cleanup, config, tooling | Done |
| 1 | Session/message persistence in Supabase | Done |
| 2 | Knowledge base ingestion + Qdrant retrieval | Done |
| 3 | Retrieval + answer quality evaluation | Next |
| 4 | LLM pipeline (DeepSeek primary, Gemini fallback) | Planned |
| 5 | Speech-to-text / text-to-speech (ElevenLabs) | Planned |
| 6 | Next.js voice client | Planned |
| 7 | Deployment (Oracle Cloud VM, domain, HTTPS) | Planned |

`POST /chat` currently returns a fixed message. It records both turns in
Supabase, so session and history handling are real; the answer generation is
not wired up yet. Retrieval itself is real and can be exercised through
`POST /search`.

## Architecture

```
Browser / phone
      |
      |  voice + chat
      v
Next.js client  --------------------+
      |                             |
      | HTTP                        | reads history
      v                             v
FastAPI backend  <->  Supabase (sessions, messages)
      |
      +--> Qdrant Cloud (knowledge base vectors)
      |
      +--> DeepSeek (primary LLM) / Gemini (fallback, embeddings)
      |
      +--> ElevenLabs (STT + TTS)
```

## Local setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
cp .env.example .env      # then fill in the values
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API docs.

### Environment variables

See `.env.example`. Only the Supabase pair is needed right now.

**Use the Supabase `service_role` key, not the `anon` key.** Row level security
is enabled on both tables with no policies, so the anon key can read nothing.
The `service_role` key bypasses RLS and must never be exposed to a browser —
it belongs only on the backend.

### Database

Run `db/migrations/0001_init.sql` once in the Supabase SQL editor. It creates
`sessions` and `messages`, indexes, an `updated_at` trigger, and enables RLS.

Verify the connection:

```bash
uv run python -m app.database.test_connection
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Service banner |
| `GET` | `/health` | Liveness + which integrations are configured |
| `POST` | `/chat` | Send a message; creates a session if `session_id` is omitted |
| `POST` | `/sessions` | Create a session explicitly (`{"channel": "web" \| "voice"}`) |
| `GET` | `/sessions/{id}` | Session status and message count |
| `GET` | `/sessions/{id}/messages` | Full ordered transcript |
| `POST` | `/sessions/{id}/end` | Mark a session as ended |
| `POST` | `/search` | Retrieval only: ranked chunks with scores and sources |
| `POST` | `/voice/turn` | Reserved for the speech pipeline (returns 501 for now) |

## Project layout

```
app/
  main.py               FastAPI app, CORS, logging, router wiring
  core/config.py        Settings loaded from .env
  api/deps.py           Shared dependencies (Supabase client, 503 handling)
  api/routes/           health, chat, sessions, voice
  database/client.py    Lazy Supabase client
  database/repositories.py  All queries for sessions and messages
  schemas/              Pydantic request/response models
  rag/
    chunking.py         Markdown -> chunks with stable IDs and metadata
    embeddings.py       EmbeddingProvider protocol + local fastembed implementation
    vector_store.py     Qdrant collection setup, upserts, search
    retriever.py        Query -> ranked chunks; prompt context formatting
    ingest.py           CLI for indexing the knowledge base
  services/             (empty) LLM clients, prompt assembly
  agents/               (empty) conversation orchestration
db/migrations/          SQL migrations to run in Supabase
knowledge_base/         Source clinic documents to ingest (fictional practice)
tests/                  Pytest suite (Supabase faked in memory, no network)
```

## Knowledge base

`knowledge_base/` contains ten markdown documents describing **Bramble Court
Surgery**, a fictional NHS GP practice: opening hours, appointments, services,
prescriptions, out-of-hours care, registration, fees, staff, test results and
policies. Roughly 3,700 words across 71 headed sections.

It is deliberately realistic in shape — front matter with `title`, `category`
and `last_reviewed`, one topic per file, and a `##` heading per self-contained
fact. Those headings become the chunk boundaries, so the retrieval unit is a
whole answer rather than an arbitrary slice of text.

If you change the documents, re-run ingestion; chunk IDs are deterministic, so
edits replace existing vectors instead of duplicating them.

### Ingestion

```bash
uv run python -m app.rag.ingest             # incremental: replaces changed files
uv run python -m app.rag.ingest --rebuild   # drop the collection and re-index
```

**Embeddings run locally** via `fastembed` and `BAAI/bge-small-en-v1.5`
(384 dimensions, ~50 MB, downloaded on first use). No API key and no cost, which
is what makes it practical to re-index on every document edit. Embeddings sit
behind the `EmbeddingProvider` protocol in `app/rag/embeddings.py`, so swapping in
Gemini or OpenAI means one class plus a `--rebuild`, because the vector size is
fixed when the Qdrant collection is created.

Retrieval is dense-only for now. Query prompts and document prompts are
deliberately separate calls: bge models are trained with different instructions
for each, and sending a query through the document path measurably hurts recall.


## Tests

```bash
uv run pytest
uv run ruff check .
```

Tests never touch the network; `tests/conftest.py` contains an in-memory fake of
the small part of the Supabase client this app uses.
