# Web client

Next.js front end for the clinic voice assistant. One page: tap the microphone,
speak, hear the answer. Text input is there as a fallback when a microphone is
not available.

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
means the browser only talks to its own origin, so there is no CORS to configure
and no preflight on the audio upload.

`API_BASE_URL` and `BACKEND_API_KEY` are server-only. They are read in
`lib/backend.ts`, which is imported only from route handlers.

## Environment

| Variable | Where | Purpose |
| --- | --- | --- |
| `API_BASE_URL` | server | FastAPI base URL. Defaults to `http://127.0.0.1:8000`. |
| `BACKEND_API_KEY` | server | Sent as `X-API-Key`. Leave empty if the backend has no `API_KEY`. |

## How a turn works

```text
mic press
  -> getUserMedia, MediaRecorder (webm/opus in Chrome, mp4 in Safari)
  -> stop -> Blob -> FormData -> POST /api/voice
       -> FastAPI /voice/turn -> Scribe -> RAG chain -> Flash TTS
  -> transcript + answer + sources + base64 MP3
  -> <audio> plays the MP3, transcript is appended to the list
```

`session_id` is kept in React state and sent with the next turn, so "and on
Saturday?" resolves against the previous exchange.

## Layout

```text
app/
  page.tsx              header, footer, mounts the console
  api/voice/route.ts    multipart proxy to /voice/turn
  api/chat/route.ts     JSON proxy to /chat (text fallback)
  api/health/route.ts   proxy to /health, drives the "backend connected" line
components/
  VoiceConsole.tsx      recording, upload, playback, errors, session state
  TurnList.tsx          transcript, source chips, per-stage timings
lib/
  recorder.ts           MediaRecorder wrapper with format detection
  backend.ts            server-only fetch helper (adds the API key)
  types.ts              response shapes mirroring the backend schemas
```

## Deploying

Vercel, root directory `web`, with the two environment variables set to the
public HTTPS API and its key. `export const maxDuration = 60` in the proxy routes
keeps a cold voice turn from being cut off by the serverless timeout.

The backend must allow the Vercel origin only if the browser ever calls it
directly — with this proxy it does not, but `ALLOWED_ORIGINS` on the API still
matters for the docs page and any direct testing.

## Limits worth knowing

- **Turn-based.** No barge-in; the answer is generated in full before any audio
  starts. The answer takes ~2s of the ~3s round trip.
- **Text fallback has no audio.** `/chat` returns text only; speaking a typed
  question needs the voice endpoint, which currently requires an audio upload.
- **iOS autoplay.** Playback is attempted automatically, but Safari may require
  a tap. The `<audio controls>` element is always rendered for that reason.
- **Microphone needs a secure context.** `localhost` or HTTPS — plain `http://`
  on a LAN address will not prompt for permission.
- **60-second cap** per recording, enforced in the component and again by the
  backend's 20 MB upload limit.

## Next step

Realtime replaces the transport, not the page: keep `TurnList`, the source chips
and the layout, and swap `sendAudio` for an ElevenLabs agent session started from
a signed URL issued by the backend. Everything below the recorder is disposable
when that happens.
