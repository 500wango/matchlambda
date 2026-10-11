"""Test-suite isolation helpers.

Every database-backed test runs against a dedicated throwaway database
(default ``<POSTGRES_DB>_test``) that is created for the session and dropped
afterwards. The development database named in ``.env`` is never opened, so a
test run cannot mutate real users, invoices, audits or demo kickoffs.

Session setup requires permission to CREATE/DROP DATABASE on the server's
``postgres`` maintenance database (or a pre-created database named by
``TEST_POSTGRES_DB``). When that permission is missing the fixture fails with
an actionable message rather than silently falling back to the dev database.
"""
import asyncio
import os
import re
import sys

import pytest

_DB_MODULES = {
    "test_api.py",
    "test_admin.py",
    "test_e2e_journey.py",
    "test_payments_reconcile.py",
    "test_etl_multi_bookmaker.py",
    "test_rate_limiter.py",
    "test_regressions.py",
}

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _admin_connect(settings, dbname):
    import psycopg2

    return psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=dbname,
    )


def _drop_and_create(settings, test_db: str) -> None:
    """Rebuild the test database so every run starts from a known-empty state."""
    from psycopg2 import errors

    if not _IDENT_RE.match(test_db):
        raise RuntimeError(
            f"Refusing to use unsafe test database name {test_db!r}; it must match "
            "[A-Za-z_][A-Za-z0-9_]*."
        )

    conn = _admin_connect(settings, "postgres")
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (test_db,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{test_db}"')
            cur.execute(
                f'CREATE DATABASE "{test_db}" OWNER "{settings.POSTGRES_USER}"'
            )
    except (errors.InsufficientPrivilege, errors.InvalidCatalogName) as exc:
        raise RuntimeError(
            "Database test isolation needs CREATE DATABASE privilege.\n"
            f"  server:    {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}\n"
            f"  db user:   {settings.POSTGRES_USER}\n"
            f"  test db:   {test_db}\n"
            "Grant CREATEDB to the role (ALTER ROLE ... CREATEDB) or pre-create an "
            "empty database and point TEST_POSTGRES_DB at it, then re-run. "
            "Tests never fall back to the development database.\n"
            f"  original error: {exc}"
        ) from exc
    finally:
        conn.close()


def _drop_database(settings, test_db: str) -> None:
    if not _IDENT_RE.match(test_db):
        return
    try:
        conn = _admin_connect(settings, "postgres")
    except Exception:
        return
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (test_db,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{test_db}"')
    except Exception:
        pass
    finally:
        conn.close()


def _rebind_async_engine_symbol(engine) -> None:
    """Modules that did ``from app.core.database import async_engine`` keep the
    old object; repoint those bindings at the isolated engine."""
    for module in list(sys.modules.values()):
        if module is None:
            continue
        try:
            if getattr(module, "async_engine", None) is not None and hasattr(
                module, "__name__"
            ):
                if module.__name__.startswith(("app.", "tests", "test_")):
                    setattr(module, "async_engine", engine)
        except Exception:
            continue


def _create_schema_and_seed() -> None:
    """Build the schema on the isolated engine and seed the demo dataset.

    Seeding here is safe: it writes to the throwaway database, never the dev DB.
    """
    from app.core.database import Base, async_engine
    import app.models  # noqa: F401  ensure every table is registered
    from app.etl.seed_data import refresh_scheduled_demo_matches, seed_database

    async def _run() -> None:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await seed_database()
        await refresh_scheduled_demo_matches()
        await _seed_demo_predictions()
        await _refresh_league_gate()

    asyncio.run(_run())


async def _refresh_league_gate() -> None:
    """Compute the league-gate snapshot so paid surfaces have deterministic data.

    The gate fails closed when no snapshot exists; without this, picks/scanner
    would see zero eligible leagues in a fresh test database.
    """
    from app.core.database import AsyncSessionLocal
    from app.services.league_gate import refresh_and_store_snapshot

    async with AsyncSessionLocal() as session:
        await refresh_and_store_snapshot(session)


async def _seed_demo_predictions() -> None:
    """Give the EPL demo fixtures a current prediction + quote.

    Without this the league gate sees no live coverage and the paid prediction
    branches are never exercised. Values are deterministic and synthetic.
    """
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.math.dixon_coles import calculate_match_distribution
    from app.math.shin import calculate_shin_probabilities
    from app.models import Match, ModelParameter, OddsSnapshot, Prediction

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        model = ModelParameter(
            league_id="EPL",
            model_version="test-seed-v1",
            training_cutoff=now - timedelta(days=2),
            calculated_at=now - timedelta(days=1),
            training_data_ref="test-seed-epl",
            home_advantage=0.2,
            rho=-0.05,
            xi_decay=0.0018,
            team_attack={"arsenal": 1.1, "chelsea": 1.0},
            team_defense={"arsenal": 0.9, "chelsea": 1.0},
        )
        session.add(model)
        await session.flush()

        distribution = calculate_match_distribution(1.6, 1.1, 0.0)
        probs, _z, method = calculate_shin_probabilities([2.40, 3.30, 3.40])

        matches = (
            await session.execute(
                select(Match)
                .where(Match.status == "SCHEDULED", Match.league_id == "EPL")
                .order_by(Match.match_date.asc())
            )
        ).scalars().all()

        as_of = now - timedelta(hours=1)
        for match in matches:
            quote = OddsSnapshot(
                match_id=match.id,
                source_name="the_odds_api",
                bookmaker="pinnacle",
                quote_at=now - timedelta(hours=2),
                recorded_at=now - timedelta(hours=1, minutes=30),
                home_odds=Decimal("2.40"),
                draw_odds=Decimal("3.30"),
                away_odds=Decimal("3.40"),
                dejuice_method=method,
                implied_prob_home=probs[0],
                implied_prob_draw=probs[1],
                implied_prob_away=probs[2],
            )
            session.add(quote)
            await session.flush()
            session.add(
                Prediction(
                    match_id=match.id,
                    model_parameters_id=model.id,
                    odds_snapshot_id=quote.id,
                    as_of=as_of,
                    kickoff_at_prediction=match.match_date,
                    generated_at=as_of,
                    lambda_home=1.6,
                    mu_away=1.1,
                    prob_home_win=distribution["prob_home_win"],
                    prob_draw=distribution["prob_draw"],
                    prob_away_win=distribution["prob_away_win"],
                    score_matrix=distribution["score_matrix"],
                    omitted_mass=distribution["omitted_mass"],
                    top_scores=distribution["top_scores"],
                )
            )
        await session.commit()


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database(request):
    """Create + seed a throwaway database for the whole session, then drop it.

    The dev DB in ``.env`` is never connected to. Sessions that contain no
    database-backed module are left untouched (no Postgres required).
    """
    module_names = {item.path.name for item in request.session.items}
    if not (module_names & _DB_MODULES):
        yield None
        return

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core import database as db_module
    from app.core.config import settings

    dev_db = settings.POSTGRES_DB
    test_db = os.environ.get("TEST_POSTGRES_DB") or f"{dev_db}_test"

    # Deterministic starting point even if a previous run crashed mid-way.
    _drop_and_create(settings, test_db)

    old_engine = db_module.async_engine
    settings.POSTGRES_DB = test_db
    # NullPool: no asyncpg connection is reused across the per-test event loops.
    new_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        future=True,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    db_module.async_engine = new_engine
    # AsyncSessionLocal is a shared object; every module that imported it by
    # value keeps using this same instance, now bound to the isolated engine.
    db_module.AsyncSessionLocal.configure(bind=new_engine)
    _rebind_async_engine_symbol(new_engine)

    _create_schema_and_seed()
    try:
        yield test_db
    finally:
        try:
            asyncio.run(new_engine.dispose())
        except Exception:
            pass
        settings.POSTGRES_DB = dev_db
        db_module.async_engine = old_engine
        db_module.AsyncSessionLocal.configure(bind=old_engine)
        _rebind_async_engine_symbol(old_engine)
        _drop_database(settings, test_db)


@pytest.fixture(autouse=True)
def bypass_rate_limiter(request, monkeypatch):
    """Neutralise IP/user shared rate-limit buckets for most of the suite.

    The whole suite shares one client IP and a live Redis bucket, which is a
    latent flake. Tests that exercise limiting for real opt out with
    ``@pytest.mark.live_rate_limit``; the limiter itself has dedicated coverage
    in ``test_rate_limiter.py``.
    """
    if "live_rate_limit" in request.keywords:
        yield
        return

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.v1.auth.check_rate_limit", _noop)
    monkeypatch.setattr("app.api.v1.payments.check_rate_limit", _noop)
    monkeypatch.setattr("app.api.v1.alpha.check_rate_limit", _noop)
    yield


@pytest.fixture(autouse=True)
async def isolate_trial_and_demo_kickoffs(request):
    """New registrations must be FREE, and demo fixtures must stay in the future.

    The monetization row is restored after the test. Modules that never touch
    the database skip the fixture. All writes land in the isolated test DB.
    """
    module_name = request.node.path.name
    if module_name not in _DB_MODULES:
        yield
        return

    from app.core.database import AsyncSessionLocal
    from app.etl.seed_data import refresh_scheduled_demo_matches
    from app.services.settings_service import (
        DEFAULT_MONETIZATION,
        get_system_setting,
        upsert_system_setting,
    )

    async with AsyncSessionLocal() as db:
        current = await get_system_setting(db, "monetization", DEFAULT_MONETIZATION)
        previous = dict(current) if isinstance(current, dict) else dict(DEFAULT_MONETIZATION)
        updated = {**DEFAULT_MONETIZATION, **previous, "new_user_trial_days": 0}
        await upsert_system_setting(db, "monetization", updated, "test isolation")
    await refresh_scheduled_demo_matches()
    yield
    async with AsyncSessionLocal() as db:
        await upsert_system_setting(
            db,
            "monetization",
            {**DEFAULT_MONETIZATION, **previous},
            "test isolation restore",
        )
    from app.core.database import async_engine
    await async_engine.dispose()
