# Deploying to Oracle Cloud (no Docker)

Target: an Always Free ARM instance running the API from a `uv` virtualenv under
systemd, with Caddy terminating HTTPS. Supabase (database) and Qdrant Cloud
(vectors) stay external, so the VM holds no state except `.env`.

A Docker version of the same deployment is in `ORACLE-DOCKER.md`. Pick one, not
both.

Estimated time: 25–40 minutes, mostly DNS and `uv sync`.

## 0. What you need

- Oracle Cloud account (Always Free tier)
- A domain you can edit DNS for
- Your code reachable from the VM: a GitHub repo, or `scp`/SFTP upload

## 1. Create the instance

Console → Compute → Instances → Create instance.

| Setting | Value |
| --- | --- |
| Image | **Canonical Ubuntu 24.04** |
| Shape | `VM.Standard.A1.Flex` — 2 OCPU / 12 GB is plenty |
| Boot volume | 50 GB |
| SSH key | upload or generate, keep the private key |

**Use Ubuntu 24.04, not 22.04.** 24.04 ships Python 3.12, which is what
`pyproject.toml` requires. On 22.04 you would need the deadsnakes PPA first.

Note the public IP.

## 2. Open the firewall — two places

Both layers must allow traffic; this is where most Oracle deployments fail.

**a) Oracle's security list**

Networking → Virtual Cloud Networks → your VCN → Security Lists → Default →
Add Ingress Rules:

| Source | Protocol | Destination port |
| --- | --- | --- |
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

Port 22 is already open. Do not open 8000 — Caddy is the only entry point.

**b) The instance's own iptables**

Oracle's Ubuntu images ship a REJECT rule that drops everything except SSH, even
after the security list is updated. On the VM:

```bash
sudo iptables -L INPUT -n --line-numbers
```

Find the line number of the `REJECT` rule (usually 6), then insert before it:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

Without the save, the rules vanish on reboot.

## 3. Install Python, uv and Caddy

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv git curl

# uv, into ~/.local/bin
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version

# Caddy (official apt repo)
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null
sudo apt-get update
sudo apt-get install -y caddy
```

Caddy starts automatically and serves a placeholder page on port 80, which is
itself a useful check that the firewall is open.

## 4. Get the code onto the server

Preferred: push to GitHub from your machine, then clone on the VM.

```bash
# on your machine
git remote add origin git@github.com:<you>/voice-agent.git
git push -u origin master

# on the VM
git clone https://github.com/<you>/voice-agent.git
cd voice-agent
```

No repo yet? Upload instead, excluding `.venv`, `.env` and `__pycache__`:

```powershell
# from Windows PowerShell — create the directory first, scp will not make it
ssh ubuntu@<ip> "mkdir -p ~/voice-agent"
scp -r app db knowledge_base pyproject.toml uv.lock .env.example ubuntu@<ip>:~/voice-agent/
```

A GUI SFTP client works the same way: keep the directory structure and skip
`.venv` (the server builds its own), `.env` (create it there) and
`__pycache__`.

You need `pyproject.toml` **and** `uv.lock` — `uv sync` uses the lock file to
install exactly the versions your tests ran against.

## 5. Create the virtualenv

```bash
cd ~/voice-agent
uv sync --frozen --no-dev
```

`--frozen` refuses to modify the lock file, so the server installs what you
tested. `--no-dev` skips pytest and ruff. Expect 1–3 minutes; `onnxruntime` is
the large download.

Verify the interpreter:

```bash
.venv/bin/python -c "import fastembed, langchain_core; print('deps ok')"
```

## 6. Configure `.env`

```bash
cp .env.example .env
openssl rand -hex 24          # use as API_KEY
nano .env
chmod 600 .env                # keys readable only by your user
```

Required values:

```bash
ENVIRONMENT=production
API_KEY=<the random value>
ALLOWED_ORIGINS=https://clinic.yourdomain.com

