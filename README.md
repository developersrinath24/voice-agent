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
| 2 | Knowledge base ingestion + Qdrant retrieval (LangChain) | Done |
| 3 | RAG answer chain, DeepSeek primary / Gemini fallback | Done, needs an API key |
| 4 | Retrieval and answer quality evaluation | Next |
| 5 | Speech-to-text / text-to-speech (ElevenLabs) | Planned |
| 6 | Next.js voice client | Planned |
| 7 | Deployment (Oracle Cloud VM, domain, HTTPS) | Planned |

`POST /chat` runs the full pipeline: retrieve relevant clinic passages, answer
from them, return citations, and persist both turns. It returns `503` until a
model key is set in `.env`, rather than pretending the knowledge base can answer
on its own.

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
      +--> LangChain chain
             |
             +--> Qdrant Cloud (knowledge base vectors, 384-dim cosine)
             +--> DeepSeek (primary LLM) -> Gemini (fallback)
      |
      +--> ElevenLabs (STT + TTS)
```

## How an answer is produced

```
question
  -> embed with bge-small (query prompt)
  -> Qdrant cosine search, top_k passages, relevance floor
  -> if nothing clears the floor: "call reception"  (no model call)
  -> numbered context block + system prompt + recent turns
  -> DeepSeek; on timeout/5xx/rate-limit, Gemini
  -> plain prose answer + source list
  -> both turns written to Supabase
```

Three properties are deliberate:

- **Grounding gate.** No relevant passage means no model call. A grounded
  "I don't have that information" costs nothing and cannot hallucinate.
- **Spoken-aloud prompt.** Two or three sentences, no markdown, no lists — a
  synthesiser reads `**` as "asterisk asterisk".
- **Emergency rules come first.** "Call 999" outranks "only answer from context",
  because "I don't have that information" is the wrong reply to "I have chest
  pain".

## Models

`LLM_ORDER` controls the call order; providers without an API key are skipped
automatically.

| Provider | Model | Notes |
| --- | --- | --- |
| Gemini | `gemini-3.5-flash-lite` | Default. ~2.1s per answer, free tier. |
| Gemini | `gemini-3.5-flash` | ~5.9s per answer, longer, slightly richer. |
| DeepSeek | `deepseek-flash` | DeepSeek-V4.1-Flash, 1M context. Needs account credit. |

Measured on the same two clinic questions through the full chain. `lite` models
use fixed sampling, so `temperature` is not sent to them.

`gemini-2.5-flash` is **no longer available to new users** (404), and
`deepseek-chat` was superseded by `deepseek-flash`. Both names appear in older
tutorials; neither works today.

## Local setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
cp .env.example .env      # then fill in the values
uv run python -m app.rag.ingest
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API docs.

### Environment variables

See `.env.example`. You need Supabase, Qdrant, and at least one of
`DEEPSEEK_API_KEY` / `GEMINI_API_KEY`.

**Use the Supabase `service_role` key, not the `anon` key.** Row level security
is enabled on all tables with no policies, so the anon key can read nothing. The
`service_role` key bypasses RLS and must never be exposed to a browser — it
belongs only on the backend.

`RETRIEVAL_MIN_SCORE` is the relevance floor. At 0.5, `"What is the capital of
France?"` (0.43) is rejected while genuine clinic questions (0.6+) pass. It needs
recalibrating if you change embedding model.

### Database

`db/migrations/0001_baseline.sql` documents the live schema: `sessions`,
`messages`, `appointments`, indexes and RLS. The tables already exist in the
project, so the script is a no-op there; it exists so the schema is versioned and
reproducible.

Verify the connection:

