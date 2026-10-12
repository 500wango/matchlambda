import asyncio
import math
import hashlib
import logging
import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.database import AsyncSessionLocal, async_engine
from app.core.celery import celery_app
from app.models import League, Team, Match, OddsSnapshot, ModelParameter, Prediction

logger = logging.getLogger(__name__)
from app.math.dixon_coles import (
    InsufficientTrainingDataError,
    fit_dixon_coles,
    calculate_match_distribution,
)
from app.math.freshness import latest_eligible_quote
from app.services.settings_service import (
    load_provider_config,
    load_quant_config,
    get_system_setting,
    upsert_system_setting,
    DEFAULT_DATA_PROVIDER,
)


def _training_content_fingerprint(league_id: str, matches: List[Match]) -> str:
    """Deterministic fingerprint of the training set — never the wall clock.

    Two runs over the same completed fixtures must produce the same ref so the
    unique constraint (and the pre-insert lookup) can reuse the existing row
    instead of appending a new one every hour.
    """
    match_count = len(matches)
    latest_result_at = max((m.result_available_at for m in matches), default=None)
    latest_match_id = max((m.id for m in matches), default="")
    source = "|".join([
        league_id,
        str(match_count),
        latest_result_at.isoformat() if latest_result_at else "none",
        latest_match_id,
    ])
    content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"dataset://{league_id}/historical-v1.3#{content_hash}"


async def run_model_training_async(league_id: str = "EPL") -> ModelParameter:
    """
    Fits Dixon-Coles model on all completed historical matches up to cutoff.
    Persists ModelParameter record.
    """
    cutoff = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        # Get all completed matches for league
        stmt = (
            select(Match)
            .where(
                Match.league_id == league_id,
                Match.status == "FINISHED",
                Match.home_score.isnot(None),
                Match.away_score.isnot(None),
                Match.result_available_at <= cutoff,
            )
            .order_by(Match.match_date.asc())
        )
        matches = (await session.execute(stmt)).scalars().all()

        # Extract all participating teams for this league
        team_set = set()
        for m in matches:
            team_set.add(m.home_team_id)
            team_set.add(m.away_team_id)
        all_teams = sorted(list(team_set))

        match_tuples = [
            (
                m.home_team_id, m.away_team_id, m.home_score, m.away_score,
                m.match_date, m.result_available_at,
            )
            for m in matches
        ]

        quant = await load_quant_config(session)
        fit_result = fit_dixon_coles(
            matches=match_tuples,
            team_list=list(all_teams),
            training_cutoff=cutoff,
            xi=float(quant["dixon_coles_decay_xi"]),
            min_matches=int(quant["min_training_matches"]),
        )

        # Deterministic content fingerprint (no wall clock) so the same dataset
        # reuses one row instead of appending a new one every run.
        data_ref = _training_content_fingerprint(league_id, list(matches))

        existing_stmt = (
            select(ModelParameter)
            .where(
                ModelParameter.league_id == league_id,
                ModelParameter.training_data_ref == data_ref,
            )
            .order_by(ModelParameter.calculated_at.desc())
        )
        existing = (await session.execute(existing_stmt)).scalars().first()
        if existing is not None:
            return existing

        model_param = ModelParameter(
            league_id=league_id,
            model_version="dc-v1.3.0",
            training_cutoff=cutoff,
            calculated_at=cutoff,
            training_data_ref=data_ref,
            home_advantage=fit_result["home_advantage"],
            rho=fit_result["rho"],
            xi_decay=fit_result["xi_decay"],
            team_attack=fit_result["team_attack"],
            team_defense=fit_result["team_defense"],
        )
        session.add(model_param)
        try:
            await session.commit()
        except IntegrityError:
            # A concurrent worker inserted the same (league_id, training_data_ref)
            # between our lookup and insert: reuse its row.
            await session.rollback()
            existing = (await session.execute(existing_stmt)).scalars().first()
            if existing is None:
                raise
            return existing
        await session.refresh(model_param)
        return model_param


