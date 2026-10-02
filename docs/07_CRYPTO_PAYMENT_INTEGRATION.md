# MatchLambda — NOWPayments Access Pass Contract

NOWPayments is the only release gateway. This is an implementation contract, not a working payment integration. Enable checkout only after merchant eligibility, a supported payment route and a public HTTPS IPN endpoint are verified. No KYC exemption, region bypass or blockchain confirmation-time guarantee is promised.

## 1. Catalog and checkout

| plan_type | USD price | Duration | User entitlement |
| --- | --- | --- | --- |
| PRO_MONTHLY | 29.00 | 30 × 24 hours | ANALYST |
| PRO_SEASON | 149.00 | 270 × 24 hours | ANALYST |

PRO_SEASON is a fixed 270-day pass, not nine calendar months or a competition end date. Both products grant the same analyst access; neither is recurring. API_DEV is deferred.

Use the provider's hosted invoice flow (POST /v1/invoice). The server selects catalog price/duration, price_currency=USD, unique order_id, the configured HTTPS ipn_callback_url and app return/cancel URLs. Do not accept client-supplied price, duration, user ID or callback URL. The provider handles its available coins/networks and payment instructions; the app must not promise unsupported combinations or generate an unverified QR/address.

Require a UUID Idempotency-Key on the local create-invoice route. First persist a CREATING order with catalog snapshots and a unique (user_id, request_key), then call the provider outside a DB lock. Lock and re-read the order when storing the returned invoice ID and checkout URL; only transition CREATING to PENDING, never downgrade a reconciled/credited order. Conflicting provider IDs require review. A repeated key with the same plan returns the same order; with another plan it returns 409.

On an uncertain provider timeout keep CREATING and reconcile the existing order against provider records before creating another invoice. Return 202 while unresolved; never blindly repeat the external creation call. A known rejection with no invoice created is FAILED. Reconciliation may be an operator action in the first release; no second payment service is required. Only return an HTTPS checkout URL from the provider's verified checkout host.

## 2. Signature authentication

The header is x-nowpayments-sig. Use **HMAC-SHA512** with the configured IPN secret and the provider's canonical JSON representation: parse the payload, sort object keys according to its current IPN specification (including nested objects where required), retain array order and scalar types, serialize without formatting whitespace, then calculate HMAC. Do not sign arbitrary raw request bytes and do not accept SHA256 as an alternative.

Use a provider-compatible serializer and verify it against a real provider sandbox/sample notification, including numeric/Unicode representation. A home-grown json.dumps call is not sufficient evidence of compatibility. Compare digests in constant time; invalid/missing signatures return 400 without state changes. Read the secret from configuration, never a code literal.

Official provider implementation reference (sorted JSON and SHA512):
https://github.com/NowPaymentsIO/nowpayments-payment-gateway-for-woocommerce/blob/master/class-wc-gateway-nowpayments.php

Current API/IPN reference:
https://documenter.getpostman.com/view/7907941/S1a32n38

## 3. Settlement verification

A signed notification identifies an order; it does not by itself authorize a plan extension.

Before crediting, fetch the referenced payment through the authenticated provider API (GET /v1/payment/{payment_id}). Require matching order_id, the stored gateway_invoice_id, provider payment identity, price_currency=USD and the stored price_amount. If an early IPN arrives before invoice creation has stored its provider ID, return 503 for reconciliation/retry; do not bind an unverified callback ID or grant access. Use Decimal for amount comparisons. Verify payment completion and full payment against the provider's expected crypto amount in the same pay_currency/precision; do not compare a crypto amount directly with USD. Bind gateway_payment_id uniquely to the invoice.

Only a verified **finished** payment can be credited. confirmed is intermediate for this application. Underpayment, identity/amount mismatch, unsupported status or multiple conflicting payments goes to REVIEW with no automatic access. Provider API timeout returns 503 for retry without granting; an invalid signature is never resolved by trusting the browser.

## 4. State and transaction

| Provider/local event | Local payment_status | Effect |
| --- | --- | --- |
| Invoice creation in progress | CREATING | No access |
| Invoice created; waiting/confirming/confirmed/sending | PENDING | No access |
| Verified eligible finished payment | PAID | Credit once |
| failed / expired before credit | FAILED / EXPIRED | No access |
| partially_paid / refunded / mismatched or unknown event before credit | REVIEW | No access; reconcile |
| Any notification after credit | PAID | Preserve credit marker; no second grant |

A later eligible finished event may credit a previously FAILED/EXPIRED/REVIEW order after provider verification. Never discard it solely because an earlier event looked terminal. After credit, refunds or conflicts require explicit operator handling and must not automatically extend or silently remove access.

Notification processing, after signature/provider verification:

1. Begin one DB transaction; lock the invoice row FOR UPDATE.
2. Recheck the immutable order/payment fields under the lock. Unknown local order returns 503 for reconciliation/retry, not an already-processed success.
3. If credited_at is present, return 200 without granting again. Record exceptional later events for review without downgrading the credited state.
4. For an eligible finished event, lock its users row FOR UPDATE (invoice then user is the consistent lock order).
5. Set plan_expires_at = max(existing expiry or now, now) + purchased duration, plan_tier = ANALYST; set credited_at and payment_status=PAID on the invoice.
6. Commit both updates together; acknowledge 200 only after commit. A rollback leaves both unchanged.

Locking the user serializes two different invoices purchased concurrently. The invoice's credited_at, not a transient Redis lock, is the idempotency marker. Helpers do not commit independently. Effective access always checks expiry, even if plan_tier still contains ANALYST.

## 5. Client and failure behavior

The return/cancel page polls the authenticated local order route; only its owner can read it. The client displays CREATING/PENDING/PAID/FAILED/EXPIRED/REVIEW and may stop polling after leaving the page. Provider validity time may be unknown; do not invent an expiry. Closing checkout or visiting a success URL does not activate access.

Log order/payment identifiers and transition failures without secrets or full sensitive payloads. Before enabling paid launch, verify the hosted-checkout/IPN round trip and repeated/concurrent final-event behavior. No payment has been made or merchant permissions verified by this specification.
