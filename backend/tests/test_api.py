import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta
from app.main import app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import User, CryptoInvoice
from app.services.nowpayments import verify_nowpayments_signature, canonical_json_dumps
import hmac
import hashlib


@pytest.mark.asyncio
async def test_auth_workflow_and_errors():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123456!"

        # 1. Register short password -> 422
        res = await client.post("/v1/auth/register", json={"email": test_email, "password": "short"})
        assert res.status_code == 422
        assert "error" in res.json()
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

        # 2. Register success -> 201
        res = await client.post("/v1/auth/register", json={"email": test_email, "password": password})
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == test_email.lower()
        user_id = data["id"]

        # 3. Duplicate email -> 409
        res = await client.post("/v1/auth/register", json={"email": test_email.upper(), "password": password})
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "EMAIL_EXISTS"

        # 4. Login wrong password -> 401
        res = await client.post("/v1/auth/login", json={"email": test_email, "password": "WrongPassword123!"})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHENTICATED"

        # 5. Login success -> 200
        res = await client.post("/v1/auth/login", json={"email": test_email, "password": password})
        assert res.status_code == 200
        token_data = res.json()
        assert "access_token" in token_data
        token = token_data["access_token"]

        # 6. GET /me -> FREE
        res = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        me = res.json()
        assert me["email"] == test_email.lower()
        assert me["effective_plan"] == "FREE"


@pytest.mark.asyncio
async def test_fixtures_access_and_filter():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Anonymous get fixtures -> 200 base fields only
        res = await client.get("/v1/matches/fixtures?league_id=EPL&days_ahead=7")
        assert res.status_code == 200
        data = res.json()
        assert "total" in data
        assert "fixtures" in data
        if data["fixtures"]:
            f0 = data["fixtures"][0]
            assert "match_id" in f0
            assert "home_team" in f0
            assert "away_team" in f0
            # Free view omits data_status, prediction, comparison
            assert f0.get("data_status") is None
            assert f0.get("prediction") is None
            assert f0.get("comparison") is None

        # 2. Unsupported league -> 422
        res = await client.get("/v1/matches/fixtures?league_id=LA_LIGA")
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

        # 3. Supplying has_value anonymously -> 401
        res = await client.get("/v1/matches/fixtures?has_value=true")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHENTICATED"

        # 4. Supplying has_value with FREE user -> 403
        test_email = f"free_{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/v1/auth/register", json={"email": test_email, "password": "Password123456!"})
        login_res = await client.post("/v1/auth/login", json={"email": test_email, "password": "Password123456!"})
        token = login_res.json()["access_token"]

        res = await client.get("/v1/matches/fixtures?has_value=true", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "PASS_REQUIRED"

        # 5. Analysis route with FREE user -> 403
        res = await client.get("/v1/matches/EPL_DEMO_001/analysis", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "PASS_REQUIRED"


@pytest.mark.asyncio
async def test_payment_and_analyst_entitlement():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create user
        test_email = f"analyst_{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/v1/auth/register", json={"email": test_email, "password": "Password123456!"})
        login_res = await client.post("/v1/auth/login", json={"email": test_email, "password": "Password123456!"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Mock settings for payment
        settings.NOWPAYMENTS_API_KEY = "sandbox_test_key"
        settings.NOWPAYMENTS_IPN_SECRET = "test_ipn_secret_key_123"

        # 1. Invalid Idempotency-Key -> 422
        res = await client.post(
            "/v1/payments/create-invoice",
            json={"plan_type": "PRO_MONTHLY"},
            headers={**headers, "Idempotency-Key": "not-a-uuid"},
        )
        assert res.status_code == 422

        # 2. Valid create-invoice -> 201
        req_key = str(uuid.uuid4())
        res = await client.post(
            "/v1/payments/create-invoice",
            json={"plan_type": "PRO_MONTHLY"},
            headers={**headers, "Idempotency-Key": req_key},
        )
        assert res.status_code == 201
        inv_data = res.json()
        assert inv_data["plan_type"] == "PRO_MONTHLY"
        assert float(inv_data["amount_usd"]) == 29.0
        assert inv_data["payment_status"] == "PENDING"
        assert inv_data["checkout_url"] is not None
        order_id = inv_data["order_id"]

        # 3. Repeated idempotency key with same plan -> 200
        res = await client.post(
            "/v1/payments/create-invoice",
            json={"plan_type": "PRO_MONTHLY"},
            headers={**headers, "Idempotency-Key": req_key},
        )
        assert res.status_code == 200
        assert res.json()["order_id"] == order_id

        # 4. Repeated idempotency key with different plan -> 409
        res = await client.post(
            "/v1/payments/create-invoice",
            json={"plan_type": "PRO_SEASON"},
            headers={**headers, "Idempotency-Key": req_key},
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

        # 5. Check order route -> 200
        res = await client.get(f"/v1/payments/orders/{order_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["order_id"] == order_id
        assert res.json()["payment_status"] == "PENDING"

        # 6. Webhook simulation with invalid signature -> 400
        unique_pay_id = f"pay_{uuid.uuid4().hex[:10]}"
        webhook_body = {
            "order_id": order_id,
            "payment_status": "finished",
            "payment_id": unique_pay_id,
        }
        res = await client.post(
            "/v1/payments/webhook",
            json=webhook_body,
            headers={"x-nowpayments-sig": "invalid_signature"},
        )
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_SIGNATURE"

        # 7. Webhook with valid signature -> 200 & grants access
        canon_json = canonical_json_dumps(webhook_body)
        valid_sig = hmac.new(
            settings.NOWPAYMENTS_IPN_SECRET.encode(),
            canon_json.encode(),
            hashlib.sha512,
        ).hexdigest()

        res = await client.post(
            "/v1/payments/webhook",
            json=webhook_body,
            headers={"x-nowpayments-sig": valid_sig},
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

        # 8. Verify user is now active ANALYST
        res = await client.get("/v1/me", headers=headers)
        assert res.status_code == 200
        assert res.json()["effective_plan"] == "ANALYST"
        assert res.json()["plan_expires_at"] is not None

        # 9. Verify duplicate finished notification -> 200 idempotent (does not add extra duration)
        prev_expiry = res.json()["plan_expires_at"]
        res = await client.post(
            "/v1/payments/webhook",
            json=webhook_body,
            headers={"x-nowpayments-sig": valid_sig},
        )
        assert res.status_code == 200
        res = await client.get("/v1/me", headers=headers)
        assert res.json()["plan_expires_at"] == prev_expiry

        # 10. Access analysis route as ANALYST -> 200
        res = await client.get("/v1/matches/EPL_DEMO_001/analysis", headers=headers)
        assert res.status_code == 200
        analysis_data = res.json()
        assert analysis_data["match_id"] == "EPL_DEMO_001"
        assert analysis_data["data_status"] in ("AVAILABLE", "STALE", "UNAVAILABLE")
        if analysis_data["prediction"]:
            assert "score_matrix" in analysis_data["prediction"]
            assert len(analysis_data["prediction"]["score_matrix"]) == 6
            assert "omitted_mass" in analysis_data["prediction"]
            assert "top_scores" in analysis_data["prediction"]