async def generate_snapshots_and_predictions_async(match_id: str, model_param_id: Optional[str] = None):
    """
    Collects/creates odds snapshot and generates prediction snapshot for a fixture.
    """
    async with AsyncSessionLocal() as session:
        match = await session.get(Match, match_id)
        if not match or match.status != "SCHEDULED":
            return

        now = datetime.now(timezone.utc)
        as_of = now
        if match.match_date <= as_of:
            return

        # Get latest model parameters
        if model_param_id:
            model_param = await session.get(ModelParameter, model_param_id)
        else:
            stmt = (
                select(ModelParameter)
                .where(ModelParameter.league_id == match.league_id)
                .order_by(ModelParameter.calculated_at.desc())
            )
            model_param = (await session.execute(stmt)).scalars().first()

        if not model_param:
            return

        quote_stmt = (
            select(OddsSnapshot)
            .where(
                OddsSnapshot.match_id == match_id,
                OddsSnapshot.quote_at >= as_of - timedelta(hours=13),
                OddsSnapshot.quote_at <= as_of,
                OddsSnapshot.recorded_at <= as_of,
            )
            .order_by(OddsSnapshot.quote_at.desc())
        )
        quote_rows = (await session.execute(quote_stmt)).scalars().all()
        odds_snap = latest_eligible_quote(quote_rows, as_of)

        attack = model_param.team_attack or {}
        defense = model_param.team_defense or {}
        if match.home_team_id not in attack or match.away_team_id not in attack:
            logger.info("Skipping prediction for %s: a team is outside the fitted model", match_id)
            return
        if match.home_team_id not in defense or match.away_team_id not in defense:
            logger.info("Skipping prediction for %s: a team has no defensive rating", match_id)
            return

        home_att = attack[match.home_team_id]
        home_def = defense[match.home_team_id]
        away_att = attack[match.away_team_id]
        away_def = defense[match.away_team_id]
        gamma = model_param.home_advantage
        rho = model_param.rho

        lam_home = math.exp(home_att - away_def + gamma)
        mu_away = math.exp(away_att - home_def)

        # 3. Calculate match distribution
        try:
            dist = calculate_match_distribution(lam_home, mu_away, rho)
        except ValueError as exc:
            logger.info("Prediction unavailable for match %s: %s", match_id, exc)
            return

        # 4. Create prediction record
        pred = Prediction(
            match_id=match_id,
            model_parameters_id=model_param.id,
            odds_snapshot_id=odds_snap.id if odds_snap else None,
            as_of=as_of,
            kickoff_at_prediction=match.match_date,
            generated_at=now,
            lambda_home=dist["lambda_home"],
            mu_away=dist["mu_away"],
            prob_home_win=dist["prob_home_win"],
            prob_draw=dist["prob_draw"],
            prob_away_win=dist["prob_away_win"],
            score_matrix=dist["score_matrix"],
            omitted_mass=dist["omitted_mass"],
            top_scores=dist["top_scores"],
        )
        session.add(pred)
        await session.commit()


# Process-local fallback locks, used only when Redis is unreachable. They cannot
# dedupe across worker processes but keep a single worker from duplicating work.
_LOCAL_LOCKS: Dict[str, threading.Lock] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()

# Lua compare-and-delete: only the owner of the token may drop the key, so a
# task that overran its TTL can never delete a lock another worker now holds.
_UNLOCK_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) else return 0 end"
)


def _training_lock_ttl() -> int:
    """Lock TTL is comfortably larger than the task time limit (2x) so a lock
    can never expire while the task it guards is still allowed to run."""
    try:
        limit = int(celery_app.conf.task_time_limit or 0)
    except Exception:
        limit = 0
    if limit <= 0:
        limit = 30 * 60
    return 2 * limit


def _acquire_local_lock(name: str) -> bool:
    with _LOCAL_LOCKS_GUARD:
        lock = _LOCAL_LOCKS.setdefault(name, threading.Lock())
    return lock.acquire(blocking=False)


