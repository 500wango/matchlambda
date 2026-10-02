# MatchLambda — REST API Contract

Base path: /v1. UTC ISO 8601 timestamps, decimal odds and probability fractions. This is a contract to implement, not an existing service. No API-key authentication or paid request-quota tier is included.

## 1. Authentication and access

Authenticated requests use Authorization: Bearer <JWT>. Validate signature, subject and expiry; check current DB entitlement on every paid route. Effective access is ANALYST only when plan_tier=ANALYST and plan_expires_at > now; otherwise FREE.

| Route | Authentication/access | Success |
| --- | --- | --- |
| POST /auth/register | Public, rate-limited | 201: id, normalized email |
| POST /auth/login | Public, rate-limited | 200: access_token, token_type=bearer, expires_in seconds |
| GET /me | JWT | 200: id, email, effective_plan, plan_expires_at |
| GET /matches/fixtures | Public; JWT required for paid fields/filter | 200: paginated fixtures |
| GET /matches/{match_id}/analysis | JWT + active analyst pass | 200: analysis/availability |
| POST /payments/create-invoice | JWT, rate-limited | 201, 200 replay, or 202 creation pending |
| GET /payments/orders/{order_id} | JWT; owner only | 200: local order state |
| POST /payments/webhook | Provider signature; no user JWT | 200 only after successful processing |

Register/login accept JSON email and password. Normalize email by trimming/lowercasing; registration requires a valid address and password of 12–128 characters, stored with Argon2id. Duplicate normalized email returns 409. Invalid login returns generic 401. Tokens last the configured 60 minutes; no refresh route. Client clears its in-memory token on logout and signs in again after reload/expiry.

## 2. Fixtures

GET /matches/fixtures query:
- league_id: optional, only EPL in this release; unsupported values return 422.
- days_ahead: integer 1–7, default 3; interval [request_time, request_time + days_ahead days).
- limit: integer 1–100, default 20; offset: integer >= 0, default 0.
- has_value: optional boolean, available only with an active pass. true includes matches with at least one current eligible EV >= 0.05; false includes those without one. Enforce access whenever the parameter is supplied.

Return fixtures ordered by (match_date, id), including scheduled fixtures only. Paid summaries use the latest completed prediction (largest as_of) and its fixed quote reference. List and analysis apply the same freshness rules and must agree on has_value for the same evaluation time and records.

### 2.1 Response fields

Every 200 response has exactly these envelope fields:

| Field | Type | Meaning |
| --- | --- | --- |
| total | integer >= 0 | Count after all filters, before pagination |
| limit | integer | Effective requested page size |
| offset | integer | Effective requested offset |
| fixtures | array | Current page; empty when no rows remain |

Every fixture has these required, non-null base fields:

| Field | Type | Meaning |
| --- | --- | --- |
| match_id | string | Canonical match ID |
| league_id | string | EPL in this release |
| match_date | UTC timestamp string | Current scheduled kickoff |
| home_team | object with exactly id:string, name:string | Canonical home team |
| away_team | object with exactly id:string, name:string | Canonical away team |
| status | string | SCHEDULED for this endpoint |

An active analyst pass adds exactly four required keys to each fixture:

| Field | Type | Meaning |
| --- | --- | --- |
| data_status | AVAILABLE / UNAVAILABLE / STALE | Same availability evaluation as section 3 |
| reason | string or null | Applicable section 3 reason; null when fully available |
| prediction | object or null | Projection of the selected analysis prediction defined below |
| comparison | object or null | Projection of its eligible analysis comparison defined below |

When prediction is present, it contains exactly:
- id: UUID string identifying the saved prediction.
- as_of: UTC timestamp string identifying its decision cutoff.
- lambda_home, mu_away: positive finite numbers.
- prob_home_win, prob_draw, prob_away_win: probability numbers in [0,1], with the math contract's rounding tolerance.

When comparison is present, it contains exactly:
- odds_snapshot_id: UUID string identifying the fixed quote snapshot.
- bookmaker: string identifying the quoted bookmaker.
- quote_at: UTC timestamp string identifying the source quote update.
- has_value: boolean; true if any eligible outcome has unrounded EV >= 0.05.
- outcomes: exactly three objects, ordered HOME, DRAW, AWAY. Each contains exactly outcome (that enum), model_prob and market_prob (probability numbers), odds (decimal number > 1), ev (finite number, possibly negative) and half_kelly (number in [0,0.5]). Values are the same as the corresponding analysis outcome, not recomputed from rounded summary probabilities.

The list omits the score matrix, top scores, model metadata and other analysis-only fields. Use the prediction/comparison keys above, not additional prediction_summary or comparison_summary wrappers. Both objects are exact field projections of the corresponding analysis response at the same evaluation time.

### 2.2 Access and null rules

