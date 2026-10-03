import re
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Match, MatchSource, OddsSnapshot, Team, TeamAlias
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


class OddsApiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.THE_ODDS_API_KEY

    async def fetch_league_odds(
        self,
        league_id: str = "EPL",
        bookmakers: str = "pinnacle,unibet,betclic,williamhill",
        markets: str = "h2h",
    ) -> List[Dict[str, Any]]:
        """
        Fetches active h2h odds from The Odds API for any supported league.
        """
        if not self.api_key:
            logger.info("THE_ODDS_API_KEY is not configured; skipping external fetch.")
            return []

        sport_key = ODDS_API_SPORT_KEYS.get(league_id, "soccer_epl")
        url = f"{THE_ODDS_API_BASE}/{sport_key}/odds/"
        params = {
            "apiKey": self.api_key,
            "regions": "eu,uk",
            "markets": markets,
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    remaining = resp.headers.get("x-requests-remaining")
                    logger.info(f"The Odds API fetched for {league_id}. Requests remaining: {remaining}")
                    return resp.json()
                elif resp.status_code == 401:
                    logger.error("The Odds API authorization failed: invalid API key.")
                    return []
                elif resp.status_code == 429:
                    logger.warning("The Odds API rate limit exceeded.")
                    return []
                else:
                    logger.error(f"The Odds API error {resp.status_code}: {resp.text}")
                    return []
            except Exception as e:
                logger.error(f"Failed to fetch from The Odds API for {league_id}: {e}")
                return []

    async def fetch_epl_odds(
        self,
        bookmakers: str = "pinnacle",
        markets: str = "h2h",
    ) -> List[Dict[str, Any]]:
        return await self.fetch_league_odds(league_id="EPL", bookmakers=bookmakers, markets=markets)

    async def ingest_odds_event(
        self,
        session: AsyncSession,
        event: Dict[str, Any],
        league_id: str = "EPL",
        league_country: str = "England",
        target_bookmaker: str = "pinnacle",
    ) -> Optional[OddsSnapshot]:
        """
        Processes one event from The Odds API into canonical match and odds snapshot.
        """
        event_id = event.get("id")
        home_ext = event.get("home_team")
        away_ext = event.get("away_team")
        commence_time_str = event.get("commence_time")

        if not (event_id and home_ext and away_ext and commence_time_str):
            return None

        # Resolve or auto-register home team
        home_id = await TeamResolver.resolve_team(
            session=session,
            source_name="the_odds_api",
            external_name=home_ext,
            country=league_country,
        )
        if not home_id:
            home_slug = re.sub(r'[^a-z0-9]+', '-', home_ext.lower()).strip('-')
            stmt_t = select(Team).where(Team.id == home_slug)
            existing_t = (await session.execute(stmt_t)).scalar_one_or_none()
            if not existing_t:
                session.add(Team(id=home_slug, canonical_name=home_ext, country=league_country))
                await session.flush()
            session.add(TeamAlias(
                source_name="the_odds_api",
                external_name=home_ext,
                country=league_country,
                team_id=home_slug,
            ))
            await session.flush()
            home_id = home_slug

        # Resolve or auto-register away team
        away_id = await TeamResolver.resolve_team(
            session=session,
            source_name="the_odds_api",
            external_name=away_ext,
            country=league_country,
        )
        if not away_id:
            away_slug = re.sub(r'[^a-z0-9]+', '-', away_ext.lower()).strip('-')
            stmt_t = select(Team).where(Team.id == away_slug)
            existing_t = (await session.execute(stmt_t)).scalar_one_or_none()
            if not existing_t:
                session.add(Team(id=away_slug, canonical_name=away_ext, country=league_country))
                await session.flush()
            session.add(TeamAlias(
                source_name="the_odds_api",
                external_name=away_ext,
                country=league_country,
                team_id=away_slug,
            ))
            await session.flush()
            away_id = away_slug

        kickoff = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))

        # Check existing match via match_sources
        stmt = select(MatchSource.match_id).where(
            MatchSource.source_name == "the_odds_api",
            MatchSource.external_id == event_id,
        )
        match_id = (await session.execute(stmt)).scalar_one_or_none()

        if not match_id:
            # Check scheduled match with same teams and league
            stmt_m = select(Match.id).where(
                Match.league_id == league_id,
                Match.home_team_id == home_id,
                Match.away_team_id == away_id,
                Match.status == "SCHEDULED",
            )
            match_id = (await session.execute(stmt_m)).scalar_one_or_none()
            if not match_id:
                # Create real match with actual kickoff time
                match_id = f"{league_id}_TOA_{event_id[:16]}"
                new_match = Match(
                    id=match_id,
                    league_id=league_id,
                    season="2026-2027",
                    match_date=kickoff,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    status="SCHEDULED",
                )
                session.add(new_match)
                await session.flush()
            else:
                # Update match_date to real kickoff
                stmt_up = select(Match).where(Match.id == match_id)
                m_obj = (await session.execute(stmt_up)).scalar_one()
                m_obj.match_date = kickoff
                await session.flush()

            # Record match source mapping
            session.add(MatchSource(source_name="the_odds_api", external_id=event_id, match_id=match_id))
            await session.flush()

        # Find bookmaker: prefer target_bookmaker (e.g. pinnacle), or fallback to first available
        bookmakers = event.get("bookmakers", [])
        selected_bm = None
        for bm in bookmakers:
            if bm.get("key") == target_bookmaker:
                selected_bm = bm
                break
        if not selected_bm and bookmakers:
            # Fallback to first bookmaker with h2h market
            for bm in bookmakers:
                if any(mkt.get("key") == "h2h" for mkt in bm.get("markets", [])):
                    selected_bm = bm
                    break

        if not selected_bm:
            return None

        actual_bookmaker = selected_bm.get("key", target_bookmaker)

        # Extract h2h market
        h2h_market = None
        for mkt in selected_bm.get("markets", []):
            if mkt.get("key") == "h2h":
                h2h_market = mkt
                break

        if not h2h_market:
            return None

        last_update_str = h2h_market.get("last_update")
        if not last_update_str:
            last_update_str = datetime.now(timezone.utc).isoformat()

        quote_at = datetime.fromisoformat(last_update_str.replace("Z", "+00:00"))
        recorded_at = datetime.now(timezone.utc)

        # Parse 3 outcomes
        outcomes = h2h_market.get("outcomes", [])
        if len(outcomes) != 3:
            return None

        odds_home, odds_draw, odds_away = None, None, None
        for oc in outcomes:
            name = oc.get("name")
            price = float(oc.get("price", 0))
            if price <= 1.0:
                return None
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
            logger.warning(f"Rejected quote due to dejuice error: {e}")
            return None

        # Snapshot uniqueness check: (source_name, bookmaker, match_id, quote_at)
        stmt_snap = select(OddsSnapshot).where(
            OddsSnapshot.source_name == "the_odds_api",
            OddsSnapshot.bookmaker == actual_bookmaker,
            OddsSnapshot.match_id == match_id,
            OddsSnapshot.quote_at == quote_at,
        )
        existing_snap = (await session.execute(stmt_snap)).scalar_one_or_none()
        if existing_snap:
            return existing_snap

        snapshot = OddsSnapshot(
            match_id=match_id,
            source_name="the_odds_api",
            bookmaker=actual_bookmaker,
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
        await session.commit()
        await session.refresh(snapshot)
        return snapshot
