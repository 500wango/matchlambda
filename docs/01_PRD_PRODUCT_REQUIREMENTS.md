# MatchLambda — Product Requirements

**Version:** 1.3.0  
**Status:** Revised specification; source access and implementation acceptance pending.  
**Audience:** Football analysts and data-oriented fans.

## 1. First-release outcome

Show reproducible pre-match EPL probabilities and comparison with a timestamped, eligible bookmaker quote. Market-derived probabilities are estimates, not ground truth. Positive estimated EV does not establish profitability.

## 2. Scope

- **Competition:** EPL only; expansion requires coverage and evaluation evidence.
- **Market:** 1X2 for regulation time including stoppage time, excluding extra time and penalties.
- **Model:** Time-weighted Dixon–Coles on completed matches. The math specification owns equations and evaluation.
- **Quotes:** One validated bookmaker, initially Pinnacle through The Odds API if account access, permissions and EPL coverage pass the ETL gate. No automatic provider substitution.
- **Refresh:** Discrete T−12h, T−2h and T−45m snapshots. Show timestamps; do not promise continuous real-time monitoring.
- **Access:** Free fixture schedule; an active analyst pass for probabilities, detailed analysis and EV filtering. The web app uses JWT-authenticated routes.
- **Billing:** NOWPayments hosted checkout and non-recurring analyst passes. Prices, durations and transitions belong to the payment specification.

## 3. User-visible behavior

- Schedule: teams, competition, kickoff, status and data availability. Store UTC; render the user's timezone.
- Analysis: expected goals, 1X2 probabilities, 0–5 goal display matrix, omitted mass and the three most likely scores from the calculation distribution.
- Comparison: eligible bookmaker name, odds, de-juiced estimates, quote time and EV for home/draw/away. Do not claim best prices across the market.
- Scanner: include an outcome when unrounded `EV >= 0.05` and prediction/quote freshness passes the ETL contract. Stale or missing information never produces a current alert.
- Half-Kelly is an optional analytical fraction, not automated execution or a return guarantee.
- Unmapped teams, insufficient history, postponed fixtures and missing quotes produce explicit unavailable states, never invented zero values.
- Purchase: open hosted checkout, then poll the authenticated local order status. A browser redirect is not proof of payment.

## 4. Non-goals

Other domestic leagues and UCL/UEL; ClubElo cross-league priors; Asian handicap, totals or in-play analysis; trade execution; Betfair depth/volume and commission-adjusted exchange EV; FBref scraping, xG/PPDA and LightGBM; Cryptomus; custom payment QR generation; recurring billing; API keys and the 100,000-request API subscription.

The earlier 18-league + UCL/UEL coverage remains a roadmap candidate. Do not build tables, endpoints or billing tiers solely for deferred features.

## 5. Acceptance

1. Record source authorization and real EPL samples before production ingestion.
2. Trace each prediction to its parameters, immutable training dataset reference and decision time, and each comparison to its quote snapshot.
3. Math and payload examples agree within stated precision; evaluation uses chronological folds and an eligible market baseline where historical evidence exists.
4. Enforce entitlement and expiry server-side. Duplicate/concurrent final payment notifications credit once.
5. Verify unavailable/stale states and the deployment gate. No fixed launch date or blockchain confirmation-time guarantee is implied.
