import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import League, Team, TeamAlias, Match, OddsSnapshot, ModelParameter, Prediction
from app.math.dixon_coles import calculate_match_distribution
from app.math.shin import calculate_shin_probabilities

EPL_TEAMS = [
    ("arsenal", "Arsenal", "England"),
    ("aston-villa", "Aston Villa", "England"),
    ("bournemouth", "Bournemouth", "England"),
    ("brentford", "Brentford", "England"),
    ("brighton", "Brighton & Hove Albion", "England"),
    ("chelsea", "Chelsea", "England"),
    ("crystal-palace", "Crystal Palace", "England"),
    ("everton", "Everton", "England"),
    ("fulham", "Fulham", "England"),
    ("ipswich", "Ipswich Town", "England"),
    ("leicester", "Leicester City", "England"),
    ("liverpool", "Liverpool", "England"),
    ("manchester-city", "Manchester City", "England"),
    ("manchester-united", "Manchester United", "England"),
    ("newcastle", "Newcastle United", "England"),
    ("nottingham-forest", "Nottingham Forest", "England"),
    ("southampton", "Southampton", "England"),
    ("tottenham", "Tottenham Hotspur", "England"),
    ("west-ham", "West Ham United", "England"),
    ("wolves", "Wolverhampton Wanderers", "England"),
]

# Confirmed aliases for external sources
CONFIRMED_ALIASES = [
    # The Odds API aliases
    ("the_odds_api", None, "Arsenal", "England", "arsenal"),
    ("the_odds_api", None, "Aston Villa", "England", "aston-villa"),
    ("the_odds_api", None, "Bournemouth", "England", "bournemouth"),
    ("the_odds_api", None, "Brentford", "England", "brentford"),
    ("the_odds_api", None, "Brighton and Hove Albion", "England", "brighton"),
    ("the_odds_api", None, "Chelsea", "England", "chelsea"),
    ("the_odds_api", None, "Crystal Palace", "England", "crystal-palace"),
    ("the_odds_api", None, "Everton", "England", "everton"),
    ("the_odds_api", None, "Fulham", "England", "fulham"),
    ("the_odds_api", None, "Ipswich", "England", "ipswich"),
    ("the_odds_api", None, "Leicester", "England", "leicester"),
    ("the_odds_api", None, "Liverpool", "England", "liverpool"),
    ("the_odds_api", None, "Manchester City", "England", "manchester-city"),
    ("the_odds_api", None, "Manchester United", "England", "manchester-united"),
    ("the_odds_api", None, "Newcastle United", "England", "newcastle"),
    ("the_odds_api", None, "Nottingham Forest", "England", "nottingham-forest"),
    ("the_odds_api", None, "Southampton", "England", "southampton"),
    ("the_odds_api", None, "Tottenham Hotspur", "England", "tottenham"),
    ("the_odds_api", None, "West Ham United", "England", "west-ham"),
    ("the_odds_api", None, "Wolverhampton Wanderers", "England", "wolves"),
    # Football data / Common short aliases
    ("football_data", None, "Man City", "England", "manchester-city"),
    ("football_data", None, "Man United", "England", "manchester-united"),
    ("football_data", None, "Spurs", "England", "tottenham"),
    ("football_data", None, "Wolves", "England", "wolves"),
    ("football_data", None, "Brighton", "England", "brighton"),
    ("football_data", None, "West Ham", "England", "west-ham"),
    ("football_data", None, "Newcastle", "England", "newcastle"),
    ("football_data", None, "Nott'm Forest", "England", "nottingham-forest"),
    ("football_data", None, "Leicester City", "England", "leicester"),
    ("football_data", None, "Ipswich Town", "England", "ipswich"),
]

