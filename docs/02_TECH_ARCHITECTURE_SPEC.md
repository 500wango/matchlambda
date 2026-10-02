# MatchLambda — Technical Architecture

## 1. Proposed topology

```text
Authorized EPL results/fixtures + validated bookmaker quotes
                         |
                  Celery worker <--- Celery beat / Redis
                         |
              PostgreSQL snapshots + model parameters
                         |
                 FastAPI REST API <--- NOWPayments IPN
                         |
                  Next.js client ---> Hosted checkout
```

Workers collect, fit and predict. Request handlers read stored results and enforce access; they do not train synchronously. Use one backend application and relational database, not a separate analytics microservice.

## 2. Service boundaries

| Service | Responsibility | Configuration |
| --- | --- | --- |
| `api` | Login, entitlement, read API, invoice creation, IPN | DB, JWT, CORS, NOWPayments |
| `celery_worker` | Import, mapping, snapshots, fitting, prediction | DB, Redis, The Odds API |
| `celery_beat` | Emit scheduled messages; one active scheduler | Redis |
| `web` | Render API data, login, checkout and order polling | Public app/API URLs |
| `db`, `redis` | Durable records; task broker | Local Compose settings |

Python uses FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic and NumPy/SciPy. The frontend uses Next.js App Router, React and TypeScript. Select supported compatible versions and lock dependencies during implementation. Use one client fetching approach. LightGBM/direct Betfair clients are out of scope.

Use UTC-aware timestamps. Task boundaries own DB transactions; mapping helpers do not commit. Retry using stable source identifiers and snapshot uniqueness. Persist predictions only after input and numerical checks; record failures as unavailable.

## 3. Local configuration

Compose is a local-development template with reload/source mounts. App Dockerfiles do not exist yet. DB and Redis have health checks; published ports bind loopback. The future web development Dockerfile must install dependencies and set its workdir for `npm run dev -- --hostname 0.0.0.0`.

`.env` supplies Compose substitution; services receive only explicitly listed variables. Build backend connection URLs from separate DB fields using SQLAlchemy's URL builder so reserved characters in passwords work. Blank provider settings disable the corresponding integration; reject invalid settings when it is enabled.

`NEXT_PUBLIC_API_URL` is browser-visible. Use client-side data requests in this release; do not reuse the browser's localhost URL for server rendering inside containers. Future production Next.js builds need public variables at build time too.

## 4. Auth and payment boundaries

- Use Argon2id password hashes, normalized email, JWT subject/expiry validation and API access rules. Tokens last 60 minutes; there is no refresh-token subsystem.
- Keep tokens in client memory; reload/expiry requires login. Do not put them in URLs. Restrict CORS to the app origin and rate-limit login/invoice creation before release.
- Provider/JWT secrets remain server-side. IPN uses provider signature authentication, not user JWT.
- Commit invoice crediting and user entitlement together. PostgreSQL, not a Redis lock, is the source of truth for payment idempotency.

## 5. Deployment gate

This local template is not a production deployment. Before launch, supply HTTPS ingress, exact public origins, non-reload commands, private DB/Redis networking, restart/health behavior, backups with a restore check, migrations and secrets. Verify actual provider/business/hosting eligibility and public webhook delivery. Region or proxy routing alone establishes no permission.

Select a target before adding deployment tooling. Interrupted collection must not overwrite earlier predictions or label old quotes fresh.
