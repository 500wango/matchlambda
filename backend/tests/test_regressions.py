"""Regression coverage for defects being fixed in parallel.

Some assertions here describe the *target* behaviour of fixes that may not have
landed yet; a red test names the pending fix rather than being relaxed. See the
accompanying report for the current green/red split.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import security
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.main import app
from app.math import backtest
from app.models import AuditLog, CryptoInvoice, User


async def _register_and_login(client, prefix):
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123456!"
    await client.post("/v1/auth/register", json={"email": email, "password": password})
    login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return email, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _promote_to_admin(email):
    async with AsyncSessionLocal() as session:
        await session.execute(
            User.__table__.update().where(User.email == email).values(is_admin=True)
        )
        await session.commit()


# --- D1: idempotency-key race ------------------------------------------------

async def test_concurrent_create_invoice_same_key_never_5xx(monkeypatch):
    monkeypatch.setattr(settings, "NOWPAYMENTS_API_KEY", "regression_sandbox_key")
    monkeypatch.setattr(settings, "PAYMENTS_SANDBOX_MODE", True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        _, headers = await _register_and_login(client, "idem")
        key = str(uuid.uuid4())

        async def create():
            return await client.post(
                "/v1/payments/create-invoice",
                json={"plan_type": "PRO_MONTHLY"},
                headers={**headers, "Idempotency-Key": key},
            )

        first, second = await asyncio.gather(create(), create(), return_exceptions=True)

    results = [first, second]
    for res in results:
        assert not isinstance(res, Exception), f"concurrent request raised: {res!r}"
        assert res.status_code < 500, f"idempotent create must not 5xx, got {res.status_code}: {res.text}"
        assert res.status_code in (200, 201, 202), res.text
    assert results[0].json()["order_id"] == results[1].json()["order_id"]


# --- D2: paywall -------------------------------------------------------------

async def test_anonymous_paywall_hides_predictions_and_blocks_paid_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/v1/matches/fixtures?league_id=EPL&days_ahead=14")
        assert res.status_code == 200
        fixtures = res.json()["fixtures"]
        assert fixtures, "seeded demo fixtures required for the paywall check"
        for fixture in fixtures:
            assert fixture.get("prediction") is None
            assert fixture.get("comparison") is None

        for endpoint in (
            "/v1/picks/daily",
            "/v1/alpha/picks",
            "/v1/analytics/backtest",
            "/v1/alpha/scanner",
        ):
            res = await client.get(endpoint)
            assert res.status_code == 401, f"{endpoint} -> {res.status_code}"
            assert res.json()["error"]["code"] == "UNAUTHENTICATED"


# --- D3: backtest status semantics ------------------------------------------

def test_dataset_backtest_reports_data_unavailable_when_dataset_missing(monkeypatch):
    monkeypatch.setattr(backtest, "get_historical_dataset_rows", lambda: [])
    res = backtest.calculate_dataset_backtest(initial_bankroll=1000.0, years=10)
    assert res["status"] == "DATA_UNAVAILABLE"


def _synthetic_no_edge_rows(count: int = 45) -> list:
    rows = []
    for i in range(count):
        home, away = ("TeamA", "TeamB") if i % 2 == 0 else ("TeamB", "TeamA")
        rows.append(
            {
                "Div": "E0",
                "Season": "2023-2024",
                "Date": f"{1 + (i % 28):02d}/01/2024",
                "HomeTeam": home,
                "AwayTeam": away,
                "FTHG": "1",
                "FTAG": "1",
                "FTR": "D",
                "PSH": "1.90",
                "PSD": "3.40",
                "PSA": "4.20",
                "PSCH": "1.90",
                "PSCD": "3.40",
                "PSCA": "4.20",
            }
        )
    return rows


def test_dataset_backtest_reports_model_no_edge_on_unprofitable_sample(monkeypatch):
    monkeypatch.setattr(
        backtest, "get_historical_dataset_rows", lambda: _synthetic_no_edge_rows()
    )
    # An unreachable odds band keeps every fixture evaluable but unbet, so the
    # model computes a result with zero ROI and must report MODEL_NO_EDGE.
    res = backtest.calculate_dataset_backtest(
        initial_bankroll=1000.0,
        min_ev=0.04,
        max_ev=0.40,
        min_odds=1000.0,
        max_odds=1000.0,
        years=10,
    )
    assert res["status"] == "MODEL_NO_EDGE", res.get("message")
    assert res["summary"]["total_bets"] == 0
    assert res["summary"]["roi_pct"] <= 0


# --- D4: JWT algorithm whitelist --------------------------------------------

def test_safe_jwt_algorithm_whitelist_excludes_none():
    assert "none" not in security.SAFE_JWT_ALGORITHMS
    assert security.JWT_ALGORITHM in security.SAFE_JWT_ALGORITHMS


def test_unsafe_jwt_algorithm_fails_startup(monkeypatch):
    import importlib

    monkeypatch.setattr(settings, "JWT_ALGORITHM", "none")
    with pytest.raises(RuntimeError):
        importlib.reload(security)
    # Restore a valid module state for the remainder of the session.
    monkeypatch.undo()
    importlib.reload(security)
    assert security.JWT_ALGORITHM == "HS256"


def test_none_signed_token_never_authenticates():
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": now + timedelta(hours=1),
            "iat": now,
            "iss": security.TOKEN_ISSUER,
        },
        None,
        algorithm="none",
    )
    assert security.decode_access_token(forged) is None


# --- D5: resolver determinism -----------------------------------------------

async def test_resolver_is_deterministic_for_seeded_alias():
    from app.etl.resolver import TeamResolver

    async with AsyncSessionLocal() as session:
        first = await TeamResolver.resolve_team(session, "the_odds_api", "AC Milan", "Europe")
        second = await TeamResolver.resolve_team(session, "the_odds_api", "AC Milan", "Europe")
    assert first is not None
    assert first == second


# --- D6: audit rows persist ------------------------------------------------

async def test_manual_grant_writes_audit_log():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email, _ = await _register_and_login(client, "audit")
        await _promote_to_admin(email)
        login = await client.post(
            "/v1/auth/login", json={"email": email, "password": "Password123456!"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        order_id = f"ORDER_AUDIT_{uuid.uuid4().hex[:8]}"
        async with AsyncSessionLocal() as session:
            user = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one()
            session.add(
                CryptoInvoice(
                    user_id=user.id,
                    order_id=order_id,
                    request_key=uuid.uuid4(),
                    plan_type="PRO_MONTHLY",
                    amount_usd=29.00,
                    duration_days=30,
                    payment_status="PENDING",
                )
            )
            await session.commit()

        grant = await client.post(f"/v1/admin/billing/invoices/{order_id}/grant", headers=headers)
        assert grant.status_code == 200, grant.text

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == "MANUAL_GRANT_INVOICE",
                    AuditLog.target == order_id,
                )
            )
        ).scalars().all()
    assert rows, "manual grant must persist an audit_logs row"