```bash
uv run python -m app.database.test_connection
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Service banner |
| `GET` | `/health` | Liveness + which integrations are configured |
| `POST` | `/chat` | RAG answer; creates a session if `session_id` is omitted |
| `POST` | `/sessions` | Create a session explicitly |
| `GET` | `/sessions/{id}` | Session status and message count |
| `GET` | `/sessions/{id}/messages` | Full ordered transcript |
| `POST` | `/sessions/{id}/end` | Mark a session as ended |
| `POST` | `/search` | Retrieval only: ranked chunks with scores and sources |
| `POST` | `/voice/turn` | Reserved for the speech pipeline (returns 501 for now) |

`/chat` returns `grounded` and a `sources` array, so a client can show *why* an
answer was given and flag ungrounded replies for review.

## Project layout

```
app/
  main.py               FastAPI app, CORS, logging, router wiring
  core/config.py        Settings loaded from .env
  api/deps.py           Shared dependencies (Supabase, assistant, 503 handling)
  api/routes/           health, chat, sessions, search, voice
  database/client.py    Lazy Supabase client
  database/repositories.py  All queries for sessions and messages
  schemas/              Pydantic request/response models
  rag/
    loaders.py          Markdown -> LangChain Documents (front matter, deterministic IDs)
    embeddings.py       Local fastembed provider + LangChain adapter
    vector_store.py     QdrantVectorStore setup, filters, delete-by-source
    retriever.py        Query -> ranked chunks; prompt context formatting
    ingest.py           CLI for indexing the knowledge base
  services/
    llm.py              DeepSeek primary, Gemini fallback (with_fallbacks)
    prompts.py          System prompt and the not-found answer
  agents/
    clinic_assistant.py Retrieve -> ground -> answer chain
db/migrations/          SQL migrations to run in Supabase
knowledge_base/         Source clinic documents to ingest (fictional practice)
tests/                  Pytest suite (fakes for Supabase, models and vectors)
```

## Why LangChain

Used where it earns its place: `Document` as the shared contract between loader,
store and chain; `MarkdownHeaderTextSplitter`; `QdrantVectorStore`;
`ChatPromptTemplate`; and `with_fallbacks`, which gives provider failover without
hand-written retry logic.

Not used where it would only add indirection: the chunking policy (front matter
parsing, title-prefixed text, deterministic point IDs), the relevance floor, and
the grounding gate are ours, because they encode decisions specific to this
clinic and this corpus.

## Knowledge base

`knowledge_base/` contains ten markdown documents describing **Bramble Court
Surgery**, a fictional NHS GP practice: opening hours, appointments, services,
prescriptions, out-of-hours care, registration, fees, staff, test results and
policies. Around 4,000 words, indexed as 78 chunks.

The structure is deliberate: front matter with `title`, `category` and
`last_reviewed`, one topic per file, and a `##` heading per self-contained fact.
Those headings are the chunk boundaries, so the retrieval unit is a whole answer
rather than an arbitrary slice of text.

### Ingestion

```bash
uv run python -m app.rag.ingest             # incremental: replaces changed files
uv run python -m app.rag.ingest --rebuild   # drop the collection and re-index
```

Re-ingestion is idempotent: point IDs are derived from file, section and
position, and each file is deleted before its chunks are re-added, so a section
removed from the markdown disappears from the index.

**Embeddings run locally** via `fastembed` and `BAAI/bge-small-en-v1.5`
(384 dimensions, ~50 MB, downloaded on first use). No API key and no per-request
cost, which is what makes re-indexing on every document edit practical.

### Known limitations

Dense-only retrieval misfires on questions where the answer is phrased very
differently from the question. `"What time do you close on a Tuesday?"` ranks
*When the surgery is closed* (0.68) above *Opening hours* (0.65): the phrase in
the heading is a near-exact lexical match, and bge-small cannot tell "closed now"
from "closing time". The correct passage is still within the top 5, so answers
survive — but rank 1 does not.

The fix is hybrid retrieval (BM25 + dense, fused with Reciprocal Rank Fusion),
which is the next planned step alongside an evaluation set. Two content fixes
already applied from the same exercise: markdown tables embed poorly, so hours
are also stated in prose; and a negation buried in a bullet list is invisible to
retrieval, so "we do not offer ear syringing" is now its own sentence.

## Tests

```bash
uv run pytest
uv run ruff check .
```

Tests never touch the network. Supabase is faked in memory, Qdrant runs in
`location=":memory:"` mode (same query engine as production), embeddings are a
deterministic fake, and the chat model is a recording fake — which lets the
assistant tests assert on the exact prompt that would have been sent.
