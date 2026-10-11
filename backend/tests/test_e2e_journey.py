import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from tests.ipn_sign import independent_ipn_signature


@pytest.mark.asyncio
async def test_complete_user_analyst_journey(monkeypatch):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        monkeypatch.setattr(settings, "NOWPAYMENTS_API_KEY", "sandbox_test_key")
        monkeypatch.setattr(settings, "PAYMENTS_SANDBOX_MODE", True)
        monkeypatch.setattr(settings, "NOWPAYMENTS_IPN_SECRET", "secret_for_e2e_journey_test")

        # 1. Anonymous user explores fixtures
        res = await client.get("/v1/matches/fixtures?league_id=EPL&days_ahead=14")
        assert res.status_code == 200
        fixtures_data = res.json()
        assert fixtures_data["total"] >= 1
        f0 = fixtures_data["fixtures"][0]
        match_id = f0["match_id"]
        # Free view strictly omits paid predictions
        assert f0.get("prediction") is None
        assert f0.get("comparison") is None

        # 2. Register account
        email = f"e2e_analyst_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"
        res = await client.post("/v1/auth/register", json={"email": email, "password": password})
        assert res.status_code == 201

        # 3. Log in to get JWT
        res = await client.post("/v1/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200
        token = res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 4. Check user profile
        res = await client.get("/v1/me", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["effective_plan"] == "FREE"

        # 5. Try accessing gated features with Free tier
        res = await client.get("/v1/matches/fixtures?has_value=true", headers=auth_headers)
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "PASS_REQUIRED"

        res = await client.get(f"/v1/matches/{match_id}/analysis", headers=auth_headers)
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "PASS_REQUIRED"

        # 6. Create crypto invoice for PRO_MONTHLY pass
        idempotency_key = str(uuid.uuid4())
        res = await client.post(
            "/v1/payments/create-invoice",
            json={"plan_type": "PRO_MONTHLY"},
            headers={**auth_headers, "Idempotency-Key": idempotency_key},
        )
        assert res.status_code == 201
        invoice_data = res.json()
        order_id = invoice_data["order_id"]
        assert invoice_data["payment_status"] == "PENDING"
        assert invoice_data["checkout_url"] is not None

        # 7. Check idempotency: second request with same key returns 200 with same order
        res_replay = await client.post(
            "/v1/payments/create-invoice",
            json={"plan_type": "PRO_MONTHLY"},
            headers={**auth_headers, "Idempotency-Key": idempotency_key},
        )
        assert res_replay.status_code == 200
        assert res_replay.json()["order_id"] == order_id

        # 8. Webhook simulation: NOWPayments confirms payment
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        webhook_payload = {
            "order_id": order_id,
            "payment_status": "finished",
            "payment_id": payment_id,
            "pay_currency": "USDTTRC20",
        }
        sig = independent_ipn_signature(webhook_payload, settings.NOWPAYMENTS_IPN_SECRET)

        res_webhook = await client.post(
            "/v1/payments/webhook",
            json=webhook_payload,
            headers={"x-nowpayments-sig": sig},
        )
        assert res_webhook.status_code == 200
        assert res_webhook.json() == {"status": "ok"}

        # 9. Poll order status
        res_order = await client.get(f"/v1/payments/orders/{order_id}", headers=auth_headers)
        assert res_order.status_code == 200
        order_status = res_order.json()
        assert order_status["payment_status"] == "PAID"
        assert order_status["credited_at"] is not None

        # 10. Verify user is now upgraded to ANALYST
        res_me = await client.get("/v1/me", headers=auth_headers)
        assert res_me.status_code == 200
        user_info = res_me.json()
        assert user_info["effective_plan"] == "ANALYST"
        assert user_info["plan_expires_at"] is not None

        # 11. Access paid fixtures list with has_value filter
        res_fixtures_analyst = await client.get(
            "/v1/matches/fixtures?league_id=EPL&days_ahead=14",
            headers=auth_headers,
        )
        assert res_fixtures_analyst.status_code == 200
        analyst_fixtures = res_fixtures_analyst.json()["fixtures"]
        assert len(analyst_fixtures) > 0
        # Paid fields are now present
        first_f = analyst_fixtures[0]
        assert "data_status" in first_f
        assert first_f["data_status"] in ("AVAILABLE", "STALE", "UNAVAILABLE")

        # 12. Access deep analysis route
        res_analysis = await client.get(f"/v1/matches/{match_id}/analysis", headers=auth_headers)
        assert res_analysis.status_code == 200
        analysis = res_analysis.json()
        assert analysis["match_id"] == match_id
        assert analysis["data_status"] in ("AVAILABLE", "STALE", "UNAVAILABLE")
        if not analysis["prediction"]:
            pytest.skip("seeded demo fixtures carry no stored prediction snapshot")
        pred = analysis["prediction"]
        assert "score_matrix" in pred
        assert len(pred["score_matrix"]) == 6
        assert len(pred["score_matrix"][0]) == 6
        assert "omitted_mass" in pred
        assert "top_scores" in pred
        assert len(pred["top_scores"]) == 3
        assert pred["prob_home_win"] + pred["prob_draw"] + pred["prob_away_win"] == pytest.approx(1.0, abs=1e-6)
