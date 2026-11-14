# Deploying to Oracle Cloud

Target: an Always Free ARM instance running the API in Docker, behind Caddy for
HTTPS. Supabase (database) and Qdrant Cloud (vectors) stay external, so the VM
holds no state worth backing up except `.env`.

Estimated time from zero: 30–45 minutes, most of it DNS propagation and the first
image build.

## 0. What you need

- An Oracle Cloud account (Always Free tier is enough)
- A domain you can edit DNS for
- The repository on GitHub (private is fine — see step 4)

## 1. Create the instance

Console → Compute → Instances → Create instance.

| Setting | Value |
| --- | --- |
| Image | Canonical Ubuntu 24.04 |
| Shape | `VM.Standard.A1.Flex` — 2 OCPU / 12 GB is plenty |
| Boot volume | 50 GB |
| SSH key | upload or generate, keep the private key |

`VM.Standard.E2.1.Micro` (x86, 1 GB RAM) also works but the Docker build of
`onnxruntime` can run out of memory. If you must use it, add a 2 GB swap file
before building, or build the image elsewhere and push it to a registry.

Note the **public IP address**.

## 2. Open the firewall — two places

This is where most Oracle deployments fail. Both layers must allow traffic.

**a) Oracle's security list**

Networking → Virtual Cloud Networks → your VCN → Security Lists → Default →
Add Ingress Rules:

| Source | Protocol | Destination port |
| --- | --- | --- |
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

Port 22 is already open for SSH. Do **not** open 8000 — Caddy is the only thing
that should reach the app, over the private Docker network.

**b) The instance's own iptables**

Oracle's Ubuntu images ship with a REJECT rule that drops everything except SSH,
even after the security list is updated. On the VM:

```bash
sudo iptables -L INPUT -n --line-numbers
```

Find the line number of the `REJECT` rule (usually 6), then insert *before* it:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

If your REJECT rule is at a different line, use that number. Persisting matters:
without `netfilter-persistent save` the rules vanish on reboot.

## 3. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
docker compose version
```

## 4. Get the code

```bash
git clone https://github.com/<you>/voice-agent.git
cd voice-agent
```

For a private repo, create a read-only deploy key on GitHub (Settings → Deploy
keys) and clone over SSH:

```bash
ssh-keygen -t ed25519 -C "oracle-vm" -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub    # paste into GitHub deploy keys
GIT_SSH_COMMAND="ssh -i ~/.ssh/github_deploy" git clone git@github.com:<you>/voice-agent.git
```

## 5. Configure `.env`

```bash
cp .env.example .env
openssl rand -hex 24          # use this as API_KEY
nano .env
```

Required values:

```bash
DOMAIN=clinic.yourdomain.com          # no https://, no trailing slash
API_KEY=<paste the random value>
ENVIRONMENT=production
LOG_LEVEL=INFO
ALLOWED_ORIGINS=https://clinic.yourdomain.com   # or http://localhost:3000 while building the UI

SUPABASE_URL=...
SUPABASE_KEY=...                      # service_role / sb_secret_ key
QDRANT_URL=...
QDRANT_API_KEY=...
QDRANT_COLLECTION=clinic_knowledge

GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash-lite
LLM_ORDER=gemini,deepseek
```

`DOMAIN` is read by docker-compose and handed to Caddy. `API_KEY` is what stops
strangers spending your model quota — set it before the ports open.

## 6. Point DNS at the VM

At your DNS provider:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| A | clinic | `<instance public IP>` | 300 |

Verify before starting Caddy, otherwise certificate issuance fails and Caddy
retries with backoff:

```bash
dig +short clinic.yourdomain.com
```

## 7. Start

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f caddy
```

First build takes 3–8 minutes on ARM (`onnxruntime` is the slow part). Caddy will
log `certificate obtained successfully` once DNS and ports are correct.

## 8. Index the knowledge base

The collection is empty until you run ingestion. It runs inside the container so
it uses the same embedding model as the API:

```bash
docker compose exec api python -m app.rag.ingest
```

Expected: `done: 78 chunks in 10 files`. Re-run it after editing anything in
`knowledge_base/`, and add `--rebuild` if you change embedding models.

## 9. Verify

```bash
curl https://clinic.yourdomain.com/health
# {"status":"ok", ..., "configured":{"supabase":true,"qdrant":true,"gemini":true,...}}

curl -X POST https://clinic.yourdomain.com/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message":"How long does a repeat prescription take?"}'
```

A `401` means the header is missing or wrong. A `503` in the body means a
dependency is unconfigured — `/health` will name it without leaking values.

## 10. Day-to-day

```bash
docker compose logs -f api          # follow logs
docker compose restart api          # restart after editing .env
git pull && docker compose up -d --build   # deploy an update
docker compose down                 # stop (Caddy certificate is kept in a volume)
```

Rotating the API key is: edit `.env`, `docker compose up -d` (compose recreates
the container because the environment changed).

## Costs

`VM.Standard.A1.Flex` up to 4 OCPU / 24 GB is Always Free. A 50 GB boot volume
is within the free allowance. Caddy and Let's Encrypt are free. Your recurring
costs are the model API and nothing else — embeddings run locally, Supabase and
Qdrant are on their free tiers.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Caddy: `no such host` | DNS not propagated; wait and `docker compose restart caddy` |
| Caddy: `connection refused` on ACME | Ports 80/443 blocked — check **both** the security list and `iptables` |
| Site loads but `/chat` returns 502 | The API container is unhealthy; `docker compose logs api` |
| `502` with `insufficient_balance` in logs | The primary LLM provider is out of credit; fallback should have caught it |
| Slow first request after deploy | The embedding model is loading; the image bakes it in, so this should be a one-off |
| Container killed after a few minutes | Out of memory on a 1 GB shape; use A1.Flex or add swap |
| `docker compose` not found | Install `docker-compose-plugin`, not the old `docker-compose` package |
