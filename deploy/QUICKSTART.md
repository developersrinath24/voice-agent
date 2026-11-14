# Deployment checklist — API on OCI, demo on Vercel

Concrete runbook for this project, using the real hostnames:

| Piece | Where | Hostname |
| --- | --- | --- |
| FastAPI backend | Oracle Cloud VM, Ubuntu 24.04, native Python + `uv` + systemd | `api-voice.horizonwebcraft.com` |
| Next.js demo | Vercel (free) | `voice.horizonwebcraft.com` |
| Database | Supabase (already provisioned) | — |
| Vectors | Qdrant Cloud (already indexed, 78 points) | — |

The VM stores nothing but the code and `.env`: no database, no vectors, no
uploads. `ORACLE-NATIVE.md` explains *why* each step exists; this file is the
order to do them in.

Assumes `ubuntu` is the SSH user (the Oracle Ubuntu images create it) and the
repo is uploaded to `/home/ubuntu/voice-agent`.

---

## 1. Reserve the public IP

Console → Compute → Instances → your instance → **Reserved public IP**.

An ephemeral address changes if the instance is stopped, which would silently
break DNS and the certificate. Do this before touching DNS.

## 2. DNS first

At the provider that serves `horizonwebcraft.com`:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| A | `api-voice` | `<instance public IP>` | 300 |

Verify from your machine **before** installing Caddy — Let's Encrypt validates
over the public DNS, and a stale record is the most common certificate failure:

```powershell
nslookup api-voice.horizonwebcraft.com
```

The answer must be the instance IP. If it is not, wait and re-check; do not
proceed.

## 3. Open the two firewalls

**a) OCI security list** — Networking → VCN → Security Lists → Default →
Add Ingress Rules:

| Source | Protocol | Port |
| --- | --- | --- |
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

Do **not** open `8000`. Caddy is the only door; the app binds `127.0.0.1`.

**b) The VM's own iptables** — Oracle images reject everything except SSH even
after the security list is updated:

```bash
sudo iptables -L INPUT -n --line-numbers
# find the REJECT line (usually 6), then:
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 4. Install Python 3.12, uv, Caddy

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv curl git unzip

curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc && uv --version

sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null
sudo apt-get update && sudo apt-get install -y caddy
```

Caddy now answers on port 80 with a placeholder — that alone proves both
firewalls are open.

## 5. Upload the code

From PowerShell on your machine:

```powershell
ssh ubuntu@<IP> "mkdir -p ~/voice-agent"
scp -r app db knowledge_base deploy pyproject.toml uv.lock .env.example README.md ubuntu@<IP>:~/voice-agent/
```

Never upload `.venv` (built on the server), `.env` (create it there) or
`__pycache__`. The `deploy/` folder matters: it contains the systemd unit and the
Caddyfile.

Alternative for a GUI SFTP client: `voice-agent-backend.zip` in the same folder
as this repository, unzip on the server into `~/voice-agent`.

## 6. Install dependencies

```bash
cd ~/voice-agent
uv sync --frozen --no-dev
.venv/bin/python -c "import fastembed, langchain_core; print('deps ok')"
```

1–3 minutes; `onnxruntime` is the large download. `--frozen` installs exactly
the versions in `uv.lock`.

## 7. Write `.env`

```bash
cd ~/voice-agent
cp .env.example .env
openssl rand -hex 24          # copy this into API_KEY and keep it for Vercel
chmod 600 .env
nano .env
```

```bash
ENVIRONMENT=production
LOG_LEVEL=INFO
API_KEY=<the 48-character hex string>
ALLOWED_ORIGINS=https://voice.horizonwebcraft.com

SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<sb_secret_... key>
QDRANT_URL=https://<cluster>.<region>.cloud.qdrant.io:6333
QDRANT_API_KEY=<key>
QDRANT_COLLECTION=clinic_knowledge

LLM_ORDER=gemini,deepseek
GEMINI_API_KEY=<key>
GEMINI_MODEL=gemini-3.5-flash-lite
DEEPSEEK_API_KEY=

RETRIEVAL_TOP_K=5
RETRIEVAL_MIN_SCORE=0.5

# Deliberately empty: the demo is text-only so it spends no ElevenLabs credits.
ELEVENLABS_API_KEY=
```

`DOMAIN` is only read by the Docker compose path; leave it out here.

