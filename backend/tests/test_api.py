import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta
from app.main import app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models import User
from tests.ipn_sign import independent_ipn_signature


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
        # The isolated test DB is seeded with SCHEDULED EPL demo fixtures.
        assert data["fixtures"], "seeded demo fixtures must be present"
        f0 = data["fixtures"][0]
        assert "match_id" in f0
        assert "home_team" in f0
        assert "away_team" in f0
        # Free view omits data_status, prediction, comparison
        assert f0.get("data_status") is None
        assert f0.get("prediction") is None
        assert f0.get("comparison") is None

        # 2. Unsupported league -> 422
        res = await client.get("/v1/matches/fixtures?league_id=UNKNOWN_LEAGUE")
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"

        # 2b. Newly supported league (LA_LIGA) -> 200
        res = await client.get("/v1/matches/fixtures?league_id=LA_LIGA")
        assert res.status_code == 200

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

        for endpoint in ("/v1/alpha/scanner", "/v1/analytics/backtest"):
            res = await client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
            assert res.status_code == 403
            assert res.json()["error"]["code"] == "PASS_REQUIRED"


@pytest.mark.asyncio
async def test_payment_and_analyst_entitlement(monkeypatch):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create user
        test_email = f"analyst_{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/v1/auth/register", json={"email": test_email, "password": "Password123456!"})
        login_res = await client.post("/v1/auth/login", json={"email": test_email, "password": "Password123456!"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        monkeypatch.setattr(settings, "NOWPAYMENTS_API_KEY", "sandbox_test_key")
        monkeypatch.setattr(settings, "PAYMENTS_SANDBOX_MODE", True)
        monkeypatch.setattr(settings, "NOWPAYMENTS_IPN_SECRET", "test_ipn_secret_key_123")

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
            "pay_currency": "USDTTRC20",
        }
        res = await client.post(
            "/v1/payments/webhook",
            json=webhook_body,
            headers={"x-nowpayments-sig": "invalid_signature"},
        )
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_SIGNATURE"

        # 7. Webhook with an independent signature -> 200 & grants access
        valid_sig = independent_ipn_signature(webhook_body, settings.NOWPAYMENTS_IPN_SECRET)

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
        res_fix = await client.get("/v1/matches/fixtures?league_id=EPL&days_ahead=14")
        assert res_fix.status_code == 200
        first_match_id = res_fix.json()["fixtures"][0]["match_id"]

        res = await client.get(f"/v1/matches/{first_match_id}/analysis", headers=headers)
        assert res.status_code == 200
        analysis_data = res.json()
        assert analysis_data["match_id"] == first_match_id
        assert analysis_data["data_status"] in ("AVAILABLE", "STALE", "UNAVAILABLE")
        if not analysis_data["prediction"]:
            pytest.skip("seeded demo fixture has no stored prediction snapshot")
        assert "score_matrix" in analysis_data["prediction"]
        assert len(analysis_data["prediction"]["score_matrix"]) == 6
        assert "omitted_mass" in analysis_data["prediction"]
        assert "top_scores" in analysis_data["prediction"]


@pytest.mark.asyncio
async def test_daily_picks_and_parlays():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"picks_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123456!"
        await client.post("/v1/auth/register", json={"email": email, "password": password})
        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            user.plan_tier = "ANALYST"
            user.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            await db.commit()
        login_res = await client.post("/v1/auth/login", json={"email": email, "password": password})
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        anonymous = await client.get("/v1/picks/daily")
        assert anonymous.status_code == 401

        res = await client.get("/v1/picks/daily", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "summary" in data
        assert "bankers" in data
        assert "values" in data
        assert "underdogs" in data
        assert "goals" in data
        assert "parlays" in data

        if not data["bankers"]:
            pytest.skip("no banker picks qualified against the seeded fixtures")
        b0 = data["bankers"][0]
        assert "category" in b0
        assert b0["category"] == "BANKER"
        assert "reasoning" in b0
        assert "【稳胆核心理由】" in b0["reasoning"]

        if not data["parlays"]:
            pytest.skip("no parlays qualified against the seeded fixtures")
        p0 = data["parlays"][0]
        assert "combined_odds" in p0
        assert "win_probability_pct" in p0
        assert "copy_text" in p0
        assert len(p0["legs"]) >= 2

        # 2. Fetch daily picks in English
        res_en = await client.get("/v1/picks/daily?lang=en", headers=headers)
        assert res_en.status_code == 200
        data_en = res_en.json()
        assert data_en["lang"] == "en"
        if not data_en["bankers"]:
            pytest.skip("no banker picks qualified against the seeded fixtures")
        b0_en = data_en["bankers"][0]
        assert "Banker Rationale" in b0_en["reasoning"]
        assert "Daily Banker" in b0_en["category_label"]
        if not data_en["parlays"]:
            pytest.skip("no parlays qualified against the seeded fixtures")
        p0_en = data_en["parlays"][0]
        assert "Ticket" in p0_en["copy_text"] or "Parlay" in p0_en["copy_text"]