def _release_local_lock(name: str) -> None:
    with _LOCAL_LOCKS_GUARD:
        lock = _LOCAL_LOCKS.get(name)
    if lock is not None and lock.locked():
        try:
            lock.release()
        except RuntimeError:
            pass


async def _acquire_training_lock(name: str, ttl: int) -> Optional[str]:
    """Return an unlock token when we hold the lock, else None.

    Fail-safe: if Redis is unreachable we log an error and degrade to a
    process-local lock instead of silently proceeding unlocked.
    """
    token = uuid.uuid4().hex
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            acquired = await client.set(name, token, nx=True, ex=ttl)
            if acquired:
                return f"redis:{token}"
            return None
        finally:
            await client.aclose()
    except Exception as exc:
        logger.error(
            "Redis training lock unavailable (%s); degrading to an in-process lock for %s",
            type(exc).__name__, name,
        )
        if _acquire_local_lock(name):
            return "local"
        return None


async def _release_training_lock(name: str, token: Optional[str]) -> None:
    if not token:
        return
    if token == "local":
        _release_local_lock(name)
        return
    redis_token = token.split(":", 1)[1] if ":" in token else token
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await client.eval(_UNLOCK_LUA, 1, name, redis_token)
        finally:
            await client.aclose()
    except Exception as exc:
        logger.warning(
            "Could not release training lock %s (%s); it will expire by TTL",
            name, type(exc).__name__,
        )


async def train_league(league_id: str, refresh_predictions: bool = True) -> Optional[str]:
    """Fit one league under a Redis lock. Returns the parameter id, or None if the lock is held."""
    lock_name = f"mlq:train:{league_id}"
    token = await _acquire_training_lock(lock_name, _training_lock_ttl())
    if token is None:
        logger.info("Training already running for %s", league_id)
        return None
    try:
        model_param = await run_model_training_async(league_id)
        if refresh_predictions:
            async with AsyncSessionLocal() as session:
                stmt = select(Match.id).where(Match.league_id == league_id, Match.status == "SCHEDULED")
                fixture_ids = (await session.execute(stmt)).scalars().all()
            for fid in fixture_ids:
                try:
                    await generate_snapshots_and_predictions_async(fid, str(model_param.id))
                except Exception:
                    logger.exception("Prediction refresh failed for %s", fid)
        return str(model_param.id)
    finally:
        await _release_training_lock(lock_name, token)


def _run_async(coro):
    """Celery workers have no running loop. Dispose pooled connections around each new loop."""
    async def _wrapped():
        await async_engine.dispose()
        try:
            return await coro
        finally:
            await async_engine.dispose()

    return asyncio.run(_wrapped())


@celery_app.task(name="app.tasks.pipeline.hourly_pipeline_task")
def hourly_pipeline_task():
    _run_async(run_hourly_pipeline())


@celery_app.task(name="app.tasks.pipeline.train_league_task")
def train_league_task(league_id: str, refresh_predictions: bool = True):
    return _run_async(train_league(league_id, refresh_predictions))


