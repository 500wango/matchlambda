import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.main import app
from tests.ipn_sign import independent_ipn_signature

LIVE_KEY = "live_nowpayments_key_not_sandbox_01"


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _Provider:
    payload = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        assert "nowpayments.io" in url
        inv_id = f"np_test_{uuid.uuid4().hex[:10]}"
        return _Response(201, {"id": inv_id, "invoice_url": f"https://nowpayments.io/payment/?iid={inv_id}"})

    async def get(self, url, headers=None):
        assert url.startswith("https://api.nowpayments.io/v1/payment/")
        assert headers and headers.get("x-api-key") == LIVE_KEY
        return _Response(200, _Provider.payload)


def _sign(payload):
    return independent_ipn_signature(payload, settings.NOWPAYMENTS_IPN_SECRET)


@pytest.mark.asyncio
async def test_provider_reconciliation_branches(monkeypatch):
    monkeypatch.setattr(settings, "NOWPAYMENTS_API_KEY", LIVE_KEY)
    monkeypatch.setattr(settings, "NOWPAYMENTS_IPN_SECRET", "provider_reconcile_secret_32chars")
    monkeypatch.setattr("app.api.v1.payments.httpx.AsyncClient", _Provider)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.post("/v1/payments/webhook", json={"order_id": "none", "payment_status": "finished"})
        assert missing.status_code == 400
        assert missing.json()["error"]["code"] == "INVALID_SIGNATURE"

        unknown = {
            "order_id": "MLQ_DOES_NOT_EXIST",
            "payment_status": "waiting",
            "payment_id": "pay_unknown",
        }
        unknown_res = await client.post(
            "/v1/payments/webhook",
            json=unknown,
            headers={"x-nowpayments-sig": _sign(unknown)},
        )
        assert unknown_res.status_code == 503

        email = f"recon_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123456!"
        await client.post("/v1/auth/register", json={"email": email, "password": password})
        login = await client.post("/v1/auth/login", json={"email": email, "password": password})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        async def create_invoice(plan_type):
            created = await client.post(
                "/v1/payments/create-invoice",
                json={"plan_type": plan_type},
                headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            )
            assert created.status_code == 201
            return created.json()

        first = await create_invoice("PRO_MONTHLY")
        payment_id = f"pay_{uuid.uuid4().hex[:10]}"
        _Provider.payload = {
            "order_id": first["order_id"],
            "payment_status": "finished",
            "price_amount": first["amount_usd"],
            "price_currency": "usd",
            "pay_currency": "usdttrc20",
        }
        finished = {
            "order_id": first["order_id"],
            "payment_status": "finished",
            "payment_id": payment_id,
        }
        paid = await client.post(
            "/v1/payments/webhook",
            json=finished,
            headers={"x-nowpayments-sig": _sign(finished)},
        )
        assert paid.status_code == 200
        me = await client.get("/v1/me", headers=headers)
        assert me.json()["effective_plan"] == "ANALYST"
        expiry = me.json()["plan_expires_at"]

        mismatched = await create_invoice("PRO_SEASON")
        _Provider.payload = {
            "order_id": mismatched["order_id"],
            "payment_status": "finished",
            "price_amount": "1.00",
            "price_currency": "usd",
            "pay_currency": "usdttrc20",
        }
        mismatch_body = {
            "order_id": mismatched["order_id"],
            "payment_status": "finished",
            "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
        }
        mismatch_res = await client.post(
            "/v1/payments/webhook",
            json=mismatch_body,
            headers={"x-nowpayments-sig": _sign(mismatch_body)},
        )
        assert mismatch_res.status_code == 200
        mismatch_order = await client.get(f"/v1/payments/orders/{mismatched['order_id']}", headers=headers)
        assert mismatch_order.json()["payment_status"] == "REVIEW"
        me_after = await client.get("/v1/me", headers=headers)
        assert me_after.json()["plan_expires_at"] == expiry

        foreign_token = await create_invoice("PRO_MONTHLY")
        _Provider.payload = {
            "order_id": foreign_token["order_id"],
            "payment_status": "finished",
            "price_amount": foreign_token["amount_usd"],
            "price_currency": "usd",
            "pay_currency": "doge",
        }
        token_body = {
            "order_id": foreign_token["order_id"],
            "payment_status": "finished",
            "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
        }
        token_res = await client.post(
            "/v1/payments/webhook",
            json=token_body,
            headers={"x-nowpayments-sig": _sign(token_body)},
        )
        assert token_res.status_code == 200
        token_order = await client.get(f"/v1/payments/orders/{foreign_token['order_id']}", headers=headers)
        assert token_order.json()["payment_status"] == "REVIEW"

        failed_invoice = await create_invoice("PRO_MONTHLY")
        failed_body = {
            "order_id": failed_invoice["order_id"],
            "payment_status": "failed",
            "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
        }
        failed_res = await client.post(
            "/v1/payments/webhook",
            json=failed_body,
            headers={"x-nowpayments-sig": _sign(failed_body)},
        )
        assert failed_res.status_code == 200
        failed_order = await client.get(f"/v1/payments/orders/{failed_invoice['order_id']}", headers=headers)
        assert failed_order.json()["payment_status"] == "FAILED"


