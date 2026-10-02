import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Match, MatchSource, OddsSnapshot
from app.etl.resolver import TeamResolver
from app.math.shin import calculate_shin_probabilities

logger = logging.getLogger(__name__)

THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/soccer_epl"


class OddsApiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.THE_ODDS_API_KEY

    async def fetch_epl_odds(
        self,
        bookmakers: str = "pinnacle",
        markets: str = "h2h",
    ) -> List[Dict[str, Any]]:
        """
        Fetches active EPL h2h odds from The Odds API.
        Adheres strictly to docs/06_DATA_PIPELINE_ETL.md.
        """
        if not self.api_key:
            logger.info("THE_ODDS_API_KEY is not configured; skipping external fetch.")
            return []

        url = f"{THE_ODDS_API_BASE}/odds/"
        params = {
            "apiKey": self.api_key,
            "regions": "eu,uk",
            "markets": markets,
            "bookmakers": bookmakers,
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    remaining = resp.headers.get("x-requests-remaining")
                    logger.info(f"The Odds API fetched successfully. Requests remaining: {remaining}")
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
            except httpx.RequestError as e:
                logger.error(f"Network error querying The Odds API: {e}")
                return []

    async def ingest_odds_event(
        self,
        session: AsyncSession,
        event: Dict[str, Any],
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

        # Resolve team identities using confirmed resolver
        home_id = await TeamResolver.resolve_team(
            session=session,
            source_name="the_odds_api",
            external_name=home_ext,
            country="England",
        )
        away_id = await TeamResolver.resolve_team(
            session=session,
            source_name="the_odds_api",
            external_name=away_ext,
            country="England",
        )

        if not home_id or not away_id:
            # Unmapped team: record operator review notice, do not auto-create
            logger.warning(
                f"Unresolved entity: home='{home_ext}' (id={home_id}), away='{away_ext}' (id={away_id})"
            )
            return None

        kickoff = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))

        # Check existing match via match_sources
        stmt = select(MatchSource.match_id).where(
            MatchSource.source_name == "the_odds_api",
            MatchSource.external_id == event_id,
        )
        match_id = (await session.execute(stmt)).scalar_one_or_none()

        if not match_id:
            # Find scheduled match with same teams
            stmt_m = select(Match.id).where(
                Match.league_id == "EPL",
                Match.home_team_id == home_id,
                Match.away_team_id == away_id,
                Match.status == "SCHEDULED",
            )
            match_id = (await session.execute(stmt_m)).scalar_one_or_none()
            if not match_id:
                # Create match
                match_id = f"EPL_TOA_{event_id[:16]}"
                new_match = Match(
                    id=match_id,
                    league_id="EPL",
                    season="2024-2025",
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

        # Find requested bookmaker's complete 1X2 quote
        bookmakers = event.get("bookmakers", [])
        selected_bm = None
        for bm in bookmakers:
            if bm.get("key") == target_bookmaker:
                selected_bm = bm
                break

        if not selected_bm:
            return None

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
            return None

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
            OddsSnapshot.bookmaker == target_bookmaker,
            OddsSnapshot.match_id == match_id,
            OddsSnapshot.quote_at == quote_at,
        )
        existing_snap = (await session.execute(stmt_snap)).scalar_one_or_none()
        if existing_snap:
            return existing_snap

        snapshot = OddsSnapshot(
            match_id=match_id,
            source_name="the_odds_api",
            bookmaker=target_bookmaker,
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