# Sample realistic EPL historical matches (2024-2025 season sample for training)
HISTORICAL_MATCHES = [
    ("EPL_2425_001", "2024-08-16T19:00:00Z", "manchester-united", "fulham", 1, 0, "2024-08-16T21:00:00Z"),
    ("EPL_2425_002", "2024-08-17T11:30:00Z", "ipswich", "liverpool", 0, 2, "2024-08-17T13:30:00Z"),
    ("EPL_2425_003", "2024-08-17T14:00:00Z", "arsenal", "wolves", 2, 0, "2024-08-17T16:00:00Z"),
    ("EPL_2425_004", "2024-08-17T14:00:00Z", "everton", "brighton", 0, 3, "2024-08-17T16:00:00Z"),
    ("EPL_2425_005", "2024-08-17T14:00:00Z", "newcastle", "southampton", 1, 0, "2024-08-17T16:00:00Z"),
    ("EPL_2425_006", "2024-08-17T14:00:00Z", "nottingham-forest", "bournemouth", 1, 1, "2024-08-17T16:00:00Z"),
    ("EPL_2425_007", "2024-08-17T16:30:00Z", "west-ham", "aston-villa", 1, 2, "2024-08-17T18:30:00Z"),
    ("EPL_2425_008", "2024-08-18T13:00:00Z", "brentford", "crystal-palace", 2, 1, "2024-08-18T15:00:00Z"),
    ("EPL_2425_009", "2024-08-18T15:30:00Z", "chelsea", "manchester-city", 0, 2, "2024-08-18T17:30:00Z"),
    ("EPL_2425_010", "2024-08-19T19:00:00Z", "leicester", "tottenham", 1, 1, "2024-08-19T21:00:00Z"),
    ("EPL_2425_011", "2024-08-24T11:30:00Z", "brighton", "manchester-united", 2, 1, "2024-08-24T13:30:00Z"),
    ("EPL_2425_012", "2024-08-24T14:00:00Z", "crystal-palace", "west-ham", 0, 2, "2024-08-24T16:00:00Z"),
    ("EPL_2425_013", "2024-08-24T14:00:00Z", "fulham", "leicester", 2, 1, "2024-08-24T16:00:00Z"),
    ("EPL_2425_014", "2024-08-24T14:00:00Z", "manchester-city", "ipswich", 4, 1, "2024-08-24T16:00:00Z"),
    ("EPL_2425_015", "2024-08-24T14:00:00Z", "southampton", "nottingham-forest", 0, 1, "2024-08-24T16:00:00Z"),
    ("EPL_2425_016", "2024-08-24T14:00:00Z", "tottenham", "everton", 4, 0, "2024-08-24T16:00:00Z"),
    ("EPL_2425_017", "2024-08-24T16:30:00Z", "aston-villa", "arsenal", 0, 2, "2024-08-24T18:30:00Z"),
    ("EPL_2425_018", "2024-08-25T13:00:00Z", "bournemouth", "newcastle", 1, 1, "2024-08-25T15:00:00Z"),
    ("EPL_2425_019", "2024-08-25T13:00:00Z", "wolves", "chelsea", 2, 6, "2024-08-25T15:00:00Z"),
    ("EPL_2425_020", "2024-08-25T15:30:00Z", "liverpool", "brentford", 2, 0, "2024-08-25T17:30:00Z"),
    ("EPL_2425_021", "2024-08-31T11:30:00Z", "arsenal", "brighton", 1, 1, "2024-08-31T13:30:00Z"),
    ("EPL_2425_022", "2024-08-31T14:00:00Z", "brentford", "southampton", 3, 1, "2024-08-31T16:00:00Z"),
    ("EPL_2425_023", "2024-08-31T14:00:00Z", "everton", "bournemouth", 2, 3, "2024-08-31T16:00:00Z"),
    ("EPL_2425_024", "2024-08-31T14:00:00Z", "ipswich", "fulham", 1, 1, "2024-08-31T16:00:00Z"),
    ("EPL_2425_025", "2024-08-31T14:00:00Z", "leicester", "aston-villa", 1, 2, "2024-08-31T16:00:00Z"),
    ("EPL_2425_026", "2024-08-31T14:00:00Z", "nottingham-forest", "wolves", 1, 1, "2024-08-31T16:00:00Z"),
    ("EPL_2425_027", "2024-08-31T16:30:00Z", "west-ham", "manchester-city", 1, 3, "2024-08-31T18:30:00Z"),
    ("EPL_2425_028", "2024-09-01T12:30:00Z", "chelsea", "crystal-palace", 1, 1, "2024-09-01T14:30:00Z"),
    ("EPL_2425_029", "2024-09-01T12:30:00Z", "newcastle", "tottenham", 2, 1, "2024-09-01T14:30:00Z"),
    ("EPL_2425_030", "2024-09-01T15:00:00Z", "manchester-united", "liverpool", 0, 3, "2024-09-01T17:00:00Z"),
    ("EPL_2425_031", "2024-09-14T11:30:00Z", "southampton", "manchester-united", 0, 3, "2024-09-14T13:30:00Z"),
    ("EPL_2425_032", "2024-09-14T14:00:00Z", "brighton", "ipswich", 0, 0, "2024-09-14T16:00:00Z"),
    ("EPL_2425_033", "2024-09-14T14:00:00Z", "crystal-palace", "leicester", 2, 2, "2024-09-14T16:00:00Z"),
    ("EPL_2425_034", "2024-09-14T14:00:00Z", "fulham", "west-ham", 1, 1, "2024-09-14T16:00:00Z"),
    ("EPL_2425_035", "2024-09-14T14:00:00Z", "liverpool", "nottingham-forest", 0, 1, "2024-09-14T16:00:00Z"),
    ("EPL_2425_036", "2024-09-14T14:00:00Z", "manchester-city", "brentford", 2, 1, "2024-09-14T16:00:00Z"),
    ("EPL_2425_037", "2024-09-14T16:30:00Z", "aston-villa", "everton", 3, 2, "2024-09-14T18:30:00Z"),
    ("EPL_2425_038", "2024-09-14T19:00:00Z", "bournemouth", "chelsea", 0, 1, "2024-09-14T21:00:00Z"),
    ("EPL_2425_039", "2024-09-15T13:00:00Z", "tottenham", "arsenal", 0, 1, "2024-09-15T15:00:00Z"),
    ("EPL_2425_040", "2024-09-15T15:30:00Z", "wolves", "newcastle", 1, 2, "2024-09-15T17:30:00Z"),
]


