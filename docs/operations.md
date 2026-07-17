# Operations runbook

How the Flux Calculation stack is deployed, operated, monitored, backed up, and
recovered. For the system design (components, data flow, trust boundaries) see
[`architecture.md`](architecture.md); for the CI/CD pipeline internals see the CI/CD
section of [`../report.md`](../report.md).

> **Secrets & privacy:** this runbook contains **no** credentials, private keys, or
> host IPs. Secrets live only in the untracked `.env` and `traefik/htpasswd` on the
> server. Never paste real keys or the access-gate password into any doc or log.

---

## 1. Where it runs

- **Live URL:** `https://flux-calculation.<domain>` (the production hostname is set by
  `DOMAIN` in the server's `.env`; DNS `A` record points at the VPS).
- **Host:** a single Linux VPS running Docker Engine + the Compose plugin.
- **Stack (root `docker-compose.yml`, project `flux-calculation`):** three containers
  on the shared `flux-net` bridge network, all `restart: always`:

  | Service | Image | Exposure | Role |
  |---|---|---|---|
  | `traefik` | `traefik:v3.5` | **host :80 + :443** | TLS edge (Let's Encrypt), routing, access gate |
  | `backend` | built (`python:3.14-slim`) | internal `:8000` only | FastAPI API under `/api` |
  | `frontend` | built (`nginx:alpine`) | internal `:80` only | React SPA + static assets |

  Traefik is the **only** service published to the host; the app containers are
  reachable only through it. Routing uses Traefik's **file provider**
  (`traefik/dynamic.yml`), not the Docker provider.

- **Companion stacks (separate Compose projects, documented in the server's root
  `CLAUDE.md`):**
  - **n8n** — the optional quality-check workflow, served at `…/<domain>/n8n`, reusing
    the Flux domain + cert. The app never depends on it being up.
  - **Uptime Kuma** — uptime/latency monitor, **localhost-only** (not publicly
    exposed); reach it over an SSH tunnel (see §6).

- **Persistent state (Docker named volumes):**

  | Volume | Contents | Backup priority |
  |---|---|---|
  | `flux-calculation_backend-data` | uploads + the SQLite DB (`/app/data`) | **critical** |
  | `flux-calculation_letsencrypt` | issued TLS certs (`acme.json`) | nice-to-have (re-issuable) |
  | `n8n_data` | n8n workflows + creds | important if n8n is used |
  | `uptime-kuma_uptime-kuma-data` | monitor config + history | nice-to-have |

---

## 2. Deploy

### Automatic (normal path)

A push that lands on **`main`** triggers GitHub Actions: `test.yml` runs the full
check suite, and only on success does `deploy.yml` SSH to the VPS and run the deploy
script with the **exact tested commit SHA**. The deploy is health-checked and rolls
back automatically on failure. Every run is auditable in the Actions log. Details,
required GitHub Secrets, and the one-time server key setup are in the CI/CD section of
[`../report.md`](../report.md).

### Manual (from the server)

```bash
cd /path/to/Flux-Calculation                 # the deploy path ($DEPLOY_PATH)
git fetch --all --prune
git checkout <good-sha>
export SENTRY_RELEASE=$(git rev-parse HEAD)   # tags monitoring to the running code
docker compose up -d --build --remove-orphans
```

`SENTRY_RELEASE` flows to both the backend env and the frontend build arg via Compose
interpolation. **Migrations are idempotent and run on backend startup**
(`create_db_and_tables` → `_run_lightweight_migrations`), so `up -d` applies them; no
separate migration step is needed.

### The deploy script

`infrastructure/deploy/deploy.sh` (installed on the server as
`/usr/local/bin/flux-deploy`) is the safe, rollback-capable entrypoint CI uses. It:

1. **Validates** the target ref (only a hex SHA or `origin/main` — injection-safe).
2. Records the current SHA, fetches, and checks out the target
   (untracked/git-ignored files like `.env` and `traefik/htpasswd` are preserved).
3. `SENTRY_RELEASE=<sha> docker compose up -d --build --remove-orphans`.
4. **Health-checks** backend + frontend container health, then the Traefik edge.
5. **Rolls back** to the previous SHA and redeploys if the health-check fails; exits
   non-zero so CI turns red.

You can run it by hand too: `sudo flux-deploy <sha>` (or `flux-deploy origin/main`).

---

## 3. Restart

```bash
cd /path/to/Flux-Calculation
docker compose restart backend            # one service
docker compose up -d                      # apply compose/.env changes (recreates as needed)
docker compose down && docker compose up -d   # full cycle (certs persist in the volume)
```

**Traefik dynamic config is a single-file bind-mount**, so `watch=true` does **not**
pick up in-place edits to `traefik/dynamic.yml` — after editing it (or `htpasswd`) you
must `docker restart flux-calculation-traefik-1` (~1–2 s proxy blip; certs persist).

---

## 4. Rollback

- **Automatic:** a failed post-deploy health-check inside `flux-deploy` checks out the
  previous SHA, redeploys, and re-checks (CI shows the failure). If the rollback also
  fails it exits `2` — manual intervention needed.
- **Manual:**

  ```bash
  cd /path/to/Flux-Calculation
  git checkout <last-good-sha>
  export SENTRY_RELEASE=$(git rev-parse HEAD)
  docker compose up -d --build
  # then verify (see §8 health checks)
  ```

Because tracked files are force-reset on checkout, any server-only config **must** be
git-ignored (like `.env`, `traefik/htpasswd`) or committed — never left as an
uncommitted edit to a tracked file, or a deploy/rollback will discard it.

---

## 5. Logs

Logging is structured (JSON) on both the **backend** (Python) and the **frontend**
(browser), and a single **correlation id** ties one browser action to its backend
request.

| | Backend | Frontend |
|---|---|---|
| Where | `backend/app/core/logging.py`, `middleware.py` | `frontend/src/lib/logger.ts` |
| Output | one JSON object per line → **stdout** (captured by Docker) | one JSON line → **browser console** |
| Level env var | `LOG_LEVEL` | `VITE_LOG_LEVEL` (build-time) |
| Format env var | `LOG_FORMAT` (`json` \| `console`) | always JSON string |
| Correlation id | `X-Request-ID` (in + echoed out) | generated per request, sent as `X-Request-ID` |
| Redaction | keys matching auth/token/cookie/… masked | same key list, masked before print |

### Backend log env vars (`.env`, read by pydantic-settings)

| Variable | Default | Meaning |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Minimum level: `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`. Unknown → `INFO`. |
| `LOG_FORMAT` | `json` | `json` (production) or `console` (human-friendly local dev). |
| `SLOW_REQUEST_MS` | `1000` | Requests slower than this (ms) also emit a `slow_request` **WARNING**. |

Backend record shape (extra fields become top-level keys; `exception`/`stack` added on
errors):

```json
{
  "timestamp": "2026-07-16T10:22:31.014Z", "level": "INFO", "logger": "app.request",
  "message": "request.completed", "request_id": "9f2c…", "method": "POST",
  "path": "/api/analyses", "status_code": 201, "duration_ms": 42.7
}
```

Events: `app.startup` (non-secret effective config, incl. a `llm_configured` boolean —
never the key), `app.shutdown`, `request.completed` (INFO 2xx/3xx, WARNING 4xx, ERROR
5xx), `slow_request` (WARNING), `request.failed` (ERROR + traceback).

### Redaction (both sides)

Any field whose **key** contains (case-insensitive) `authorization`, `cookie`,
`password`/`passwd`/`pwd`, `secret`, `token`, `api_key`/`apikey`, `access_key`,
`private_key`, `credential`, `session`, `auth` → value becomes `***REDACTED***`
(recurses into nested structures). **Request/response bodies and query strings are
never logged** — only method, path, status, and timing — so hand-typed field notes and
any personal data stay out of the logs. If a secret ever appears in a line, add the
missing key substring to `SENSITIVE_KEY_PARTS` in **both** `logging.py` and
`logger.ts` (with a test).

### Reading the logs

```bash
docker compose logs -f backend                                   # follow backend
docker compose logs --since 15m traefik                          # last 15 min of the proxy
docker compose logs backend | jq 'select(.level=="ERROR")'       # errors only
docker compose logs backend | jq 'select(.request_id=="9f2c…")'  # trace one request end-to-end
```

Grab the `request_id`/`correlationId` from a browser console line to trace that exact
click on the backend. To turn up verbosity temporarily, set `LOG_LEVEL=DEBUG` in `.env`
and `docker compose up -d backend`. **Nothing in the logs?** Check the service is up
(`docker compose ps`) and that `LOG_LEVEL` (or a baked-in `VITE_LOG_LEVEL`) isn't
above the level you expect.

### Docker log rotation

All services use the `json-file` driver with rotation (`max-size: 10m`, `max-file: 3`,
set via a YAML anchor in `docker-compose.yml`) — ≈ 30 MB max per container, so logs
can't fill the disk. Changing that block needs a container recreate (`up -d`).

---

## 6. Monitoring & alerts

- **Sentry (error/performance)** — SDK integrated in both apps but **off unless a DSN
  is set** (`SENTRY_DSN` backend / `VITE_SENTRY_DSN` frontend). When on it auto-captures
  unhandled exceptions, stamps the same `request_id` as the logs on every event, and
  redacts sensitive values. `SENTRY_RELEASE` = the git SHA, supplied at deploy time.
  Alert-rule proposals are in [`../report.md`](../report.md).
- **Uptime Kuma (availability/latency)** — runs on the VPS, **localhost-only**. Reach it
  over an SSH tunnel:

  ```bash
  ssh -L 3001:localhost:3001 <ssh-user>@<vps-host>   # then open http://localhost:3001
  ```

  Suggested monitors: `…/api/health` (keyword `"status":"ok"`), `…/` (200), `…/n8n/`
  (200), and a TLS-cert-expiry notification. **Note:** the public site is behind the
  access gate, so external checks against the public URL get `401` unless given the
  gate credentials (or point them at an unauthenticated health path if one is added).
- **Manual liveness:** `curl -s https://flux-calculation.<domain>/api/health` (behind
  the gate it returns `401` — that still proves Traefik + routing are up).

---

## 7. Backup & restore

The only **critical** state is the `backend-data` volume (uploads + SQLite DB). Raw
uploads are kept on disk per analysis, so any campaign is re-runnable from them.

**Back up a volume** (repeat per volume in §1):

```bash
docker run --rm \
  -v flux-calculation_backend-data:/d -v "$PWD":/b \
  alpine tar czf /b/backend-data-$(date +%F).tgz -C /d .
```

Do this **before every risky change** (schema, base-image bump, host migration). Store
the tarball off the box.

**Restore into a fresh volume:**

```bash
cd /path/to/Flux-Calculation
docker compose down                          # stop writers
docker volume create flux-calculation_backend-data
docker run --rm \
  -v flux-calculation_backend-data:/d -v "$PWD":/b \
  alpine sh -c "rm -rf /d/* && tar xzf /b/backend-data-YYYY-MM-DD.tgz -C /d"
docker compose up -d
```

The `letsencrypt` volume is worth backing up to avoid re-issuing certs, but Let's
Encrypt will simply re-issue on the next start if it's lost (DNS must resolve first).

---

## 8. Maintenance tasks

**Health check after any deploy/restart:**

```bash
docker compose ps                                              # all Up / healthy?
docker inspect -f '{{.State.Health.Status}}' $(docker compose ps -q backend)
curl -sk -o /dev/null -w '%{http_code}\n' https://flux-calculation.<domain>/api/health
# 200 = open, 401 = up behind the access gate; anything else = investigate
```

**Regenerate the API docs** (after any endpoint/schema change — CI enforces it's
current):

```bash
cd backend && . .venv/bin/activate && python scripts/export_openapi.py
# or from the repo root:  npm run docs:generate
npm run docs:validate     # redocly
npm run docs:lint         # markdownlint
```

**Rotate the access-gate password** (shared basic-auth in front of the whole site):

```bash
openssl passwd -apr1 'NEW_PASSWORD'          # copy the hash (never commit the plaintext)
# put  flux:<hash>  in traefik/htpasswd  (git-ignored), then:
docker restart flux-calculation-traefik-1    # single-file bind-mount → restart to load
```

Keep the plaintext only in the root-only key file on the server; distribute it out of
band. Per-person keys = add unique `user:hash` lines; revoke = remove that line.

**TLS certificates** renew automatically (Traefik/Let's Encrypt, HTTP-01) and persist
in the `letsencrypt` volume. If issuance fails, confirm DNS resolves to the VPS and
that no other host answers the ACME challenge, then check Traefik logs.

---

## 9. Incident response

1. **Triage.** `docker compose ps` and `docker compose logs --since 15m <svc>`. Check
   Uptime Kuma and (if configured) Sentry for the first error + its `request_id`.
2. **Read logs first** — never restart blindly. Match the `request_id` across frontend
   and backend to see the failing call. Confirm the symptom points at the service
   you're about to touch.
3. **Contain.** If a bad deploy is live, roll back (§4) — fastest path to green.
4. **If the edge is down** (`curl` to the domain fails at the TLS/connection layer):
   check `traefik` logs and that :80/:443 are bound; a `traefik/dynamic.yml` edit that
   didn't take needs a Traefik restart (§3).
5. **If data looks wrong/corrupt:** stop writers (`docker compose stop backend`),
   back up the current `backend-data` volume before any repair, then restore the last
   good backup (§7).
6. **After recovery:** capture what happened, the offending SHA, and the fix in
   [`../report.md`](../report.md); open a follow-up if a guard is missing.

**Known operational gotchas** — Traefik dynamic config / `htpasswd` need a Traefik
restart to load (single-file bind-mount); a deploy/rollback force-resets tracked files
(server-only config must be git-ignored or committed); external monitors against the
public URL get `401` because of the access gate.
