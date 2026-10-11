# MatchLambda — Football Probability & Market Intelligence Engine

MatchLambda is a football probability and market-comparison product. This repository contains the complete application codebase: a FastAPI backend, Next.js 14 frontend, Dixon–Coles math engine, Celery ETL pipeline, Alembic database migrations, and Docker configurations. Specification revision: **1.4.0**.

## First release

Pre-match regulation-time 1X2 across gate-approved leagues (Tier 1: EPL; Tier 2 candidates behind the §2.1 eligibility gate), derived markets (Totals, BTTS, Double Chance), Dixon–Coles probabilities, timestamped bookmaker comparisons, historical backtesting, bankroll simulations, and NOWPayments access passes (day/week entry passes, monthly and season passes).

## Document ownership

| File | Authority |
| --- | --- |
| `docs/01_PRD_PRODUCT_REQUIREMENTS.md` | Scope, user outcomes and non-goals |
| `docs/02_TECH_ARCHITECTURE_SPEC.md` | Service boundaries and deployment assumptions |
| `docs/03_DATABASE_SCHEMA.sql` | Storage fields and constraints |
| `docs/04_ALGORITHMS_MATH_SPEC.md` | Formulas, numerical conventions and evaluation |
| `docs/05_API_SPECIFICATION.md` | Routes, payloads, access rules and errors |
| `docs/06_DATA_PIPELINE_ETL.md` | Source eligibility, mapping and timestamps |
| `docs/07_CRYPTO_PAYMENT_INTEGRATION.md` | Catalog, payment verification and entitlement transitions |
| `docs/08_SPRINT_IMPLEMENTATION_PLAN.md` | Work order and acceptance gates |
| `AI_DEV_PROMPT_GEMINI.md` | Coding-agent workflow referencing those contracts |
| `docker-compose.yml`, `.env.example` | Service configuration |

## Local setup status

1. Copy `.env.example` to `.env` and fill in secrets.
2. Run database migrations: `alembic upgrade head` (inside backend directory or using the project virtualenv).
3. Start infrastructure and services: `docker compose up -d` or run backend and frontend independently for local development.
4. Run backend tests: `pytest backend/tests/`.
5. Build frontend: `npm --prefix frontend run build`.

