# Realtime voice calls (ElevenLabs Agents)

The demo's **Call** button places a real, full-duplex call: the browser streams
the microphone to ElevenLabs, the agent decides when the visitor has finished
speaking, and the agent's brain is this repository's RAG chain.

```
browser ──signed URL──▶ ElevenLabs agent ──POST /v1/chat/completions──▶ OCI API
   ▲                          │                                            │
   └──────── speech ──────────┘◀──────────── grounded answer ──────────────┘
```

Everything except creating the agent happens in this repo. Text chat stays the
default; a call is only placed when someone presses Start.

---

## 1. What the browser does

| Step | Request | Notes |
| --- | --- | --- |
| 1 | `GET /api/voice-session` (Next proxy) → `GET /voice/session` (FastAPI) | Gated by `X-API-Key`, exactly like `/chat`. |
| 2 | microphone permission | Asked **before** the session, so a blocked mic does not spend a call. |
| 3 | `startSession({ signedUrl })` | `@elevenlabs/react`, WebSocket transport. |
| 4 | auto-hangup at `max_seconds` | 90 s by default, enforced in the UI. |

The browser never sees `ELEVENLABS_API_KEY`, `API_KEY` or `AGENT_LLM_SECRET`.
It only receives a short-lived signed URL for one agent.

## 2. What ElevenLabs calls

`POST /v1/chat/completions`, OpenAI-compatible, `text/event-stream`:

```
data: {"choices":[{"delta":{"content":"One moment, let me check that for you. "}}]}
data: {"choices":[{"delta":{"content":"We close at 18:30 on Tuesdays."}}]}
data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

The first chunk is a buffer phrase sent **before** retrieval starts. The chain
takes two to four seconds; without it the caller hears silence and interrupts.
The answer itself is sent in one chunk because the chain does not stream tokens,
and half a sentence is worse than a short wait.

Authentication is `AGENT_LLM_SECRET`, accepted as `Authorization: Bearer …`,
`xi-api-key` or `x-api-key`. If a request is rejected the server logs the header
*names* it received (`journalctl -u gp-voice-agent | grep "agent llm auth"`),
never their values.

## 3. Backend setup (on the OCI box)

```bash
cd ~/voice-agent
openssl rand -hex 24            # this is AGENT_LLM_SECRET, keep it for the dashboard
nano .env
```

Add:

```dotenv
ELEVENLABS_API_KEY=<same key as phase 5a>
ELEVENLABS_AGENT_ID=agent_xxxxxxxxxxxxxxxxxxxxx
AGENT_LLM_SECRET=<the hex string>
VOICE_MAX_CALL_SECONDS=90
VOICE_DAILY_CALL_LIMIT=10
```

Restart and check:

```bash
sudo systemctl restart gp-voice-agent
curl https://api-voice.horizonwebcraft.com/health
# "elevenlabs": true
```

Then test the LLM endpoint directly:

```bash
curl -N https://api-voice.horizonwebcraft.com/v1/chat/completions \
  -H "Authorization: Bearer $AGENT_LLM_SECRET" \
  -H "content-type: application/json" \
  -d '{"model":"clinic-rag","messages":[{"role":"user","content":"What time do you close on a Tuesday?"}]}'
```

Expected: the buffer phrase, then a grounded answer ending 18:30, then
`[DONE]`. On PowerShell use `curl.exe` (plain `curl` is an alias for
`Invoke-WebRequest` and will not stream).

Also confirm the reverse proxy is not buffering. The `Caddyfile.native` excludes
`/v1/chat/completions` from `encode`, because a compressor waits for enough
bytes before flushing and the buffer phrase would arrive late. After editing the
Caddyfile:

```bash
sudo sed 's/{$DOMAIN}/api-voice.horizonwebcraft.com/' deploy/Caddyfile.native \
  | sudo tee /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## 4. Create the agent in the dashboard

One-time, in <https://elevenlabs.io>:

1. **Agents → New agent → Blank agent.** Name it *Bramble Court Surgery*.
2. **Voice**: Bella (`EXAVITQu4vr4xnSDxMaL`), model **Flash v2.5** — the
   low-latency model. Premade voices work on the free tier; most library voices
   return `402`.
3. **First message**: `Good morning, Bramble Court Surgery. How can I help?`
4. **System prompt**: keep it short and deferential to the knowledge base. The
   RAG chain already writes the answer; the agent's job is to be a receptionist,
   not to add facts:

   > You are the receptionist at Bramble Court Surgery. Answer briefly, in one
   > or two sentences. Only use the information the custom LLM gives you — never
   > invent opening hours, prices or policies. If it says the information is not
   > available, offer to put the caller through to reception on 01234 567890.

5. **LLM → Custom LLM**:
   - Server URL: `https://api-voice.horizonwebcraft.com/v1`
     (the dashboard appends `/chat/completions`; if it asks for a full
     endpoint, enter the whole path).
   - Model ID: `clinic-rag` (any name; our endpoint echoes it back).
   - Secret / API key: the `AGENT_LLM_SECRET` value from step 3.
6. **Advanced**: max call duration 2 minutes as a backstop (the UI hangs up at
   90 s and the server counts one call either way).
7. Copy the **Agent ID** (`agent_…`) into `ELEVENLABS_AGENT_ID` and restart the
   service.

## 5. Test the call

Open `https://voice.horizonwebcraft.com`, press **Call** in the assistant panel,
allow the microphone, and ask *"What time do you close on a Tuesday?"*.

- The status line moves through Connecting → Listening → Reception is speaking.
- The transcript appears live on the panel; a timer counts down to 90 s.
- Hang up, then ask the same question in **Chat**: the text answer carries
  citations that scroll the source document into view. That side-by-side is
  the point of the demo — the call is convenient, the text tab is checkable.

## 6. Cost control

A call spends credits for as long as it is open, so there are three independent
brakes:

| Brake | Where | What it does |
| --- | --- | --- |
| `VOICE_MAX_CALL_SECONDS` | returned by `/voice/session`, enforced in the UI | hangs up at 90 s |
| `VOICE_DAILY_CALL_LIMIT` | in-process counter in the API | `429` after N calls per UTC day |
| agent max duration | ElevenLabs dashboard | backstop if a client ignores the UI |

A call is only counted once ElevenLabs has returned a signed URL, so a failed
handshake costs nothing. The counter is process memory: restarting the service
resets it. That is deliberate — the failure mode is "the allowance came back",
never "the account was drained".

## 7. Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Call button says `503 … ELEVENLABS_AGENT_ID` | env not set, or service not restarted |
| `429 … used its calls for today` | daily cap reached; wait for the UTC reset or use Chat |
| Agent says "something went wrong" | `journalctl -u gp-voice-agent` — usually LLM quota or Qdrant |
| Agent talks to itself / long silence | buffer phrase not arriving: check Caddy's `encode` exclusion |
| `401 Invalid agent secret` in the log | dashboard secret ≠ `AGENT_LLM_SECRET`; the log lists header names |
| No microphone prompt | site is not HTTPS, or the browser has blocked the mic for the origin |
| Ends immediately after connecting | agent id / signed URL belongs to a different agent, or free minutes are exhausted |