SUPABASE_URL=...
SUPABASE_KEY=...              # service_role / sb_secret_ key
QDRANT_URL=...
QDRANT_API_KEY=...
QDRANT_COLLECTION=clinic_knowledge

GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash-lite
LLM_ORDER=gemini,deepseek

RETRIEVAL_TOP_K=5
RETRIEVAL_MIN_SCORE=0.5
```

`pydantic-settings` reads `.env` from the working directory, so the service must
run with `WorkingDirectory=/home/ubuntu/voice-agent` — which the unit file does.

## 7. Index the knowledge base

```bash
cd ~/voice-agent
.venv/bin/python -m app.rag.ingest
```

Expected: `done: 78 chunks in 10 files`. The embedding model downloads on first
use (~50 MB) into `FASTEMBED_CACHE_PATH`. Re-run this after editing anything in
`knowledge_base/`, adding `--rebuild` if you change embedding models.

## 8. Install the systemd service

```bash
sudo cp deploy/gp-voice-agent.service /etc/systemd/system/
# If you uploaded the files from Windows rather than cloning, strip CRLF:
sudo sed -i 's/\r$//' /etc/systemd/system/gp-voice-agent.service
sudo systemctl daemon-reload
sudo systemctl enable --now gp-voice-agent
systemctl status gp-voice-agent --no-pager
journalctl -u gp-voice-agent -n 30 --no-pager
```

The API now listens on `127.0.0.1:8000` only. Quick local check:

```bash
curl -s http://127.0.0.1:8000/health
```

If the service restarts in a loop, `journalctl` shows why — usually a missing env
value or `ProtectHome` blocking the repo. Comment out `ProtectSystem` and
`ProtectHome` in the unit if so.

## 9. Point DNS and enable HTTPS

At your DNS provider:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| A | clinic | `<instance public IP>` | 300 |

Wait until it resolves **before** touching Caddy, or certificate issuance fails:

```bash
dig +short clinic.yourdomain.com
```

Then install the site config, substituting your domain:

```bash
cd ~/voice-agent
sudo sed "s/{\$DOMAIN}/clinic.yourdomain.com/" deploy/Caddyfile.native \
  | sudo tee /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
journalctl -u caddy -n 20 --no-pager     # look for "certificate obtained successfully"
```

Caddy renews the certificate automatically.

## 10. Verify

```bash
curl https://clinic.yourdomain.com/health
# {"status":"ok",...,"configured":{"supabase":true,"qdrant":true,"gemini":true,...}}

curl -X POST https://clinic.yourdomain.com/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message":"How long does a repeat prescription take?"}'
```

`401` = missing or wrong key. `503` = a dependency is unconfigured; `/health`
names it without leaking values.

## 11. Day-to-day

```bash
journalctl -u gp-voice-agent -f              # follow logs
sudo systemctl restart gp-voice-agent        # after editing .env
sudo systemctl stop gp-voice-agent           # stop
```

Deploy an update:

```bash
cd ~/voice-agent
git pull
uv sync --frozen --no-dev
sudo systemctl restart gp-voice-agent
```

Rotating the API key: edit `.env`, restart the service, update the frontend.

## Costs

`VM.Standard.A1.Flex` up to 4 OCPU / 24 GB is Always Free, as is a 50 GB boot
volume. Caddy and Let's Encrypt are free. Embeddings run locally. The only
recurring cost is the model API.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `uv sync` fails on `onnxruntime` | Out of memory on a 1 GB shape; use A1.Flex or add swap |
| `ModuleNotFoundError: app` | Service started from the wrong directory; check `WorkingDirectory` |
| 502 from Caddy | App not listening; `systemctl status gp-voice-agent` |
| Caddy `no such host` | DNS not propagated; wait, then `systemctl reload caddy` |
| ACME connection refused | Ports 80/443 blocked — check both the security list and `iptables` |
| First request takes ~6s | Gemini cold start; later turns are ~2.5s |
| Container-like restarts every 5s | systemd `Restart=always` doing its job; read `journalctl` |
