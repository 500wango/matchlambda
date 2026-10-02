# MatchLambda — Implementation Gates

These gates replace the unvalidated 21-day schedule. Estimate after source access and team capacity are known. All application work remains pending.

## Gate 1: Sources and foundation

- [ ] Complete ETL evidence for EPL results, fixtures and one bookmaker; obtain rights and real samples before production import.
- [ ] Initialize the application repository, ignore secrets and scaffold backend/frontend Dockerfiles with locked dependencies.
- [ ] Introduce the SQL through one Alembic migration and verify local service startup.
- [ ] Seed confirmed EPL mappings; import validated history and refresh fixtures/results.
- **Exit:** A source event maps to one canonical fixture; reruns/reschedules preserve identity and ambiguous rows are rejected.

## Gate 2: Probability and traceability

- [ ] Implement constrained Dixon–Coles and the specified de-juicing methods.
- [ ] Generate calculation probabilities, display window and omitted mass from one result.
- [ ] Schedule the three collection points; persist quote, model and prediction references.
- [ ] Evaluate chronological folds using Brier score/log loss and an eligible market baseline; disclose missing historical evidence.
- **Exit:** Numerical examples pass; a live prediction and evaluation fold are reproducible. Invalid/stale data cannot emit a current signal.

## Gate 3: API and payment

- [ ] Implement API auth, access, pagination, unavailable states and errors.
- [ ] Integrate NOWPayments hosted invoices, local polling and server-verified final settlement.
- [ ] Implement atomic invoice/user crediting and verify duplicate/concurrent notification behavior and renewal of expired passes.
- **Exit:** Unpaid users cannot access paid data; an eligible finished payment grants its purchased pass once.

## Gate 4: Web workflow and launch

- [ ] Build login, fixtures, probability/market analysis, EV filtering and checkout return/polling.
- [ ] Show timestamps, omitted mass, unavailable states and expiry; omit deferred markets and tiers.
- [ ] Select deployment and pass the architecture's HTTPS/configuration/backup/restore/provider gate.
- **Exit:** Verify the paid-analysis workflow in the target environment; disclose remaining limitations.

## Verification discipline

Use relevant existing checks first. Add only checks for the current changed behavior, without a new framework, broad snapshot suite or unrelated coverage. Distinguish numerical checks, provider smoke checks and runtime acceptance; none proves profitability. Remove unnecessary abstractions after each implementation.
