import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
import httpx
from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Match, MatchSource, OddsSnapshot
from app.etl.resolver import TeamResolver
from app.math.shin import calculate_shin_probabilities

logger = logging.getLogger(__name__)

ODDS_API_SPORT_KEYS = {
    "EPL": "soccer_epl",
    "LA_LIGA": "soccer_spain_la_liga",
    "SERIE_A": "soccer_italy_serie_a",
    "BUNDESLIGA": "soccer_germany_bundesliga",
    "LIGUE_1": "soccer_france_ligue_one",
    "UCL": "soccer_uefa_champs_league",
    "UEL": "soccer_uefa_europa_league",
    "ALLSVENSKAN": "soccer_sweden_allsvenskan",
    "ELITESERIEN": "soccer_norway_eliteserien",
    "SUPERLIGA": "soccer_denmark_superliga",
    "AUSTRIAN_BUNDESLIGA": "soccer_austria_bundesliga",
    "CHAMPIONSHIP": "soccer_efl_champ",
    "EREDIVISIE": "soccer_netherlands_eredivisie",
    "PRIMEIRA_LIGA": "soccer_portugal_primeira_liga",
    "MLS": "soccer_usa_mls",
    "BRASILEIRAO": "soccer_brazil_campeonato",
    "SAUDI_PRO_LEAGUE": "soccer_saudi_arabia_pro_league",
}

THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"
_HTTP_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


@dataclass
class OddsFetchResult:
    ok: bool
    events: List[Dict[str, Any]] = field(default_factory=list)
    status_code: Optional[int] = None


def season_label(kickoff: datetime) -> str:
    year = kickoff.year
    if kickoff.month >= 7:
        return f"{year}-{year + 1}"
    return f"{year - 1}-{year}"


def _safe_error(exc: BaseException) -> str:
    text = str(exc)
    if "apiKey" in text or "api_key" in text:
        return type(exc).__name__
    return text[:300]


class OddsApiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.THE_ODDS_API_KEY

    async def fetch_league_odds(
        self,
        league_id: str = "EPL",
        bookmakers: str = "pinnacle",
        markets: str = "h2h",
    ) -> OddsFetchResult:
        """
        Fetches active h2h odds from The Odds API for any supported league.
        ok=False means the caller must not treat the league as successfully polled.
        """
        if not self.api_key:
            logger.info("THE_ODDS_API_KEY is not configured; skipping external fetch.")
            return OddsFetchResult(ok=False, status_code=None)

        sport_key = ODDS_API_SPORT_KEYS.get(league_id)
        if not sport_key:
            logger.error("No Odds API sport key for league %s", league_id)
            return OddsFetchResult(ok=False)
        url = f"{THE_ODDS_API_BASE}/{sport_key}/odds/"
        params = {
            "apiKey": self.api_key,
            "regions": "eu,uk",
            "bookmakers": bookmakers,
            "markets": markets,
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }

        last_error = "unknown"
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                    resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    remaining = resp.headers.get("x-requests-remaining")
                    logger.info("The Odds API fetched for %s. Requests remaining: %s", league_id, remaining)
                    payload = resp.json()
                    events = payload if isinstance(payload, list) else []
                    return OddsFetchResult(ok=True, events=events, status_code=200)
                if resp.status_code == 401:
                    logger.error("The Odds API authorization failed for %s.", league_id)
                    return OddsFetchResult(ok=False, status_code=401)
                last_error = f"HTTP {resp.status_code}"
                logger.warning("The Odds API error for %s: %s", league_id, last_error)
                if resp.status_code != 429 or attempt == 1:
                    return OddsFetchResult(ok=False, status_code=resp.status_code)
            except Exception as exc:
                last_error = _safe_error(exc)
                logger.error("Failed to fetch odds for %s: %s", league_id, last_error)
                if attempt == 1:
                    return OddsFetchResult(ok=False)
            await asyncio.sleep(1.0)
        return OddsFetchResult(ok=False)

    async def fetch_epl_odds(
        self,
        bookmakers: str = "pinnacle",
        markets: str = "h2h",
    ) -> OddsFetchResult:
        return await self.fetch_league_odds(league_id="EPL", bookmakers=bookmakers, markets=markets)

    async def ingest_odds_event(
        self,
        session: AsyncSession,
        event: Dict[str, Any],
        league_id: str = "EPL",
        league_country: str = "England",
        target_bookmaker: str = "pinnacle",
        bookmaker_priority: Optional[List[str]] = None,
    ) -> Optional[List[OddsSnapshot]]:
        """
        Processes one event from The Odds API into canonical match and odds
        snapshots. Every configured bookmaker that actually quoted the event
        gets its own snapshot row, so cross-book line shopping survives
        downstream freshness selection; priority order only decides the
        attempt order, not exclusivity.

        Returns the staged snapshots (empty list when the event resolved but no
        usable quote survived), or ``None`` when the event cannot be ingested
        (missing fields / unresolved teams). This method **commits** the
        session on success; callers own the session and should roll back on an
        exception raised out of it.
        """
        event_id = event.get("id")
        home_ext = event.get("home_team")
        away_ext = event.get("away_team")
        commence_time_str = event.get("commence_time")

        if not (event_id and home_ext and away_ext and commence_time_str):
            logger.warning("Skipping malformed odds event (missing id/teams/commence_time): keys=%s", sorted(event.keys()))
            return None

        try:
            kickoff = datetime.fromisoformat(str(commence_time_str).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            logger.warning("Skipping odds event %s: bad commence_time %r", event_id, commence_time_str)
            return None
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)

        home_id = await TeamResolver.resolve_team(
            session=session,
            source_name="the_odds_api",
            external_name=home_ext,
            country=league_country,
        )
        if not home_id:
            await TeamResolver.log_unresolved_entity(
                session=session,
                source_name="the_odds_api",
                external_name=home_ext,
                country=league_country,
            )
            logger.warning("Unresolved home team %s in %s; event skipped", home_ext, league_id)
            return None

        away_id = await TeamResolver.resolve_team(
            session=session,
            source_name="the_odds_api",
            external_name=away_ext,
            country=league_country,
        )
        if not away_id:
            await TeamResolver.log_unresolved_entity(
                session=session,
                source_name="the_odds_api",
                external_name=away_ext,
                country=league_country,
            )
            logger.warning("Unresolved away team %s in %s; event skipped", away_ext, league_id)
            return None

        # Check existing match via match_sources
        stmt = select(MatchSource.match_id).where(
            MatchSource.source_name == "the_odds_api",
            MatchSource.external_id == event_id,
        )
        match_id = (await session.execute(stmt)).scalar_one_or_none()

        if not match_id:
            # Match against a scheduled fixture with the same teams. Several rows
            # can match (demo schedules and real fixtures share clubs), so pick
            # deterministically instead of raising MultipleResultsFound.
            stmt_m = select(
                Match,
                exists().where(MatchSource.match_id == Match.id),
            ).where(
                Match.league_id == league_id,
                Match.home_team_id == home_id,
                Match.away_team_id == away_id,
                Match.status == "SCHEDULED",
            )
            candidates = (await session.execute(stmt_m)).all()

            def _rank(row) -> tuple:
                match_obj, has_source = row[0], bool(row[1])
                # Prefer a fixture already bound to a real source, then the one
                # whose kickoff is closest to the quoted start, then lowest id.
                return (
                    0 if has_source else 1,
                    abs((match_obj.match_date - kickoff).total_seconds()),
                    match_obj.id,
                )

            if candidates:
                chosen, has_source = min(candidates, key=_rank)
                match_id = chosen.id
                if not has_source and "_DEMO_" in chosen.id:
                    logger.warning(
                        "Reusing demo fixture %s for real odds event %s (kickoff %s); "
                        "verify the schedule is not rewritten incorrectly",
                        chosen.id,
                        event_id,
                        kickoff.isoformat(),
                    )
                if chosen.match_date != kickoff:
                    chosen.match_date = kickoff
                    chosen.updated_at = datetime.now(timezone.utc)
                    await session.flush()
            else:
                # Create real match with actual kickoff time
                match_id = f"{league_id}_TOA_{event_id[:16]}"
                new_match = Match(
                    id=match_id,
                    league_id=league_id,
                    season=season_label(kickoff),
                    match_date=kickoff,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    status="SCHEDULED",
                )
                session.add(new_match)
                await session.flush()

            # Record match source mapping
            session.add(MatchSource(source_name="the_odds_api", external_id=event_id, match_id=match_id))
            await session.flush()

        # Store one snapshot per configured bookmaker that quoted this event.
        priority = bookmaker_priority or [target_bookmaker]
        by_key: Dict[str, Any] = {}
        for bm in event.get("bookmakers", []):
            key = bm.get("key")
            if key:
                by_key[str(key)] = bm

        snapshots: List[OddsSnapshot] = []
        for key in priority:
            bm = by_key.get(key)
            if bm is None:
                continue
            snap = await self._snapshot_for_bookmaker(
                session=session,
                match_id=match_id,
                bookmaker=bm,
                bookmaker_key=str(key),
                home_ext=home_ext,
                away_ext=away_ext,
            )
            if snap is not None:
                snapshots.append(snap)

        if not snapshots:
            return []

        await session.commit()
        for snap in snapshots:
            await session.refresh(snap)
        return snapshots

    async def _snapshot_for_bookmaker(
        self,
        session: AsyncSession,
        match_id: str,
        bookmaker: Dict[str, Any],
        bookmaker_key: str,
        home_ext: str,
        away_ext: str,
    ) -> Optional[OddsSnapshot]:
        """Parse one bookmaker's h2h quote and stage the snapshot row (no commit)."""
        # Extract h2h market
        h2h_market = None
        for mkt in bookmaker.get("markets", []):
            if mkt.get("key") == "h2h":
                h2h_market = mkt
                break

        if not h2h_market:
            return None

        last_update_str = h2h_market.get("last_update")
        if not last_update_str:
            last_update_str = datetime.now(timezone.utc).isoformat()

        try:
            quote_at = datetime.fromisoformat(str(last_update_str).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            logger.warning(
                "Skipping %s quote for match %s: malformed last_update %r",
                bookmaker_key, match_id, last_update_str,
            )
            return None
        if quote_at.tzinfo is None:
            quote_at = quote_at.replace(tzinfo=timezone.utc)
        recorded_at = datetime.now(timezone.utc)
        if quote_at > recorded_at:
            logger.warning("Clamping quote_at ahead of recorded_at for match %s", match_id)
            quote_at = recorded_at

        # Parse 3 outcomes. A single malformed price skips only that outcome (and
        # therefore this one bookmaker); it must not abort the whole league fetch.
        outcomes = h2h_market.get("outcomes", [])
        if len(outcomes) != 3:
            logger.debug("Skipping %s quote for match %s: %d outcomes", bookmaker_key, match_id, len(outcomes))
            return None

        odds_home, odds_draw, odds_away = None, None, None
        for oc in outcomes:
            name = oc.get("name")
            try:
                price = float(oc.get("price"))
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping malformed price %r from %s for match %s",
                    oc.get("price"), bookmaker_key, match_id,
                )
                continue
            if price <= 1.0:
                logger.debug("Skipping non-positive price %s from %s for match %s", price, bookmaker_key, match_id)
                continue
            if name == home_ext:
                odds_home = Decimal(str(price))
            elif name == away_ext:
                odds_away = Decimal(str(price))
            elif name.lower() == "draw":
                odds_draw = Decimal(str(price))

        if not (odds_home and odds_draw and odds_away):
            return None

        # De-juice via Shin
        try:
            probs, z, method = calculate_shin_probabilities(
                [float(odds_home), float(odds_draw), float(odds_away)]
            )
        except ValueError as e:
            logger.warning("Rejected %s quote due to dejuice error: %s", bookmaker_key, e)
            return None

        # Snapshot uniqueness check: (source_name, bookmaker, match_id, quote_at)
        stmt_snap = select(OddsSnapshot).where(
            OddsSnapshot.source_name == "the_odds_api",
            OddsSnapshot.bookmaker == bookmaker_key,
            OddsSnapshot.match_id == match_id,
            OddsSnapshot.quote_at == quote_at,
        )
        existing_snap = (await session.execute(stmt_snap)).scalar_one_or_none()
        if existing_snap:
            return existing_snap

        snapshot = OddsSnapshot(
            match_id=match_id,
            source_name="the_odds_api",
            bookmaker=bookmaker_key,
            quote_at=quote_at,
            recorded_at=recorded_at,
            home_odds=odds_home,
            draw_odds=odds_draw,
            away_odds=odds_away,
            dejuice_method=method,
            implied_prob_home=probs[0],
            implied_prob_draw=probs[1],
            implied_prob_away=probs[2],
        )
        session.add(snapshot)
        return snapshot

