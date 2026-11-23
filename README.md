# StreamAudio Server

Low-latency live audio stack: **MediaMTX (WebRTC WHIP/WHEP)** + **admin panel** + **Postgres**, deployed with Docker behind **Caddy** (automatic HTTPS).

## Architecture

| Service   | Role |
|-----------|------|
| `caddy`   | TLS termination (`https://your-subdomain`), reverse proxy |
| `admin`   | React admin SPA (login, publishers, live listen) |
| `api`     | FastAPI auth API, publisher CRUD, MediaMTX auth webhook |
| `mediamtx`| WebRTC ingest (WHIP) / play (WHEP) |
| `postgres`| Admins + publisher credentials (hashed) |

**Access model**

- No public registration. Bootstrap one admin via env, then sign in on the panel.
- Admin creates **publisher** credentials (devices that send audio).
- Only the **admin** can listen (short-lived WHEP listen tokens).
- Publish/read is denied unless MediaMTX’s HTTP auth webhook allows it.

## Requirements

- Linux VPS (or any Docker host) with ports **80**, **443**, and **8189/udp** (WebRTC media) open
- Docker Engine + Docker Compose v2
- DNS `A`/`AAAA` for your subdomain pointing at the server (e.g. `stream.example.com`)

## Deploy

```bash
cd Server
cp .env.example .env
# Edit .env — set DOMAIN, passwords, JWT_SECRET, WEBRTC_ADDITIONAL_HOSTS
docker compose up -d --build
```

### SSL / reverse proxy

**This stack does not bind host :80/:443 by default** (avoids fighting aaPanel/nginx).

Docker publishes locally:

| Service | Host address |
|---------|----------------|
| Admin UI | `127.0.0.1:8080` |
| API | `127.0.0.1:3000` |
| MediaMTX WHIP/WHEP | `127.0.0.1:8889` |
| WebRTC media | `8189/udp` + `8189/tcp` |

Point your existing HTTPS vhost at those ports. Example config: [`deploy/nginx-st.fifa2012.ir.conf`](deploy/nginx-st.fifa2012.ir.conf).

Critical: `location /api/` must proxy to `127.0.0.1:3000`. If only `/` goes to admin, login returns **502**.

Optional all-in-one Caddy (only if nothing else uses 80/443):

```bash
docker compose --profile caddy up -d
```

Quick check that API is reachable on the host:

```bash
curl -sS http://127.0.0.1:3000/api/health
# {"ok":true}
```

Open `https://YOUR_DOMAIN`, sign in with `ADMIN_BOOTSTRAP_USER` / `ADMIN_BOOTSTRAP_PASSWORD`, then create a publisher.

### `.env` checklist

| Variable | Purpose |
|----------|---------|
| `DOMAIN` | Public hostname (Let’s Encrypt) |
| `ACME_EMAIL` | Optional ACME contact email |
| `ADMIN_BOOTSTRAP_*` | First admin (only if DB has no admins) |
| `JWT_SECRET` | Session + listen-token signing (≥32 random chars) |
| `POSTGRES_*` / `DATABASE_URL` | Postgres credentials (must match) |
| `WEBRTC_ADDITIONAL_HOSTS` | Usually same as `DOMAIN` (ICE candidates) |
| `ADMIN_LOGIN_IP_ALLOWLIST` | Optional comma-separated IPs for login |
| `COOKIE_SECURE` | `true` in production (HTTPS) |

## Publisher credentials (for a future Android / WHIP client)

After **Create access** in the admin panel (secret shown once):

- **WHIP URL:** `https://DOMAIN/live/{publisherId}/whip`
- **Auth:** `Authorization: Bearer username:secret`  
  or HTTP Basic `username` / `secret`

## Admin live listen

Open **Listen** on a publisher → **Start listening**. The panel fetches a short-lived listen token and connects via **WHEP** with an audio visualizer.

## Security notes

- TLS via Caddy for UI, API, and WHIP/WHEP signaling
- Argon2id password/secret hashes in Postgres
- httpOnly `SameSite=Strict` session cookie + CSRF double-submit (`X-CSRF-Token`)
- MediaMTX HTTP ports are **not** published to the host (only via Caddy); UDP **8189** is published for WebRTC media
- No anonymous publish or play
- Rotate publisher secrets from the panel; revoke by Disable/Delete

## Local development (API + admin without TLS)

```bash
# Postgres (example)
docker run -d --name sa-pg -e POSTGRES_PASSWORD=dev -e POSTGRES_USER=stream -e POSTGRES_DB=streamaudio -p 5432:5432 postgres:16-alpine

cd api
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgres://stream:dev@localhost:5432/streamaudio
export JWT_SECRET=dev-secret-dev-secret-dev-secret
export ADMIN_BOOTSTRAP_USER=admin
export ADMIN_BOOTSTRAP_PASSWORD=adminadmin
export COOKIE_SECURE=false
export DOMAIN=localhost
uvicorn app.main:app --reload --port 3000

cd ../admin
npm install && npm run dev
# Vite proxies /api → localhost:3000
```

MediaMTX still needs to run (Compose or binary) for real WHIP/WHEP tests.

## Useful commands

```bash
docker compose logs -f api
docker compose logs -f mediamtx
docker compose ps
docker compose down
```

## Troubleshooting: login returns 502

`502` means Caddy reached the site but the **API container is down** (or still starting).

```bash
cd Server
docker compose ps
docker compose logs --tail=100 api
```

Common causes:

1. **Missing `.env`** — `cp .env.example .env` and fill values on the server.
2. **Wrong DB host in `DATABASE_URL`** — inside Docker use host `postgres`, not `localhost`. Prefer leaving `DATABASE_URL` empty and set only `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`.
3. **Empty `JWT_SECRET`** — API refuses to start.
4. **`$` in secrets** — Docker Compose interpolates `$`. Use `$$` for a literal dollar sign, or generate secrets without `$`.
5. Check logs: `docker compose logs --tail=200 api`

Rebuild after pulling fixes:

```bash
docker compose up -d --build --force-recreate
docker compose logs -f api
```

## Out of scope (this phase)

- Android WHIP publisher wiring
- Multi-listener user accounts
- TURN server (add if ICE fails behind strict NAT)