- Anonymous requests and valid JWTs with effective FREE access receive only the base fields. Omit data_status, reason, prediction and comparison entirely; do not return null placeholders for paid fields.
- Invalid or expired supplied JWTs return 401, even without a paid filter. An expired pass with a still-valid JWT receives the free shape when has_value is absent.
- Supplying has_value requires authentication (401 if missing/invalid) and an active analyst pass (403 otherwise), for both true and false.
- For a paid UNAVAILABLE fixture, prediction=null and comparison=null; reason follows section 3.
- For a paid STALE fixture, return the last saved prediction summary and comparison=null, with the applicable stale reason. It is labelled historical, never a current signal. Fixtures no longer scheduled are excluded before pagination rather than returned with MATCH_NOT_SCHEDULED.
- With an AVAILABLE prediction but no eligible quote, prediction is present, comparison=null and reason is MISSING_QUOTE or STALE_QUOTE. When both are current, reason=null.
- A null comparison has no has_value or outcome values. has_value=false filters for absence of an eligible positive signal and therefore also includes unavailable/stale comparisons; do not synthesize a false comparison object or zero EV for those rows.

### 2.3 Free 200 example

GET /matches/fixtures?league_id=EPL&days_ahead=3&limit=20&offset=0, without an active pass. Both list examples use the same synthetic fixture and evaluation clock as section 3 (2026-10-04T16:01:00Z), with one matching fixture in the illustrative dataset.

```json
{
  "total": 1,
  "limit": 20,
  "offset": 0,
  "fixtures": [
    {
      "match_id": "EPL_DEMO_001",
      "league_id": "EPL",
      "match_date": "2026-10-04T18:00:00Z",
      "home_team": {
        "id": "demo-home",
        "name": "Demo Home"
      },
      "away_team": {
        "id": "demo-away",
        "name": "Demo Away"
      },
      "status": "SCHEDULED"
    }
  ]
}
```

### 2.4 Paid 200 example

The same request with a valid JWT and active analyst pass. Prediction and comparison values are projected from the section 3 analysis example.

```json
{
  "total": 1,
  "limit": 20,
  "offset": 0,
  "fixtures": [
    {
      "match_id": "EPL_DEMO_001",
      "league_id": "EPL",
      "match_date": "2026-10-04T18:00:00Z",
      "home_team": {
        "id": "demo-home",
        "name": "Demo Home"
      },
      "away_team": {
        "id": "demo-away",
        "name": "Demo Away"
      },
      "status": "SCHEDULED",
      "data_status": "AVAILABLE",
      "reason": null,
      "prediction": {
        "id": "11111111-1111-4111-8111-111111111111",
        "as_of": "2026-10-04T16:00:00Z",
        "lambda_home": 1.78,
        "mu_away": 0.92,
        "prob_home_win": 0.576491515,
        "prob_draw": 0.2314130732,
        "prob_away_win": 0.1920954117
      },
      "comparison": {
        "odds_snapshot_id": "22222222-2222-4222-8222-222222222222",
        "bookmaker": "DEMO_BOOK",
        "quote_at": "2026-10-04T15:59:00Z",
        "has_value": true,
        "outcomes": [
          {
            "outcome": "HOME",
            "model_prob": 0.576491515,
            "market_prob": 0.5205380051,
            "odds": 1.9,
            "ev": 0.0953338786,
            "half_kelly": 0.0529632659
          },
          {
            "outcome": "DRAW",
            "model_prob": 0.2314130732,
            "market_prob": 0.2618678364,
            "odds": 3.75,
            "ev": -0.1322009754,
            "half_kelly": 0.0
          },
          {
            "outcome": "AWAY",
            "model_prob": 0.1920954117,
            "market_prob": 0.2175941585,
            "odds": 4.5,
            "ev": -0.1355706472,
            "half_kelly": 0.0
          }
        ]
      }
    }
  ]
}
```

## 3. Analysis and availability

GET /matches/{match_id}/analysis returns match_id, data_status, reason, prediction and comparison:
- AVAILABLE: current eligible prediction; comparison may still be null if no eligible quote.
- UNAVAILABLE: prediction=null, comparison=null; reason identifies NO_PREDICTION, UNRESOLVED_ENTITY, INSUFFICIENT_HISTORY or INVALID_MODEL. Use NO_PREDICTION unless a more specific cause is actually recorded; do not infer it from missing rows.
- STALE: return the last saved prediction with its timestamps, comparison=null; reason identifies STALE_PREDICTION, FIXTURE_CHANGED or MATCH_NOT_SCHEDULED. If no saved prediction exists, use UNAVAILABLE instead.
- With a current prediction but no comparison, reason is MISSING_QUOTE or STALE_QUOTE; otherwise null.

Apply the ETL age/fixture checks at response time. If comparison is null, there is no current EV/half-Kelly/has_value result; do not use zeros to represent missing data. Missing match returns 404, distinct from an existing match with unavailable prediction.

The prediction includes the model parameter reference/version, training cutoff, decision/completion timestamps and kickoff captured at prediction. Matrix rows are home goals, columns away goals. It is always 6×6 when present, with omitted_mass; it is not normalized to 1. top_scores comes from the calculation support. See the math contract.

### Synthetic, internally consistent 200 example

Assume the evaluation clock is 2026-10-04T16:01:00Z, kickoff is 18:00Z, and the fixture is scheduled. These are invented fixtures/quotes for documentation, not a data-provider sample. Lambda=1.78, mu=0.92, rho=0; numeric values share the same computation.