## 8. Verify the app can reach its dependencies

```bash
cd ~/voice-agent
.venv/bin/python -m app.database.test_connection
.venv/bin/python -m app.rag.ingest
```

Expected: `done: 78 chunks in 10 files`. Ingestion is idempotent — it replaces
each file's points and writes the same deterministic IDs.

## 9. Run it under systemd

```bash
sudo cp deploy/gp-voice-agent.service /etc/systemd/system/
sudo sed -i 's/\r$//' /etc/systemd/system/gp-voice-agent.service
sudo systemctl daemon-reload
sudo systemctl enable --now gp-voice-agent
systemctl status gp-voice-agent --no-pager
```

Local check, before any TLS is involved:

```bash
curl -s http://127.0.0.1:8000/health
```

`{"status":"ok",...,"configured":{"supabase":true,"qdrant":true,"gemini":true}}`
means the process is up and every dependency key is present.

## 10. HTTPS with Caddy

```bash
cd ~/voice-agent
sudo sed 's/{$DOMAIN}/api-voice.horizonwebcraft.com/' deploy/Caddyfile.native \
  | sudo tee /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
journalctl -u caddy -n 30 --no-pager     # "certificate obtained successfully"
```

```bash
curl https://api-voice.horizonwebcraft.com/health
```

## 11. Prove the API from your machine

```powershell
$key = "<API_KEY from .env>"
Invoke-RestMethod https://api-voice.horizonwebcraft.com/documents | Measure-Object
Invoke-RestMethod -Method Post https://api-voice.horizonwebcraft.com/chat `
  -ContentType "application/json" -Headers @{ "X-API-Key" = $key } `
  -Body '{"message":"How long does a repeat prescription take?"}'
```

`/documents` must work **without** the key; `/chat` must return `401` without it.

## 12. Deploy the frontend to Vercel

1. Push the repository to GitHub (or import the folder into Vercel).
2. Vercel → New Project → root directory **`web`**, framework Next.js.
3. Environment variables (Production **and** Preview):

   | Name | Value |
   | --- | --- |
   | `API_BASE_URL` | `https://api-voice.horizonwebcraft.com` |
   | `BACKEND_API_KEY` | the same `API_KEY` as the server |

   Both are server-only. Do **not** prefix them with `NEXT_PUBLIC_`.
4. Settings → Domains → add `voice.horizonwebcraft.com`, then create the record
   Vercel shows (usually `CNAME voice → cname.vercel-dns.com`).

## 13. Smoke test the demo

Open `https://voice.horizonwebcraft.com`:

- The document list shows 10 documents and 78 indexed passages.
- The sections render as headings, lists and tables.
- Ask *"What time do you close on a Tuesday?"* → answer cites **Opening hours**;
  click the citation → the left pane jumps to and highlights that section.
- Ask *"What is the capital of France?"* → "not in the practice information"
  badge, no invented answer.

## 14. Day-to-day

```bash
journalctl -u gp-voice-agent -f            # logs
sudo systemctl restart gp-voice-agent      # after editing .env
```

Update the code: re-upload `app/` (or `git pull`), then

```bash
cd ~/voice-agent && uv sync --frozen --no-dev && sudo systemctl restart gp-voice-agent
```

Re-ingest only when `knowledge_base/` changes:

```bash
cd ~/voice-agent && .venv/bin/python -m app.rag.ingest
```

Rotate the API key: `openssl rand -hex 24` → `.env` → restart → update
`BACKEND_API_KEY` in Vercel → redeploy.

---

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `curl` to the domain times out | Security list **or** iptables; check both |
| Caddy: `no such host`, `DNS problem` | A record missing/stale; `nslookup`, wait, reload |
| 502 from Caddy | Service down: `systemctl status gp-voice-agent` |
| Service restarts every 5s | Read `journalctl`; usually a bad `.env` value |
| `ModuleNotFoundError: app` | Wrong `WorkingDirectory` in the unit |
| `/chat` returns 503 | `/health` → `configured` names the missing integration |
| Frontend says "Cannot reach the API" | `API_BASE_URL` wrong or missing trailing HTTPS |
| Frontend 401 | `BACKEND_API_KEY` differs from the server's `API_KEY` |
| First answer takes ~6s | Cold model start; later turns ~2–3s |
| `uv sync` killed | 1 GB shape; use `VM.Standard.A1.Flex` |
