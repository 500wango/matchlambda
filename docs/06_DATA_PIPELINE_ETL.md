# MatchLambda — Data Pipeline and Source Contract

## 1. Source gate (not yet passed)

Before production import, record permission evidence, account/plan, actual EPL sample, available seasons/fields, timezone semantics and storage/display restrictions. Record references, never credentials.

| Need | Candidate | Required evidence | Status |
| --- | --- | --- | --- |
| Historical EPL results | Licensed dataset; football-data only with suitable permission | Seasons, regulation scores, identity, availability/corrections and training rights | Provider/dataset not selected |
| Future fixtures and final results | Validated The Odds API account or selected licensed results source | EPL event IDs, kickoff/status updates, regulation results and refresh limits | Account/sample unverified |
| Pinnacle pre-match 1X2 | The Odds API | Complete EPL three-outcome sample, source timestamp, storage/display rights and budget | Account/sample unverified |
| ClubElo, FBref, Betfair depth | Deferred | Separate coverage, permission and model contracts | Out of scope |

Checked 2026-10-03: football-data's public page restricts commercial/automated data-training uses and warns of systematically stale Pinnacle quotes since 2025-07-23. Public downloadability is not permission, and affected quotes are not a clean historical benchmark. Source: `https://www.football-data.co.uk/data.php`.

The Odds API documents `h2h` and supported exchange `h2h_lay`; this does not establish a depth/volume feed. Reference: `https://the-odds-api.com/liveapi/guides/v4/`. Do not scrape or purchase a substitute merely to fill this table; first validate its fit and rights.

## 2. Inputs and identities

- Results need source identity, league, season, kickoff with known timezone, team identities, status, regulation scores and result-availability time. Reject unknown timezones or score semantics.
- Seed canonical EPL teams and reviewed aliases before history. Resolve `(source_name, external_id)` first. With no source ID, use a confirmed `(source_name, country, external_name)` alias whose `external_id` is null.
- Fuzzy matching only proposes candidates restricted by competition/season and country. Preserve canonical IDs for same-name teams. Ambiguous/unmatched rows enter an operator-reviewed rejection file. Empty candidates mean unresolved.
- Resolvers return an existing ID or unresolved; they do not create clubs/aliases or commit. Reviewed alias insertion is part of the caller's transaction. On uniqueness conflict, re-read and verify the same target.
- `match_sources` maps stable source event IDs to canonical matches. Where the source has no ID, establish a reviewed key independent of mutable kickoff. Reschedules update the existing match; conflicting teams require review.
- Only final regulation results train the model. Postponed/cancelled/abandoned fixtures remain unavailable until an eligible final result exists. A kickoff change invalidates predictions recording the previous kickoff.

## 3. Collection and timestamps

- Refresh active fixtures/results hourly, subject to a verified provider request budget. Bootstrap only licensed, validated seasons; there is no assumed ten-year coverage.
- Collect one quote snapshot and generate a prediction at T−12h, T−2h and T−45m. Reuse eligible model parameters or fit before the decision cutoff. Missed points stay missing, never backdated. Recompute future tasks after rescheduling.
- Select one bookmaker's complete `h2h` market. Reject missing/duplicate outcomes, suspended quotes, odds <= 1, non-finite numbers and absent source update time.
- `quote_at` is the source update; `recorded_at` is receipt. Re-reading the same update is not a fresh quote. Store immutable snapshots unique by source/bookmaker/match/quote time; conflicting data at the same key requires review.
- `predictions.as_of` is the live decision cutoff; parameters must be calculated and data received by it. `generated_at` records completion. Store the selected quote ID; do not rewrite an old comparison with a newer quote.
- Current comparisons require a scheduled future fixture, unchanged kickoff, prediction age <= 13 hours, quote age <= 13 hours and `quote_at <= recorded_at <= as_of`. This fits the stated sampling schedule, not continuous real-time alerts. Missing/invalid/old inputs make comparison fields unavailable; never retain an old positive EV flag as current.

## 4. Training and replay provenance

`model_parameters.training_data_ref` identifies an immutable dataset artifact plus content hash. Include exact input rows, source references, result-availability timestamps, training window and fitting configuration. `training_cutoff` excludes results not known by that time and cannot exceed the prediction cutoff.

Replay uses chronological folds and data demonstrably available at each simulated decision. Today's receipt time is not historical availability evidence. With only final scores/closing odds, label evaluation as final-data/closing-market comparison; do not claim a tradable T−12h EV backtest. Offline replay results stay in the evaluation artifact, not live predictions.

Result corrections create new dataset/model artifacts; retain those supporting published predictions. Log rejected rows, source failures and missed points without secrets; obey provider rate/retry limits.
