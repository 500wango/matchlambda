# MatchLambda — Product Requirements

**Version:** 1.4.0  
**Status:** Multi-league scope adopted; expansion gated by §2.1 coverage and evaluation criteria.  
**Audience:** Football analysts and data-oriented fans.

## 1. First-release outcome

Show reproducible pre-match probabilities for covered leagues (Tier 1: Premier League; Tier 2: English Championship and other candidate leagues once they pass §2.1 gates) alongside a timestamped, eligible bookmaker quote. Market-derived probabilities are estimates, not ground truth. Positive estimated EV does not establish profitability.

## 2. Scope

- **Competition:** Multi-league, tiered by evidence (§2.1). Tier 1 — Premier League (full historical coverage). Tier 2 — leagues released only after passing the automated eligibility gate (coverage, quote availability and held-out evaluation against the market baseline). Unlisted and pending leagues never surface predictions, scanner signals or picks.
- **Market:** 1X2 for regulation time including stoppage time, excluding extra time and penalties.
- **Model:** Time-weighted Dixon–Coles on completed matches. The math specification owns equations and evaluation.
- **Quotes:** One validated bookmaker, initially Pinnacle through The Odds API if account access, permissions and EPL coverage pass the ETL gate. No automatic provider substitution.
- **Refresh:** Discrete T−12h, T−2h and T−45m snapshots. Show timestamps; do not promise continuous real-time monitoring.
- **Access:** Free fixture schedule; an active analyst pass for probabilities, detailed analysis and EV filtering. The web app uses JWT-authenticated routes.
- **Billing:** NOWPayments hosted checkout and non-recurring analyst passes (entry-level day/week passes plus monthly and season passes). Prices, durations and transitions belong to the payment specification.

### 2.1 League coverage tiers and expansion gates

League expansion is data-driven and reversible. A daily scheduled job recomputes, per league:

1. **Coverage floor:** at least 300 completed matches with recorded results.
2. **Quote availability:** at least 40% of completed matches carry an eligible pre-kickoff bookmaker snapshot.
3. **Held-out evaluation:** on the most recent completed matches with stored predictions (minimum 40 evaluated samples), the model's multiclass Brier score must not exceed the Shin de-juiced market baseline by more than 5%.
4. **Live coverage:** scheduled fixtures in the window carry current predictions.

Outcomes: a league that passes every check becomes *eligible* and is exposed to the scanner, daily picks and parlay generator; a league that fails any check is *pending* (or reverts to pending after a regression) and is hidden from user surfaces while remaining visible and inspectable in the admin panel. Leagues approved on the frozen 10-year dataset backtest (Premier League, English Championship) run on a *provisional* basis: history, quote-availability and sample-count checks are waived while live stored predictions are still thin, but the market-baseline comparison and live-coverage checks always bind, and every check becomes fully enforceable once live samples reach the floor. Thresholds are operator-configurable. The eligibility snapshot records computed time, per-league metrics, evaluation basis and failed reasons for audit.

## 3. User-visible behavior

- Schedule: teams, competition, kickoff, status and data availability. Store UTC; render the user's timezone.
- Analysis: expected goals, 1X2 probabilities, 0–5 goal display matrix, omitted mass and the three most likely scores from the calculation distribution.
- Comparison: eligible bookmaker name, odds, de-juiced estimates, quote time and EV for home/draw/away. Do not claim best prices across the market.
- Scanner: include an outcome when unrounded `EV >= 0.05` and prediction/quote freshness passes the ETL contract. Stale or missing information never produces a current alert.
- Half-Kelly is an optional analytical fraction, not automated execution or a return guarantee.
- Unmapped teams, insufficient history, postponed fixtures and missing quotes produce explicit unavailable states, never invented zero values.
- Purchase: open hosted checkout, then poll the authenticated local order status. A browser redirect is not proof of payment.

## 4. Non-goals

ClubElo cross-league priors; Asian handicap, totals or in-play analysis; trade execution; Betfair depth/volume and commission-adjusted exchange EV; FBref scraping, xG/PPDA and LightGBM; Cryptomus; custom payment QR generation; recurring billing; API keys and the 100,000-request API subscription.

Cup competitions (UCL/UEL) stay in *pending* until their knockout format is either evaluated on league-phase matches only or a dedicated model is specified; the eligibility gate governs their exposure. Multi-national league coverage beyond the current candidate list remains a roadmap candidate. Do not build tables, endpoints or billing tiers solely for deferred features.

## 5. Acceptance

1. Record source authorization and real samples per league before production ingestion.
2. Trace each prediction to its parameters, immutable training dataset reference and decision time, and each comparison to its quote snapshot.
3. Math and payload examples agree within stated precision; evaluation uses chronological folds and an eligible market baseline where historical evidence exists.
4. Enforce entitlement and expiry server-side. Duplicate/concurrent final payment notifications credit once.
5. Verify unavailable/stale states and the deployment gate. No fixed launch date or blockchain confirmation-time guarantee is implied.
6. Enforce §2.1 server-side: scanner, picks and parlay surfaces draw only from eligible leagues; the public eligibility snapshot and admin refresh path are auditable.
