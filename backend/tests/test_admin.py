import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models import User, Team, CryptoInvoice


@pytest.mark.asyncio
async def test_admin_rbac_and_operations():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a regular user
        user_email = f"norm_{uuid.uuid4().hex[:8]}@example.com"
        pwd = "Password123456!"
        reg = await client.post("/v1/auth/register", json={"email": user_email, "password": pwd})
        assert reg.status_code == 201

        login = await client.post("/v1/auth/login", json={"email": user_email, "password": pwd})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Check /me -> is_admin is False
        me_res = await client.get("/v1/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["is_admin"] is False

        # 3. Access admin endpoint -> 403 Forbidden
        etl_res = await client.get("/v1/admin/etl/leagues", headers=headers)
        assert etl_res.status_code == 403
        assert etl_res.json()["error"]["code"] == "FORBIDDEN"

        # 4. Promote user to is_admin in DB
        async with AsyncSessionLocal() as session:
            await session.execute(
                User.__table__.update().where(User.email == user_email).values(is_admin=True)
            )
            await session.commit()

        # 5. Access admin endpoint -> 200 OK
        etl_res = await client.get("/v1/admin/etl/leagues", headers=headers)
        assert etl_res.status_code == 200
        data = etl_res.json()
        assert "leagues" in data
        assert any(l["id"] == "EPL" for l in data["leagues"])

        # 6. Test CSV Preview with an unknown team
        unknown_team = f"Unknown_{uuid.uuid4().hex[:6]}"
        sample_csv = (
            "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,PSH,PSD,PSA\n"
            f"E0,15/09/2024,Arsenal,{unknown_team},2,1,H,1.50,4.20,6.50\n"
        )
        files = {"file": ("test.csv", sample_csv.encode("utf-8"), "text/csv")}
        prev_res = await client.post(
            "/v1/admin/etl/upload-csv/preview",
            files=files,
            data={"league_id": "EPL"},
            headers=headers,
        )
        assert prev_res.status_code == 200
        prev_data = prev_res.json()
        assert prev_data["total_rows"] == 1
        assert unknown_team in prev_data["unknown_teams"]

        # 7. Commit CSV with alias mapping
        commit_res = await client.post(
            "/v1/admin/etl/upload-csv/commit",
            json={
                "csv_content": sample_csv,
                "league_id": "EPL",
                "alias_mappings": {unknown_team: "chelsea"},
                "auto_train": False,
            },
            headers=headers,
        )
        assert commit_res.status_code == 200
        c_data = commit_res.json()
        assert c_data["matches_inserted"] + c_data["matches_updated"] == 1
        assert c_data["aliases_created"] >= 0

        # 8. Test Model Overview endpoint
        model_res = await client.get("/v1/admin/model/overview", headers=headers)
        assert model_res.status_code == 200
        assert "leagues" in model_res.json()

        # 9. Test Manual Invoice Grant workflow
        order_id = f"ORDER_{uuid.uuid4().hex[:10]}"
        async with AsyncSessionLocal() as session:
            inv = CryptoInvoice(
                user_id=uuid.UUID(reg.json()["id"]),
                order_id=order_id,
                request_key=uuid.uuid4(),
                plan_type="PRO_MONTHLY",
                amount_usd=49.00,
                duration_days=30,
                payment_status="PENDING",
            )
            session.add(inv)
            await session.commit()

        # Check invoices list
        invs_res = await client.get("/v1/admin/billing/invoices", headers=headers)
        assert invs_res.status_code == 200
        assert any(i["order_id"] == order_id for i in invs_res.json())

        # Grant invoice
        grant_res = await client.post(f"/v1/admin/billing/invoices/{order_id}/grant", headers=headers)
        assert grant_res.status_code == 200
        g_data = grant_res.json()
        assert g_data["plan_tier"] == "ANALYST"
        assert g_data["plan_expires_at"] is not None

        second_grant = await client.post(f"/v1/admin/billing/invoices/{order_id}/grant", headers=headers)
        assert second_grant.status_code == 409
        assert second_grant.json()["error"]["code"] == "CONFLICT"

        # Verify user /me now shows effective ANALYST
        me_after = await client.get("/v1/me", headers=headers)
        assert me_after.json()["effective_plan"] == "ANALYST"

        # 10. Test Settings: Add new League
        new_league_id = f"TEST_L_{uuid.uuid4().hex[:6].upper()}"
        create_l_res = await client.post(
            "/v1/admin/settings/leagues",
            json={
                "id": new_league_id,
                "name": "Test Super League",
                "country": "Testland",
                "active": True,
            },
            headers=headers,
        )
        assert create_l_res.status_code == 201
        assert create_l_res.json()["league"]["id"] == new_league_id

        # Update league (toggle active)
        patch_l_res = await client.patch(
            f"/v1/admin/settings/leagues/{new_league_id}",
            json={"active": False, "name": "Renamed Super League"},
            headers=headers,
        )
        assert patch_l_res.status_code == 200
        assert patch_l_res.json()["league"]["active"] is False

        # Add team
        team_id = f"team_{uuid.uuid4().hex[:6]}"
        team_res = await client.post(
            "/v1/admin/settings/teams",
            json={
                "id": team_id,
                "canonical_name": "Test United",
                "country": "Testland",
            },
            headers=headers,
        )
        assert team_res.status_code == 201

        # Delete test league (no matches, should succeed)
        del_res = await client.delete(f"/v1/admin/settings/leagues/{new_league_id}", headers=headers)
        assert del_res.status_code == 200

        # 11. Test Alias Hub: Create, List, and Delete
        alias_name = f"Test FC Alias {uuid.uuid4().hex[:4]}"
        create_alias_res = await client.post(
            "/v1/admin/settings/aliases",
            json={
                "team_id": team_id,
                "external_name": alias_name,
                "source_name": "MANUAL_ADMIN",
            },
            headers=headers,
        )
        assert create_alias_res.status_code == 201
        alias_id = create_alias_res.json()["alias"]["id"]

        list_aliases_res = await client.get(f"/v1/admin/settings/aliases?search={alias_name}", headers=headers)
        assert list_aliases_res.status_code == 200
        listed = list_aliases_res.json()
        assert any(a["id"] == alias_id for a in listed["aliases"])
        assert listed["total"] == len(listed["aliases"])

        del_alias_res = await client.delete(f"/v1/admin/settings/aliases/{alias_id}", headers=headers)
        assert del_alias_res.status_code == 200

        async with AsyncSessionLocal() as db:
            orphan = await db.get(Team, team_id)
            if orphan is not None:
                await db.delete(orphan)
                await db.commit()

        # 12. Test Dynamic Quant & Risk Settings
        get_quant_res = await client.get("/v1/admin/settings/config/quant-risk", headers=headers)
        assert get_quant_res.status_code == 200
        assert "value_scanner_min_ev" in get_quant_res.json()

        put_quant_res = await client.put(
            "/v1/admin/settings/config/quant-risk",
            json={
                "value_scanner_min_ev": 0.06,
                "kelly_fraction": 0.25,
                "max_stake_cap": 0.04,
                "dixon_coles_decay_xi": 0.0020,
                "min_training_matches": 70,
            },
            headers=headers,
        )
        assert put_quant_res.status_code == 200
        assert put_quant_res.json()["config"]["kelly_fraction"] == 0.25
        restore_quant = await client.put(
            "/v1/admin/settings/config/quant-risk",
            json={
                "value_scanner_min_ev": get_quant_res.json()["value_scanner_min_ev"],
                "kelly_fraction": get_quant_res.json()["kelly_fraction"],
                "max_stake_cap": get_quant_res.json()["max_stake_cap"],
                "dixon_coles_decay_xi": get_quant_res.json()["dixon_coles_decay_xi"],
                "min_training_matches": get_quant_res.json()["min_training_matches"],
            },
            headers=headers,
        )
        assert restore_quant.status_code == 200

        # 13. Test Data Provider & Quota Check
        get_prov_res = await client.get("/v1/admin/settings/config/data-provider", headers=headers)
        assert get_prov_res.status_code == 200

        quota_res = await client.get("/v1/admin/settings/provider/quota", headers=headers)
        assert quota_res.status_code == 200
        assert "status" in quota_res.json()

        # 14. Test Monetization Config
        get_mon_res = await client.get("/v1/admin/settings/config/monetization", headers=headers)
        assert get_mon_res.status_code == 200

        put_mon_res = await client.put(
            "/v1/admin/settings/config/monetization",
            json={
                "monthly_price_usd": 39.0,
                "season_price_usd": 179.0,
                "new_user_trial_days": 5,
                "accepted_tokens": ["USDTTRC20", "BTC"],
            },
            headers=headers,
        )
        assert put_mon_res.status_code == 200
        assert put_mon_res.json()["config"]["monthly_price_usd"] == 39.0

        # Reset monetization config to defaults so other test suites are isolated
        await client.put(
            "/v1/admin/settings/config/monetization",
            json={
                "monthly_price_usd": 29.0,
                "season_price_usd": 149.0,
                "new_user_trial_days": 0,
                "accepted_tokens": ["USDTTRC20", "USDTERC20", "USDC", "BTC"],
            },
            headers=headers,
        )

        # 15. Test Notifications & Test Ping
        get_notif_res = await client.get("/v1/admin/settings/config/notifications", headers=headers)
        assert get_notif_res.status_code == 200

        test_notif_res = await client.post(
            "/v1/admin/settings/notifications/test",
            json={"channel": "all", "custom_message": "Ping Test"},
            headers=headers,
        )
        assert test_notif_res.status_code == 200
        assert "results" in test_notif_res.json()

        # 16. Test Cache Purge & Audit Logs
        purge_res = await client.post("/v1/admin/settings/cache/purge", headers=headers)
        assert purge_res.status_code == 200
        assert purge_res.json()["status"] in ("SUCCESS", "ERROR")

        audit_res = await client.get("/v1/admin/settings/audit-logs", headers=headers)
        assert audit_res.status_code == 200
        assert len(audit_res.json()["logs"]) > 0


@pytest.mark.asyncio
async def test_new_leagues_normalization_and_preview():
    from app.api.v1.admin.etl import _normalize_new_league_csv, LEAGUE_CODE_MAP

    assert "B1" in LEAGUE_CODE_MAP
    assert "AUT" in LEAGUE_CODE_MAP
    assert "DNK" in LEAGUE_CODE_MAP
    assert "NOR" in LEAGUE_CODE_MAP
    assert "SWE" in LEAGUE_CODE_MAP

    # Test multi-season new CSV format normalization (used by AUT, DNK, NOR, SWE)
    raw_new_csv = (
        "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PH,PD,PA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA\n"
        "Austria,Bundesliga,2024/2025,18/08/2024,16:00,Rapid Vienna,Salzburg,2,1,H,3.20,3.50,2.15,3.30,3.60,2.20,3.15,3.45,2.10\n"
        "Austria,Bundesliga,2023/2024,12/08/2023,16:00,Rapid Vienna,LASK,1,1,D,2.40,3.30,2.90,2.50,3.40,3.00,2.35,3.25,2.85\n"
    )

    normalized_2425 = _normalize_new_league_csv(raw_new_csv, "2425")
    assert "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,PSH,PSD,PSA" in normalized_2425
    assert ",18/08/2024,16:00,Rapid Vienna,Salzburg,2,1,H,3.20,3.50,2.15" in normalized_2425
    assert "2023/2024" not in normalized_2425
    assert "LASK" not in normalized_2425

    # Test normalization with MaxH/MaxD/MaxA fallback when PSH/PSD/PSA are missing
    raw_fallback_csv = (
        "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PH,PD,PA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA\n"
        "Denmark,Superliga,2024/2025,21/07/2024,17:00,FC Copenhagen,Viborg,3,2,H,,,,,2.10,3.40,3.50,2.05,3.30,3.40\n"
    )
    normalized_dnk = _normalize_new_league_csv(raw_fallback_csv, "2425")
    assert "FC Copenhagen,Viborg,3,2,H" in normalized_dnk
    assert "2.10,3.40,3.50" in normalized_dnk


@pytest.mark.asyncio
async def test_league_gate_admin_and_public_exposure():
    # PRD §2.1: admin can inspect/retune thresholds, refresh the snapshot, and
    # the public leagues endpoints expose the resulting eligibility flags.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"gate_{uuid.uuid4().hex[:8]}@example.com"
        pwd = "Password123456!"
        await client.post("/v1/auth/register", json={"email": email, "password": pwd})
        login = await client.post("/v1/auth/login", json={"email": email, "password": pwd})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Gate config is admin-only
        forbidden = await client.get("/v1/admin/settings/config/league-gate", headers=headers)
        assert forbidden.status_code == 403

        async with AsyncSessionLocal() as session:
            await session.execute(
                User.__table__.update().where(User.email == email).values(is_admin=True)
            )
            await session.commit()

        get_res = await client.get("/v1/admin/settings/config/league-gate", headers=headers)
        assert get_res.status_code == 200
        body = get_res.json()
        assert "min_finished_matches" in body["thresholds"]
        assert "provisional_leagues" in body["defaults"]
        original = dict(body["thresholds"])

        put_res = await client.put(
            "/v1/admin/settings/config/league-gate",
            json={
                "min_finished_matches": 250,
                "min_odds_coverage": original.get("min_odds_coverage", 0.40),
                "min_eval_samples": original.get("min_eval_samples", 40),
                "max_brier_vs_market_ratio": original.get("max_brier_vs_market_ratio", 1.05),
                "provisional_leagues": ["epl", "championship"],
            },
            headers=headers,
        )
        assert put_res.status_code == 200
        assert put_res.json()["config"]["min_finished_matches"] == 250
        # Validator normalizes league codes to uppercase
        assert put_res.json()["config"]["provisional_leagues"] == ["EPL", "CHAMPIONSHIP"]

        refresh_res = await client.post("/v1/admin/settings/league-gate/refresh", headers=headers)
        assert refresh_res.status_code == 200
        snapshot = refresh_res.json()["snapshot"]
        leagues = snapshot["leagues"]
        # Provisional leagues unlock on the frozen dataset backtest basis...
        assert leagues["EPL"]["eligible"] is True
        assert leagues["EPL"]["basis"] == "PROVISIONAL_DATASET_BACKTEST"
        # ...while every other league stays behind the live-evidence bar.
        pending = [lid for lid, info in leagues.items() if not info["eligible"]]
        assert pending, "expected at least one gated league while live eval samples are thin"

        # Restore the pre-test thresholds (snapshot keeps the refreshed view)
        restore = await client.put(
            "/v1/admin/settings/config/league-gate",
            json=original,
            headers=headers,
        )
        assert restore.status_code == 200

        # Public audit endpoint reflects the stored snapshot
        elig_res = await client.get("/v1/matches/leagues/eligibility")
        assert elig_res.status_code == 200
        assert elig_res.json()["status"] == "READY"

        # League list carries the eligibility flags consumed by the frontend gate
        rows_res = await client.get("/v1/matches/leagues")
        assert rows_res.status_code == 200
        rows = rows_res.json()
        assert rows and all(isinstance(r.get("eligible"), bool) for r in rows)
        epl_rows = [r for r in rows if r["id"] == "EPL"]
        if epl_rows:
            assert epl_rows[0]["eligible"] is True