```json
{
  "match_id": "EPL_DEMO_001",
  "data_status": "AVAILABLE",
  "reason": null,
  "prediction": {
    "id": "11111111-1111-4111-8111-111111111111",
    "model_parameters_id": "33333333-3333-4333-8333-333333333333",
    "model_version": "dc-demo-1",
    "training_cutoff": "2026-10-03T00:00:00Z",
    "as_of": "2026-10-04T16:00:00Z",
    "generated_at": "2026-10-04T16:00:01Z",
    "kickoff_at_prediction": "2026-10-04T18:00:00Z",
    "lambda_home": 1.78,
    "mu_away": 0.92,
    "rho": 0.0,
    "prob_home_win": 0.5764915150,
    "prob_draw": 0.2314130732,
    "prob_away_win": 0.1920954117,
    "score_matrix": [
      [0.0672055127, 0.0618290717, 0.0284413730, 0.0087220211, 0.0020060648, 0.0003691159],
      [0.1196258127, 0.1100557477, 0.0506256439, 0.0155251975, 0.0035707954, 0.0006570264],
      [0.1064669733, 0.0979496154, 0.0450568231, 0.0138174257, 0.0031780079, 0.0005847535],
      [0.0631704041, 0.0581167718, 0.0267337150, 0.0081983393, 0.0018856180, 0.0003469537],
      [0.0281108298, 0.0258619635, 0.0118965032, 0.0036482610, 0.0008391000, 0.0001543944],
      [0.0100074554, 0.0092068590, 0.0042351551, 0.0012987809, 0.0002987196, 0.0000549644]
    ],
    "omitted_mass": 0.0102482299,
    "top_scores": [
      {"score": "1-0", "prob": 0.1196258127},
      {"score": "1-1", "prob": 0.1100557477},
      {"score": "2-0", "prob": 0.1064669733}
    ]
  },
  "comparison": {
    "odds_snapshot_id": "22222222-2222-4222-8222-222222222222",
    "source_name": "demo",
    "bookmaker": "DEMO_BOOK",
    "quote_at": "2026-10-04T15:59:00Z",
    "recorded_at": "2026-10-04T15:59:05Z",
    "dejuice_method": "SHIN",
    "overround": 0.0152046784,
    "has_value": true,
    "outcomes": [
      {"outcome": "HOME", "model_prob": 0.5764915150, "market_prob": 0.5205380051, "odds": 1.90, "ev": 0.0953338786, "half_kelly": 0.0529632659},
      {"outcome": "DRAW", "model_prob": 0.2314130732, "market_prob": 0.2618678364, "odds": 3.75, "ev": -0.1322009754, "half_kelly": 0.0},
      {"outcome": "AWAY", "model_prob": 0.1920954117, "market_prob": 0.2175941585, "odds": 4.50, "ev": -0.1355706472, "half_kelly": 0.0}
    ]
  }
}
```

## 4. Payment routes

POST /payments/create-invoice requires a UUID Idempotency-Key and JSON body:
```json
{"plan_type": "PRO_MONTHLY"}
```
PRO_SEASON is also accepted. Reject unsupported plans or client price/duration fields with 422. The payment specification owns catalog prices and renewal semantics. A repeated key with a different plan returns 409.

Return order_id, plan_type, amount_usd, payment_status, checkout_url and valid_until. checkout_url is a provider-verified HTTPS URL only after creation; valid_until may be null if the provider supplies no expiry. A new ready invoice returns 201; an existing non-CREATING order returns 200 with its current state (including failure/review); unresolved CREATING returns 202 with checkout_url=null. Missing provider configuration returns 503 PAYMENTS_UNAVAILABLE before creating an order.

GET /payments/orders/{order_id} returns the same fields plus credited_at and current plan_expires_at. Only the authenticated owner can see the order; unknown or other-user orders return 404. Poll no more often than every five seconds while CREATING/PENDING; stop when leaving the page or showing a final/review state. Later server reconciliation is still possible. Never grant access from a checkout return URL.

POST /payments/webhook follows the signature, provider-verification and transaction contract in the payment document. It returns {"status":"ok"} after committed processing, including a genuine duplicate already credited. A valid but unknown local order returns 503, not a misleading duplicate success.

## 5. Errors

Use one JSON envelope for all endpoints, including request validation:
```json
{"error": {"code": "PASS_REQUIRED", "message": "An active analyst pass is required."}}
```

| HTTP | Code / meaning |
| --- | --- |
| 400 | INVALID_SIGNATURE or malformed JSON |
| 401 | UNAUTHENTICATED |
| 403 | PASS_REQUIRED |
| 404 | NOT_FOUND |
| 409 | EMAIL_EXISTS or IDEMPOTENCY_CONFLICT |
| 422 | VALIDATION_ERROR |
| 429 | RATE_LIMITED, with Retry-After |
| 503 | PAYMENTS_UNAVAILABLE, PROVIDER_UNAVAILABLE or ORDER_RECONCILIATION_REQUIRED |

Do not leak stack traces, provider secrets or other users' order state. Match data gaps use the 200 availability contract, not fabricated success probabilities.