async def seed_database():
    async with AsyncSessionLocal() as session:
        # 1. League
        stmt = select(League).where(League.id == "EPL")
        league = (await session.execute(stmt)).scalar_one_or_none()
        if not league:
            league = League(id="EPL", name="Premier League", country="England", active=True)
            session.add(league)

        # 2. Teams
        for team_id, name, country in EPL_TEAMS:
            stmt = select(Team).where(Team.id == team_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                session.add(Team(id=team_id, canonical_name=name, country=country))

        await session.flush()

        # 3. Aliases
        for source_name, ext_id, ext_name, country, team_id in CONFIRMED_ALIASES:
            if ext_id:
                stmt = select(TeamAlias).where(
                    TeamAlias.source_name == source_name,
                    TeamAlias.external_id == ext_id,
                )
            else:
                stmt = select(TeamAlias).where(
                    TeamAlias.source_name == source_name,
                    TeamAlias.country == country,
                    TeamAlias.external_name == ext_name,
                    TeamAlias.external_id.is_(None),
                )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                session.add(TeamAlias(
                    source_name=source_name,
                    external_id=ext_id,
                    external_name=ext_name,
                    country=country,
                    team_id=team_id,
                ))

        await session.flush()

        # 4. Historical Finished Matches
        for m_id, m_date_str, h_team, a_team, h_score, a_score, res_avail_str in HISTORICAL_MATCHES:
            stmt = select(Match).where(Match.id == m_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                m_date = datetime.fromisoformat(m_date_str.replace("Z", "+00:00"))
                res_avail = datetime.fromisoformat(res_avail_str.replace("Z", "+00:00"))
                session.add(Match(
                    id=m_id,
                    league_id="EPL",
                    season="2024-2025",
                    match_date=m_date,
                    home_team_id=h_team,
                    away_team_id=a_team,
                    status="FINISHED",
                    home_score=h_score,
                    away_score=a_score,
                    result_available_at=res_avail,
                ))

        # 5. Scheduled Matches (for immediate demonstration & testing)
        now = datetime.now(timezone.utc)
        scheduled_fixtures = [
            ("EPL_DEMO_001", now + timedelta(days=1), "arsenal", "chelsea"),
            ("EPL_DEMO_002", now + timedelta(days=2), "manchester-city", "liverpool"),
            ("EPL_DEMO_003", now + timedelta(days=2, hours=3), "tottenham", "manchester-united"),
            ("EPL_DEMO_004", now + timedelta(days=3), "aston-villa", "newcastle"),
            ("EPL_DEMO_005", now + timedelta(days=4), "everton", "wolves"),
        ]

        for m_id, m_date, h_team, a_team in scheduled_fixtures:
            stmt = select(Match).where(Match.id == m_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                session.add(Match(
                    id=m_id,
                    league_id="EPL",
                    season="2024-2025",
                    match_date=m_date,
                    home_team_id=h_team,
                    away_team_id=a_team,
                    status="SCHEDULED",
                ))

        await session.flush()

        # Deterministic local data keeps the development UI useful. The scheduled
        # pipeline replaces these records with provider-backed snapshots.
        model = (await session.execute(
            select(ModelParameter).where(ModelParameter.model_version == "dc-demo-1")
        )).scalar_one_or_none()
        if not model:
            model = ModelParameter(
                league_id="EPL",
                model_version="dc-demo-1",
                training_cutoff=now - timedelta(days=1),
                calculated_at=now - timedelta(hours=1),
                training_data_ref="dataset://EPL/demo-seed-v1",
                home_advantage=0.25,
                rho=0.0,
                xi_decay=0.0018,
                team_attack={team_id: 0.0 for team_id, _, _ in EPL_TEAMS},
                team_defense={team_id: 0.0 for team_id, _, _ in EPL_TEAMS},
            )
            session.add(model)
            await session.flush()

        for m_id, m_date, _, _ in scheduled_fixtures:
            existing = (await session.execute(
                select(Prediction).where(Prediction.match_id == m_id)
            )).scalar_one_or_none()
            if existing:
                continue
            as_of = m_date - timedelta(hours=2)
            odds_h, odds_d, odds_a = 1.90, 3.75, 4.50
            market_probs, _, method = calculate_shin_probabilities([odds_h, odds_d, odds_a])
            odds = OddsSnapshot(
                match_id=m_id, source_name="demo", bookmaker="DEMO_BOOK",
                quote_at=as_of - timedelta(minutes=1), recorded_at=as_of,
                home_odds=Decimal(str(odds_h)), draw_odds=Decimal(str(odds_d)),
                away_odds=Decimal(str(odds_a)), dejuice_method=method,
                implied_prob_home=market_probs[0], implied_prob_draw=market_probs[1],
                implied_prob_away=market_probs[2],
            )
            session.add(odds)
            await session.flush()
            dist = calculate_match_distribution(1.78, 0.92, 0.0)
            session.add(Prediction(
                match_id=m_id, model_parameters_id=model.id, odds_snapshot_id=odds.id,
                as_of=as_of, kickoff_at_prediction=m_date,
                generated_at=as_of + timedelta(seconds=1),
                lambda_home=dist["lambda_home"], mu_away=dist["mu_away"],
                prob_home_win=dist["prob_home_win"], prob_draw=dist["prob_draw"],
                prob_away_win=dist["prob_away_win"], score_matrix=dist["score_matrix"],
                omitted_mass=dist["omitted_mass"], top_scores=dist["top_scores"],
            ))

        await session.commit()
        print("Database seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_database())
