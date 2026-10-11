# Deployment

Production is one always-on host plus Cloudflare Pages for the frontend.

```
browser ──> Cloudflare Pages (static SPA, free, edge-cached)
                │
                │  https://api.<domain>/v1/*
                ▼
        one always-on host  (docker-compose.prod.yml)
          caddy           ── TLS + reverse proxy, the only published ports
          api             ── uvicorn, no --reload
          celery_worker   ── always on, --concurrency=2
          celery_beat     ── always on
          db / redis      ── compose network only, no published ports
```

**Why the frontend is separate.** It is a static SPA: no route handlers, no
server actions, no `next/headers`, no middleware, no ISR, no dynamic routes, and
no `next/image`. Nothing needs a Node server, so Pages serves it from the edge
and the host never renders HTML.

**Why the backend is not on Cloudflare Workers.** The API imports numpy, scipy
and asyncpg, which measured **~127 MB peak RSS before serving a single request**
against Workers' **128 MB per-isolate** limit. Those are native C extensions and
`asyncpg` needs a raw TCP socket; neither is available in the Pyodide runtime.
Celery's `task_time_limit` is 30 minutes, far past Workers' CPU budget. Cloudflare
Containers could run the image, but an always-on worker fights their
request-driven, sleep-when-idle design.

---

## 1. Host

Oracle Cloud **Always Free**, shape `VM.Standard.A1.Flex`, **2 OCPU / 12 GB**,
Ubuntu 24.04. Free for the life of the account, and sized well above the ~1.5 GB
the whole stack is expected to use.

Two caveats, both from Oracle's documentation:

- **Idle reclamation.** An Always Free instance may be reclaimed if, over a
  7-day window, CPU 95th percentile, network *and* memory are all below 20%.
  This workload keeps memory above that threshold, but never treat the host as
  the only copy of anything — see §5.
- **`out of host capacity`** while creating the instance is routine for Always
  Free ARM. Retry, try another availability domain, or upgrade to Pay As You Go
  (Always Free resources stay free; only usage above the limits is billed).

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"          # log out and back in for the group
git clone https://github.com/500wango/matchlambda.git /opt/matchlambda
cd /opt/matchlambda
```

## 2. Datasets

`data/` is gitignored, so a fresh clone contains none of it. Copy it from your
development machine:

```bash
rsync -av --delete data/ user@host:/opt/matchlambda/data/
```

Without it, seeding and backtests report `DATA_UNAVAILABLE` — deliberate
behaviour, but easy to mistake for a broken deployment.

## 3. DNS and TLS

Create an **A record for `DOMAIN` pointing at the host's public IP before the
first start**. Caddy validates ownership over the ACME HTTP-01 challenge on port
80, and each failed challenge counts against Let's Encrypt rate limits.

Open 80 and 443 both in the Oracle security list (VCN) *and* on the host.
Oracle's Ubuntu images ship a `REJECT` rule that blocks traffic the VCN allows;
the usual fix is to insert the ACCEPT rules above it:

```bash
sudo iptables -L INPUT --line-numbers      # confirm the REJECT rule's position
sudo iptables -I INPUT 6 -p tcp --dport 80  -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

If you do not own a domain yet, DuckDNS provides a free subdomain and Caddy's
HTTP-01 challenge works against it.

## 4. First deploy

```bash
cp deploy/env.prod.example .env
$EDITOR .env                              # JWT_SECRET: openssl rand -base64 48
./deploy/deploy.sh
curl -fsS https://api.<domain>/health     # {"status":"healthy",...}
```

`api` runs `alembic upgrade head` on start (`RUN_MIGRATIONS=1`); the celery
services set it to `0` so they cannot race it. To create the first
administrator, set `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` in `.env`
before the first `up` — they are consumed only while the database has no
administrators.

## 5. Backups

```bash
crontab -e
23 3 * * * /opt/matchlambda/deploy/backup.sh >> /var/log/matchlambda-backup.log 2>&1
```

Set `R2_REMOTE` in `.env` to an rclone remote (e.g. `r2:matchlambda-backups`) so
dumps leave the host. Without it `backup.sh` warns on stderr and keeps local
copies only, which do not survive losing the instance.

Restore:

```bash
gunzip -c backups/matchlambda_<stamp>.sql.gz \
  | docker compose -f docker-compose.prod.yml exec -T db \
      psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

## 6. Frontend on Cloudflare Pages

`NEXT_PUBLIC_API_URL` is **required**: without it `lib/api.ts` falls back to
`${window.location.origin}/v1`, which on Pages resolves to the static bundle and
404s.

```bash
NEXT_PUBLIC_API_URL=https://api.<domain>/v1 npm --prefix frontend run build:static
```

`build:static` exports to `frontend/out/` and writes `out/_headers`. Cloudflare
Pages has no Node server, so the CSP that `next.config.js` sends as a response
header is emitted as a file instead — both are rendered by the same
`frontend/lib/csp.cjs`, so the two cannot drift.

On Pages: build command `npm run build:static`, output directory `out`, and
`NEXT_PUBLIC_API_URL` set in the project environment.

Then set `APP_ORIGIN` in `.env` to the Pages URL and re-run `./deploy/deploy.sh`.
Until you do, the browser app cannot reach the API (the webhook still works,
which makes this look like a frontend bug).

## 7. Operating notes

**Client IP behind the proxy.** `TRUSTED_PROXY_HOPS=1` and
`TRUSTED_PROXY_CIDRS=${COMPOSE_SUBNET}` are set in `docker-compose.prod.yml`.
Both must stay correct: too low and the rate limiter sees Caddy's address and
buckets every client together, so one abusive client can lock out everyone; too
high and `X-Forwarded-For` becomes client-controlled and spoofable. `COMPOSE_SUBNET`
also pins the compose network, so the CIDR names a value that cannot drift.

**Celery concurrency.** Set to `2` for 2 vCPUs. The numpy/scipy tasks are
CPU-bound, so extra children add memory pressure without throughput. (The dev
stack's default of 12 is fine for copy-on-write forks on a workstation, not
here.)

**Deploys** are `git pull` based — `./deploy/deploy.sh` pulls, rebuilds, restarts
and prints the applied Alembic revision. The repository is public; the
code-review reports under `docs/CODE_REVIEW_REPORT*.md` are gitignored and stay
local by design.

**Logs:**

```bash
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml ps
```

**Docs endpoints** are off (`SHOW_DOCS=false`) and Caddy 404s everything outside
`/v1/*` and `/health`. To debug against the schema temporarily, set
`SHOW_DOCS=true`, add a `handle /docs*` block to the Caddyfile, and remove both
afterwards.
