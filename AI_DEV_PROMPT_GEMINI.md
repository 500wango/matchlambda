# MatchLambda — Coding-Agent Handoff

This is a specification-only project. Implement the release defined in `docs/01_PRD_PRODUCT_REQUIREMENTS.md`; planned services do not already exist.

## Working rules

1. Read the relevant contract before editing. Scope belongs to the PRD, formulas to the math document, routes to the API document and payment behavior to the payment document. Fix contradictions at their source.
2. Use the smallest implementation meeting the current gate. Do not add provider frameworks, event buses, compatibility layers or schemas for deferred markets.
3. Collection, training and inference belong in Python/FastAPI/Celery; Next.js consumes REST. Select and lock supported dependency versions when scaffolding. Proposed stack: Python 3.11+, PostgreSQL 16, Redis 7, Next.js/React, NumPy/SciPy, SQLAlchemy 2 and Alembic.
4. Validate source permissions and actual EPL field coverage before bulk import. Synthetic fixtures must be labelled and cannot stand in for production evidence.
5. Resolve identities through confirmed mappings. Fuzzy matches propose candidates; they never auto-create aliases or commit the caller's transaction.
6. Preserve quote, training and prediction timestamps. Do not reconstruct an earlier forecast with later information or overwrite historical snapshots.
7. Follow `docs/07_CRYPTO_PAYMENT_INTEGRATION.md` for canonicalization, accepted final payment status and atomic entitlement crediting. Do not invent another gateway or signature algorithm.
8. Describe the actual service accurately. Provider eligibility depends on business use and account permission, not renamed keywords or proxy routing.

## Execution order

- Pass the source gate for EPL.
- Scaffold local services and migrate the proposed schema.
- Implement confirmed mappings, results/fixtures and immutable quote snapshots.
- Implement the mathematical specification and chronological evaluation.
- Implement JWT, the documented read API and NOWPayments hosted checkout.
- Build the dashboard and complete the release gates in the implementation plan.

## Verification

Run relevant existing checks first. Add a test only for changed behavior existing checks cannot cover, limited to the main path and one important failure path per change. Do not introduce a test framework solely for this handoff.

Acceptance concerns valid probabilities, traceable inputs, access enforcement and one-time payment crediting. A 6×6 display window is not a normalized full distribution; follow the math document's tail contract. Disclose unverified provider/runtime prerequisites. After implementation, remove abstractions not needed for the accepted behavior.
