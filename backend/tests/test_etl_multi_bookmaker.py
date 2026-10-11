"""Multi-bookmaker live ingest (Betfair Exchange + William Hill alongside Pinnacle).

The Odds API fetch asks for every configured sharp book, and each one that
quoted the event must now land in odds_snapshots instead of only the highest
priority book.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.etl.odds_api import OddsApiClient
from app.models import Match, MatchSource, OddsSnapshot, Team

PRIORITY = ["pinnacle", "betfair_ex_uk", "bet365", "williamhill"]


def _h2h(key: str, home: str, away: str, prices) -> dict:
    return {
        "key": key,
        "markets": [
            {
                "key": "h2h",
                "last_update": prices["updated"],
                "outcomes": [
                    {"name": home, "price": prices["home"]},
                    {"name": "Draw", "price": prices["draw"]},
                    {"name": away, "price": prices["away"]},
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_ingest_stores_every_configured_bookmaker():
    quote_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    async with AsyncSessionLocal() as session:
        # Reuse a proven-resolvable fixture so no team aliases are required.
        row = (
            await session.execute(
                select(Match)
                .join(MatchSource, MatchSource.match_id == Match.id)
                .where(
                    MatchSource.source_name == "the_odds_api",
                    Match.status == "SCHEDULED",
                )
                .order_by(Match.match_date.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            pytest.skip("No live scheduled the_odds_api fixture available right now")

        match = row
        home_team = (
            await session.execute(
                select(Team.canonical_name, Team.country).where(Team.id == match.home_team_id)
            )
        ).one()
        away_name = (
            await session.execute(select(Team.canonical_name).where(Team.id == match.away_team_id))
        ).scalar_one()
        home_name, country = home_team

        event_id = f"mlq_test_{uuid.uuid4().hex}"
        event = {
            "id": event_id,
            "home_team": home_name,
            "away_team": away_name,
            "commence_time": match.match_date.astimezone(timezone.utc).isoformat(),
            "bookmakers": [
                _h2h("williamhill", home_name, away_name, {"updated": quote_time, "home": 2.05, "draw": 3.4, "away": 3.75}),
                _h2h("pinnacle", home_name, away_name, {"updated": quote_time, "home": 1.98, "draw": 3.55, "away": 3.9}),
                _h2h("betfair_ex_uk", home_name, away_name, {"updated": quote_time, "home": 2.02, "draw": 3.45, "away": 3.8}),
                _h2h("boylesports", home_name, away_name, {"updated": quote_time, "home": 2.1, "draw": 3.3, "away": 3.6}),
            ],
        }

        client = OddsApiClient(api_key="ingest_test_key")
        snapshots = await client.ingest_odds_event(
            session=session,
            event=event,
            league_id=match.league_id,
            league_country=country,
            bookmaker_priority=PRIORITY,
        )

        stored = {snap.bookmaker for snap in snapshots}
        assert stored == {"pinnacle", "betfair_ex_uk", "williamhill"}, "unconfigured books must not be stored"
        for snap in snapshots:
            assert snap.match_id == match.id
            assert snap.implied_prob_home is not None

        # Same event again: dedup on (bookmaker, match, quote_at), no duplicate rows.
        again = await client.ingest_odds_event(
            session=session,
            event=event,
            league_id=match.league_id,
            league_country=country,
            bookmaker_priority=PRIORITY,
        )
        assert {s.id for s in again} == {s.id for s in snapshots}

        count = (
            await session.execute(
                select(OddsSnapshot.id).where(
                    OddsSnapshot.match_id == match.id,
                    OddsSnapshot.bookmaker.in_(["pinnacle", "betfair_ex_uk", "williamhill"]),
                    OddsSnapshot.quote_at == datetime.fromisoformat(quote_time),
                )
            )
        ).all()
        assert len(count) == 3

        # Leave the fixture as found.
        await session.execute(
            delete(OddsSnapshot).where(
                OddsSnapshot.match_id == match.id,
                OddsSnapshot.quote_at == datetime.fromisoformat(quote_time),
            )
        )
        await session.execute(delete(MatchSource).where(MatchSource.external_id == event_id))
        await session.commit()
