# MatchLambda — Development Specification

MatchLambda is a planned football probability and market-comparison product. This directory contains specifications, a proposed PostgreSQL schema and a **local-development** Compose template. It contains no application code, Dockerfiles, migrations or deployed service. Specification revision: **1.3.0**.

## First release

EPL only, pre-match regulation-time 1X2, Dixon–Coles probabilities, timestamped bookmaker comparisons and NOWPayments access passes. Source authorization and real sample coverage are prerequisites; naming a provider does not establish access.

## Document ownership

| File | Authority |
| --- | --- |
| `docs/01_PRD_PRODUCT_REQUIREMENTS.md` | Scope, user outcomes and non-goals |
| `docs/02_TECH_ARCHITECTURE_SPEC.md` | Service boundaries and deployment assumptions |
| `docs/03_DATABASE_SCHEMA.sql` | Proposed storage fields and constraints |
| `docs/04_ALGORITHMS_MATH_SPEC.md` | Formulas, numerical conventions and evaluation |
| `docs/05_API_SPECIFICATION.md` | Routes, payloads, access rules and errors |
| `docs/06_DATA_PIPELINE_ETL.md` | Source eligibility, mapping and timestamps |
| `docs/07_CRYPTO_PAYMENT_INTEGRATION.md` | Catalog, payment verification and entitlement transitions |
| `docs/08_SPRINT_IMPLEMENTATION_PLAN.md` | Work order and acceptance gates |
| `AI_DEV_PROMPT_GEMINI.md` | Coding-agent workflow referencing those contracts |
| `docker-compose.yml`, `.env.example` | Local service configuration |

If documents disagree, correct the conflict at its source before implementation; do not build compatibility code for conflicting drafts.

## Local setup status

Copy `.env.example` to a private `.env`, replace the database and JWT placeholders, then run `docker compose config --quiet`. Do not commit `.env`; add it to ignore rules when creating the application repository.

`docker compose up -d db redis` starts local infrastructure only. `docker compose up --build` is **not yet runnable**: `backend/`, `frontend/` and their Dockerfiles must first be implemented. Introduce the proposed SQL through Alembic once the backend exists; do not execute both a database init script and the same migration.

Production deployment is a later gate. Do not expose this development Compose configuration publicly. Read the PRD and ETL prerequisites, then follow the implementation plan. API examples are synthetic, not actual fixtures, quotes or evidence of performance.
