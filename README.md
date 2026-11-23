# StreamAudio Server

Low-latency live audio stack: **MediaMTX (WebRTC WHIP/WHEP)** + **admin panel** + **Postgres**, deployed with Docker. TLS is usually terminated by an **existing** reverse proxy (Caddy / nginx / aaPanel). Optional in-compose Caddy is available if nothing else binds :80/:443.

## Architecture

| Service   | Role |
|-----------|------|
| `admin`   | React admin SPA (login, publishers, live listen) |
| `api`     | FastAPI auth API, publisher CRUD, MediaMTX auth webhook |
| `mediamtx`| WebRTC ingest (WHIP) / play (WHEP) |
| `postgres`| Admins + publisher credentials (hashed) |
| `caddy`   | Optional TLS (Compose profile `caddy` only) |

**Access model**

- No public registration. Bootstrap one admin via env, then sign in on the panel.
- Admin creates **publisher** credentials (devices that send audio).
- Only the **admin** can listen (short-lived WHEP listen tokens).
- Publish/read is denied unless MediaMTX’s HTTP auth webhook allows it.

## Requirements

- Linux VPS (or any Docker host) with ports **80**, **443**, and **8189/udp** (WebRTC media) open
- Docker Engine + Docker Compose v2
- DNS `A`/`AAAA` for your subdomain pointing at the server (e.g. `st.fifa2012.ir`)

## Deploy

```bash
cd Server
cp .env.example .env
# Edit .env — set DOMAIN, passwords, JWT_SECRET, WEBRTC_ADDITIONAL_HOSTS
docker compose up -d --build
./deploy/verify.sh
```

Compose project name is fixed to **`streamaudio`** (network `streamaudio_internal`). Containers always look like `streamaudio-api-1`, with stable aliases `streamaudio-api`, `streamaudio-admin`, `streamaudio-mediamtx`.

### SSL / reverse proxy (pick one)

**This stack does not bind host :80/:443 by default** (avoids fighting an existing Caddy/nginx).

Docker publishes locally:

| Service | Host address |
|---------|----------------|
| Admin UI | `127.0.0.1:8080` |
| API | `127.0.0.1:3000` |
| MediaMTX WHIP/WHEP | `127.0.0.1:8889` |
| WebRTC media | `8189/udp` + `8189/tcp` |

#### A) Existing Caddy **container** already on :80/:443 (recommended for st.fifa2012.ir)

Do **not** run `--profile caddy`.

1. `docker compose up -d --build`
2. `chmod +x deploy/*.sh && ./deploy/wire-existing-caddy.sh server-caddy-1`
3. Replace that Caddy’s site block with [`deploy/existing-docker-caddy.Caddyfile`](deploy/existing-docker-caddy.Caddyfile)  
   Upstream names must be **`streamaudio-api` / `streamaudio-admin` / `streamaudio-mediamtx`** — not bare `api` / `admin` / `mediamtx` (those collide with other Compose projects and cause **502 on login**).
4. The host path bind-mounted as the Caddyfile must be a **real file**. If it is missing, Docker may create a **directory** and Caddy will refuse to start.
5. `docker restart server-caddy-1 && ./deploy/verify.sh`

#### B) Host nginx / aaPanel

Use [`deploy/nginx-st.fifa2012.ir.conf`](deploy/nginx-st.fifa2012.ir.conf).  
`location /api/` **must** proxy to `127.0.0.1:3000`.

#### C) Host Caddy (not in Docker)

Use [`deploy/existing-host-caddy.Caddyfile`](deploy/existing-host-caddy.Caddyfile) (`127.0.0.1:3000` / `8080` / `8889`).

#### D) Nothing else on :80/:443

```bash
docker compose --profile caddy up -d --build
```

Quick local check:

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
| `POSTGRES_*` | Postgres credentials |
| `WEBRTC_ADDITIONAL_HOSTS` | Usually same as `DOMAIN` (ICE candidates) |
| `ADMIN_LOGIN_IP_ALLOWLIST` | Optional comma-separated IPs for login |
| `COOKIE_SECURE` | `true` in production (HTTPS) |

## Publisher credentials (for a future Android / WHIP client)

After **Create access** or **Rotate** in the admin panel (secret shown once):

- **WHIP URL:** `https://DOMAIN/live/{publisherId}/whip`
- **Auth:** `Authorization: Bearer username:secret`  
  or HTTP Basic `username` / `secret`
- **QR payload** (JSON, scan with the Android app):

```json
{
  "v": 1,
  "type": "streamaudio.publish",
  "username": "device1",
  "secret": "<shown-once>",
  "whipUrl": "https://DOMAIN/live/{publisherId}/whip"
}
```

## Admin live listen

Open **Listen** on a publisher → **Start listening**. The panel fetches a short-lived listen token and connects via **WHEP** with an audio visualizer.

## Security notes

- TLS at the edge reverse proxy for UI, API, and WHIP/WHEP signaling
- Argon2id password/secret hashes in Postgres
- httpOnly `SameSite=Strict` session cookie + CSRF double-submit (`X-CSRF-Token`)
- API / admin / MediaMTX HTTP are bound to **127.0.0.1** only (not the public interface); UDP/TCP **8189** is published for WebRTC media
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
./deploy/verify.sh
docker compose down
```

## Troubleshooting: login returns 502

`502` means the public reverse proxy cannot reach the **API** (API may still be healthy inside Docker).

```bash
cd Server
docker compose ps
curl -sS http://127.0.0.1:3000/api/health || echo "host cannot reach API"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -iE 'caddy|stream'
./deploy/verify.sh
```

Common causes:

1. **Another Caddy owns :80/:443** and still proxies to bare `api:3000` — that DNS name hits the *wrong* Compose project. Wire the network and use aliases: `./deploy/wire-existing-caddy.sh server-caddy-1` + [`deploy/existing-docker-caddy.Caddyfile`](deploy/existing-docker-caddy.Caddyfile).
2. **Missing Caddyfile bind-mount on the host** — path must be a file; a missing path becomes a directory and Caddy fails to start.
3. **Do not run two Caddies** — skip `--profile caddy` when `server-caddy-1` (or similar) already binds 80/443.
4. **Missing `.env`** — `cp .env.example .env` and fill values.
5. **Wrong DB host** — inside Docker use `postgres`, not `localhost`.
6. **Empty `JWT_SECRET`** or bare `$` in secrets (Compose interpolates `$`; use `$$`).

Rebuild after pulling fixes:

```bash
docker compose up -d --build --force-recreate
./deploy/verify.sh
```

### MediaMTX: `unknown field "webrtcAllowOrigins"`

Pinned image `bluenviron/mediamtx:1.12.3` expects singular `webrtcAllowOrigin` (already set in `mediamtx/mediamtx.yml`).

```bash
docker compose up -d --force-recreate mediamtx
docker compose logs --tail=20 mediamtx
```

## Out of scope (this phase)

- Android WHIP publisher wiring
- Multi-listener user accounts
- TURN server (add if ICE fails behind strict NAT)