async def run_hourly_pipeline():
    async with AsyncSessionLocal() as session:
        stmt = select(League).where(League.active == True)
        leagues = (await session.execute(stmt)).scalars().all()
        try:
            provider = await load_provider_config(session)
        except Exception as exc:
            # A single malformed config row must not abort the whole tick.
            logger.error(
                "Provider config load failed (%s); using defaults for this tick", type(exc).__name__
            )
            provider = dict(DEFAULT_DATA_PROVIDER)
        if not isinstance(provider, dict):
            logger.error("Provider config is not a JSON object; using defaults for this tick")
            provider = dict(DEFAULT_DATA_PROVIDER)
        try:
            ops_state = await get_system_setting(session, "ops_state", {})
        except Exception as exc:
            logger.error("ops_state load failed (%s); resetting poll clock", type(exc).__name__)
            ops_state = {}
        if not isinstance(ops_state, dict):
            logger.error("ops_state is not a JSON object; resetting poll clock")
            ops_state = {}

    # Beat stays hourly because the schedule is static. The saved interval decides whether this tick fetches.
    live_enabled = bool(provider.get("live_monitoring_enabled", True))
    api_key = provider.get("the_odds_api_key") or settings.THE_ODDS_API_KEY
    bookmakers = [str(name) for name in (provider.get("sharp_bookmakers") or ["pinnacle"]) if str(name).strip()]
    if not bookmakers:
        bookmakers = ["pinnacle"]
    interval_hours = max(1, int(provider.get("polling_interval_hours") or 1))
    last_poll_raw = ops_state.get("last_odds_poll_at")
    poll_due = True
    if last_poll_raw:
        try:
            last_poll = datetime.fromisoformat(str(last_poll_raw))
            if last_poll.tzinfo is None:
                last_poll = last_poll.replace(tzinfo=timezone.utc)
            poll_due = datetime.now(timezone.utc) - last_poll >= timedelta(hours=interval_hours)
        except ValueError:
            poll_due = True

    if live_enabled and api_key and poll_due:
        from app.etl.odds_api import OddsApiClient
        client = OddsApiClient(api_key=api_key)
        books_param = ",".join(bookmakers)
        # A hard failure is an API-level failure for a whole league (network,
        # auth, HTTP error). Per-event problems (one bad quote, one unresolved
        # fixture) are logged and skipped so a single bad event cannot keep the
        # poll clock from advancing and re-burning the API quota every hour.
        hard_failures = 0
        for league in leagues:
            try:
                fetched = await client.fetch_league_odds(league_id=league.id, bookmakers=books_param)
            except Exception:
                hard_failures += 1
                logger.exception("Live fetch failed for %s", league.id)
                continue
            if not fetched.ok:
                hard_failures += 1
                logger.warning("Odds fetch unsuccessful for %s (status=%s)", league.id, fetched.status_code)
                continue
            if not fetched.events:
                continue
            async with AsyncSessionLocal() as session:
                for ev in fetched.events:
                    try:
                        await client.ingest_odds_event(
                            session=session,
                            event=ev,
                            league_id=league.id,
                            league_country=league.country,
                            target_bookmaker=bookmakers[0],
                            bookmaker_priority=bookmakers,
                        )
                    except Exception:
                        await session.rollback()
                        logger.warning(
                            "Skipping odds event %s in %s after ingest error",
                            ev.get("id"), league.id, exc_info=True,
                        )
        if hard_failures == 0:
            async with AsyncSessionLocal() as session:
                ops_state["last_odds_poll_at"] = datetime.now(timezone.utc).isoformat()
                await upsert_system_setting(session, "ops_state", ops_state, "Odds poll clock")
        else:
            logger.warning(
                "Odds poll incomplete (%d/%d leagues failed at the API level); last_odds_poll_at was not advanced",
                hard_failures, len(leagues),
            )

    for league in leagues:
        try:
            await train_league(league.id, refresh_predictions=True)
        except InsufficientTrainingDataError as exc:
            # Expected for leagues that are newly activated or still thin on
            # history. Logged as a warning without a traceback so it does not
            # drown the real failures in noise every hour.
            logger.warning("Skipping training for %s: %s", league.id, exc)
        except Exception:
            logger.exception("Pipeline training failed for %s", league.id)

    try:
        from app.services.notifier import dispatch_value_alerts
        await dispatch_value_alerts()
    except Exception:
        logger.exception("Notification dispatch failed")


async def refresh_league_eligibility() -> Dict[str, Any]:
    """Recompute the PRD §2.1 league gate snapshot and persist it for surfaces."""
    from app.services.league_gate import refresh_and_store_snapshot

    async with AsyncSessionLocal() as session:
        snapshot = await refresh_and_store_snapshot(session)
    eligible = sorted(lid for lid, info in snapshot["leagues"].items() if info.get("eligible"))
    logger.info("League gate refreshed: eligible=%s", eligible)
    return {"computed_at": snapshot["computed_at"], "eligible": eligible}


@celery_app.task(name="app.tasks.pipeline.refresh_league_eligibility_task")
def refresh_league_eligibility_task():
    return _run_async(refresh_league_eligibility())