@pytest.mark.asyncio
async def test_sandbox_mode_validates_conflicting_webhook_amount(monkeypatch):
    # Sandbox is explicit opt-in only; a "test_" key prefix alone no longer
    # skips provider reconciliation. With the flag on, finished webhooks that
    # carry a conflicting price_amount must land in REVIEW instead of credit.
    monkeypatch.setattr(settings, "NOWPAYMENTS_API_KEY", "test_prefix_not_sandbox_anymore")
    monkeypatch.setattr(settings, "NOWPAYMENTS_IPN_SECRET", "sandbox_amount_secret_32chars_ok")
    monkeypatch.setattr(settings, "PAYMENTS_SANDBOX_MODE", True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"sbx_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123456!"
        await client.post("/v1/auth/register", json={"email": email, "password": password})
        login = await client.post("/v1/auth/login", json={"email": email, "password": password})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        async def create_invoice():
            created = await client.post(
                "/v1/payments/create-invoice",
                json={"plan_type": "PRO_MONTHLY"},
                headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            )
            assert created.status_code == 201
            return created.json()

        bad = await create_invoice()
        bad_body = {
            "order_id": bad["order_id"],
            "payment_status": "finished",
            "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
            "price_amount": "1.00",
            "price_currency": "usd",
            "pay_currency": "USDTTRC20",
        }
        bad_res = await client.post(
            "/v1/payments/webhook",
            json=bad_body,
            headers={"x-nowpayments-sig": _sign(bad_body)},
        )
        assert bad_res.status_code == 200
        bad_order = await client.get(f"/v1/payments/orders/{bad['order_id']}", headers=headers)
        assert bad_order.json()["payment_status"] == "REVIEW"

        good = await create_invoice()
        good_body = {
            "order_id": good["order_id"],
            "payment_status": "finished",
            "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
            "price_amount": good["amount_usd"],
            "price_currency": "usd",
            "pay_currency": "USDTTRC20",
        }
        good_res = await client.post(
            "/v1/payments/webhook",
            json=good_body,
            headers={"x-nowpayments-sig": _sign(good_body)},
        )
        assert good_res.status_code == 200
        good_order = await client.get(f"/v1/payments/orders/{good['order_id']}", headers=headers)
        assert good_order.json()["payment_status"] == "PAID"
        me = await client.get("/v1/me", headers=headers)
        assert me.json()["effective_plan"] == "ANALYST"


@pytest.mark.asyncio
async def test_day_and_week_pass_purchase(monkeypatch):
    # PRD v1.4 entry-level passes: cheap single-day / single-week units must be
    # purchasable and credit exactly their advertised duration.
    monkeypatch.setattr(settings, "NOWPAYMENTS_API_KEY", "micro_pass_sandbox_key")
    monkeypatch.setattr(settings, "NOWPAYMENTS_IPN_SECRET", "micro_pass_ipn_secret_32chars_ok")
    monkeypatch.setattr(settings, "PAYMENTS_SANDBOX_MODE", True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        pricing = await client.get("/v1/payments/pricing")
        assert pricing.status_code == 200
        assert pricing.json()["day_price_usd"] == 3.0
        assert pricing.json()["week_price_usd"] == 9.0

        email = f"micro_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123456!"
        await client.post("/v1/auth/register", json={"email": email, "password": password})
        login = await client.post("/v1/auth/login", json={"email": email, "password": password})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        async def create_invoice(plan_type):
            created = await client.post(
                "/v1/payments/create-invoice",
                json={"plan_type": plan_type},
                headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            )
            assert created.status_code == 201
            return created.json()

        for plan_type, expected_usd in (("PRO_DAY", 3.00), ("PRO_WEEK", 9.00)):
            invoice = await create_invoice(plan_type)
            assert float(invoice["amount_usd"]) == expected_usd
            body = {
                "order_id": invoice["order_id"],
                "payment_status": "finished",
                "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
                "price_amount": invoice["amount_usd"],
                "price_currency": "usd",
                "pay_currency": "USDTTRC20",
            }
            res = await client.post(
                "/v1/payments/webhook",
                json=body,
                headers={"x-nowpayments-sig": _sign(body)},
            )
            assert res.status_code == 200
            order = await client.get(f"/v1/payments/orders/{invoice['order_id']}", headers=headers)
            assert order.json()["payment_status"] == "PAID"
            assert order.json()["credited_at"] is not None
        me = await client.get("/v1/me", headers=headers)
        assert me.json()["effective_plan"] == "ANALYST"


@pytest.mark.asyncio
async def test_review_transition_dispatches_ops_alert_once(monkeypatch):
    # Every REVIEW transition must ping operators exactly once; provider
    # retries against an already-REVIEW invoice must not re-alert.
    monkeypatch.setattr(settings, "NOWPAYMENTS_API_KEY", "ops_alert_sandbox_key")
    monkeypatch.setattr(settings, "NOWPAYMENTS_IPN_SECRET", "ops_alert_ipn_secret_32chars_ok")
    monkeypatch.setattr(settings, "PAYMENTS_SANDBOX_MODE", True)

    alerts = []

    async def fake_alert(title, detail):
        alerts.append((title, detail))

    monkeypatch.setattr("app.api.v1.payments.dispatch_ops_alert", fake_alert)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"opsal_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123456!"
        await client.post("/v1/auth/register", json={"email": email, "password": password})
        login = await client.post("/v1/auth/login", json={"email": email, "password": password})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        async def create_invoice():
            created = await client.post(
                "/v1/payments/create-invoice",
                json={"plan_type": "PRO_MONTHLY"},
                headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            )
            assert created.status_code == 201
            return created.json()

        conflict = await create_invoice()
        bad_body = {
            "order_id": conflict["order_id"],
            "payment_status": "finished",
            "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
            "price_amount": "1.00",
            "price_currency": "usd",
            "pay_currency": "USDTTRC20",
        }
        for _ in range(2):
            res = await client.post(
                "/v1/payments/webhook",
                json=bad_body,
                headers={"x-nowpayments-sig": _sign(bad_body)},
            )
            assert res.status_code == 200
        order = await client.get(f"/v1/payments/orders/{conflict['order_id']}", headers=headers)
        assert order.json()["payment_status"] == "REVIEW"
        assert len(alerts) == 1
        assert "conflicts" in alerts[0][0]

        partial = await create_invoice()
        partial_body = {
            "order_id": partial["order_id"],
            "payment_status": "partially_paid",
            "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
        }
        for _ in range(2):
            res = await client.post(
                "/v1/payments/webhook",
                json=partial_body,
                headers={"x-nowpayments-sig": _sign(partial_body)},
            )
            assert res.status_code == 200
        order = await client.get(f"/v1/payments/orders/{partial['order_id']}", headers=headers)
        assert order.json()["payment_status"] == "REVIEW"
        assert len(alerts) == 2

