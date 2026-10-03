import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import League, Team, TeamAlias, Match

LEAGUES = [
    ("EPL", "Premier League", "England", True),
    ("LA_LIGA", "La Liga", "Spain", True),
    ("SERIE_A", "Serie A", "Italy", True),
    ("BUNDESLIGA", "Bundesliga", "Germany", True),
    ("LIGUE_1", "Ligue 1", "France", True),
]

TEAMS = [
    # EPL (England)
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

    # La Liga (Spain)
    ("real-madrid", "Real Madrid", "Spain"),
    ("barcelona", "Barcelona", "Spain"),
    ("atletico-madrid", "Atletico Madrid", "Spain"),
    ("girona", "Girona", "Spain"),
    ("athletic-club", "Athletic Club", "Spain"),
    ("real-sociedad", "Real Sociedad", "Spain"),
    ("real-betis", "Real Betis", "Spain"),
    ("villarreal", "Villarreal", "Spain"),
    ("valencia", "Valencia", "Spain"),
    ("sevilla", "Sevilla", "Spain"),

    # Serie A (Italy)
    ("inter", "Inter Milan", "Italy"),
    ("milan", "AC Milan", "Italy"),
    ("juventus", "Juventus", "Italy"),
    ("atalanta", "Atalanta", "Italy"),
    ("roma", "AS Roma", "Italy"),
    ("lazio", "Lazio", "Italy"),
    ("napoli", "Napoli", "Italy"),
    ("fiorentina", "Fiorentina", "Italy"),

    # Bundesliga (Germany)
    ("leverkusen", "Bayer Leverkusen", "Germany"),
    ("bayern-munich", "Bayern Munich", "Germany"),
    ("stuttgart", "VfB Stuttgart", "Germany"),
    ("rb-leipzig", "RB Leipzig", "Germany"),
    ("dortmund", "Borussia Dortmund", "Germany"),
    ("frankfurt", "Eintracht Frankfurt", "Germany"),

    # Ligue 1 (France)
    ("psg", "Paris Saint-Germain", "France"),
    ("monaco", "Monaco", "France"),
    ("brest", "Brest", "France"),
    ("lille", "Lille", "France"),
    ("nice", "Nice", "France"),
    ("lyon", "Lyon", "France"),
    ("marseille", "Marseille", "France"),
]

CONFIRMED_ALIASES = [
    # EPL Aliases
    ("the_odds_api", None, "Arsenal", "England", "arsenal"),
    ("the_odds_api", None, "Chelsea", "England", "chelsea"),
    ("the_odds_api", None, "Liverpool", "England", "liverpool"),
    ("the_odds_api", None, "Manchester City", "England", "manchester-city"),
    ("the_odds_api", None, "Manchester United", "England", "manchester-united"),
    ("the_odds_api", None, "Tottenham Hotspur", "England", "tottenham"),
    ("football_data", None, "Man City", "England", "manchester-city"),
    ("football_data", None, "Man United", "England", "manchester-united"),
    ("football_data", None, "Spurs", "England", "tottenham"),
    # La Liga Aliases
    ("the_odds_api", None, "Real Madrid", "Spain", "real-madrid"),
    ("the_odds_api", None, "Barcelona", "Spain", "barcelona"),
    ("the_odds_api", None, "Atletico Madrid", "Spain", "atletico-madrid"),
    ("the_odds_api", None, "Sevilla FC", "Spain", "sevilla"),
    ("football_data", None, "Ath Bilbao", "Spain", "athletic-club"),
    ("football_data", None, "Atl Madrid", "Spain", "atletico-madrid"),
    # Serie A Aliases
    ("the_odds_api", None, "Inter", "Italy", "inter"),
    ("the_odds_api", None, "AC Milan", "Italy", "milan"),
    ("the_odds_api", None, "Juventus", "Italy", "juventus"),
    ("football_data", None, "Inter Milan", "Italy", "inter"),
    ("football_data", None, "Roma", "Italy", "roma"),
    # Bundesliga Aliases
    ("the_odds_api", None, "Bayern Munich", "Germany", "bayern-munich"),
    ("the_odds_api", None, "Borussia Dortmund", "Germany", "dortmund"),
    ("the_odds_api", None, "Bayer Leverkusen", "Germany", "leverkusen"),
    ("football_data", None, "Bayern", "Germany", "bayern-munich"),
    # Ligue 1 Aliases
    ("the_odds_api", None, "Paris SG", "France", "psg"),
    ("the_odds_api", None, "PSG", "France", "psg"),
    ("the_odds_api", None, "AS Monaco", "France", "monaco"),
    ("football_data", None, "Paris Saint Germain", "France", "psg"),
]

# Historical results across all 5 leagues
HISTORICAL_MATCHES = [
    # EPL Historical
    ("EPL_2425_001", "EPL", "2024-08-16T19:00:00Z", "manchester-united", "fulham", 1, 0, "2024-08-16T21:00:00Z"),
    ("EPL_2425_002", "EPL", "2024-08-17T11:30:00Z", "ipswich", "liverpool", 0, 2, "2024-08-17T13:30:00Z"),
    ("EPL_2425_003", "EPL", "2024-08-17T14:00:00Z", "arsenal", "wolves", 2, 0, "2024-08-17T16:00:00Z"),
    ("EPL_2425_004", "EPL", "2024-08-17T14:00:00Z", "everton", "brighton", 0, 3, "2024-08-17T16:00:00Z"),
    ("EPL_2425_005", "EPL", "2024-08-17T14:00:00Z", "newcastle", "southampton", 1, 0, "2024-08-17T16:00:00Z"),
    ("EPL_2425_006", "EPL", "2024-08-17T14:00:00Z", "nottingham-forest", "bournemouth", 1, 1, "2024-08-17T16:00:00Z"),
    ("EPL_2425_007", "EPL", "2024-08-17T16:30:00Z", "west-ham", "aston-villa", 1, 2, "2024-08-17T18:30:00Z"),
    ("EPL_2425_008", "EPL", "2024-08-18T13:00:00Z", "brentford", "crystal-palace", 2, 1, "2024-08-18T15:00:00Z"),
    ("EPL_2425_009", "EPL", "2024-08-18T15:30:00Z", "chelsea", "manchester-city", 0, 2, "2024-08-18T17:30:00Z"),
    ("EPL_2425_010", "EPL", "2024-08-19T19:00:00Z", "leicester", "tottenham", 1, 1, "2024-08-19T21:00:00Z"),
    ("EPL_2425_011", "EPL", "2024-08-24T11:30:00Z", "brighton", "manchester-united", 2, 1, "2024-08-24T13:30:00Z"),
    ("EPL_2425_012", "EPL", "2024-08-24T14:00:00Z", "crystal-palace", "west-ham", 0, 2, "2024-08-24T16:00:00Z"),
    ("EPL_2425_013", "EPL", "2024-08-24T14:00:00Z", "fulham", "leicester", 2, 1, "2024-08-24T16:00:00Z"),
    ("EPL_2425_014", "EPL", "2024-08-24T14:00:00Z", "manchester-city", "ipswich", 4, 1, "2024-08-24T16:00:00Z"),
    ("EPL_2425_015", "EPL", "2024-08-24T14:00:00Z", "southampton", "nottingham-forest", 0, 1, "2024-08-24T16:00:00Z"),
    ("EPL_2425_016", "EPL", "2024-08-24T14:00:00Z", "tottenham", "everton", 4, 0, "2024-08-24T16:00:00Z"),
    ("EPL_2425_017", "EPL", "2024-08-24T16:30:00Z", "aston-villa", "arsenal", 0, 2, "2024-08-24T18:30:00Z"),
    ("EPL_2425_018", "EPL", "2024-08-25T13:00:00Z", "bournemouth", "newcastle", 1, 1, "2024-08-25T15:00:00Z"),
    ("EPL_2425_019", "EPL", "2024-08-25T13:00:00Z", "wolves", "chelsea", 2, 6, "2024-08-25T15:00:00Z"),
    ("EPL_2425_020", "EPL", "2024-08-25T15:30:00Z", "liverpool", "brentford", 2, 0, "2024-08-25T17:30:00Z"),

    # La Liga Historical
    ("LL_2425_001", "LA_LIGA", "2024-08-15T19:00:00Z", "athletic-club", "getafe" if "getafe" in [t[0] for t in TEAMS] else "sevilla", 1, 1, "2024-08-15T21:00:00Z"),
    ("LL_2425_002", "LA_LIGA", "2024-08-15T21:30:00Z", "real-betis", "girona", 1, 1, "2024-08-15T23:30:00Z"),
    ("LL_2425_003", "LA_LIGA", "2024-08-17T19:30:00Z", "valencia", "barcelona", 1, 2, "2024-08-17T21:30:00Z"),
    ("LL_2425_004", "LA_LIGA", "2024-08-18T19:30:00Z", "villarreal", "atletico-madrid", 2, 2, "2024-08-18T21:30:00Z"),
    ("LL_2425_005", "LA_LIGA", "2024-08-18T21:30:00Z", "real-sociedad", "valencia", 2, 1, "2024-08-18T23:30:00Z"),
    ("LL_2425_006", "LA_LIGA", "2024-08-19T21:30:00Z", "real-madrid", "sevilla", 3, 0, "2024-08-19T23:30:00Z"),
    ("LL_2425_007", "LA_LIGA", "2024-08-23T19:00:00Z", "sevilla", "villarreal", 1, 2, "2024-08-23T21:00:00Z"),
    ("LL_2425_008", "LA_LIGA", "2024-08-24T19:00:00Z", "barcelona", "athletic-club", 2, 1, "2024-08-24T21:00:00Z"),
    ("LL_2425_009", "LA_LIGA", "2024-08-25T17:00:00Z", "real-madrid", "real-betis", 2, 0, "2024-08-25T19:00:00Z"),
    ("LL_2425_010", "LA_LIGA", "2024-08-25T19:30:00Z", "atletico-madrid", "girona", 3, 0, "2024-08-25T21:30:00Z"),
    ("LL_2425_011", "LA_LIGA", "2024-08-31T17:00:00Z", "barcelona", "valencia", 7, 0, "2024-08-31T19:00:00Z"),
    ("LL_2425_012", "LA_LIGA", "2024-09-01T19:30:00Z", "real-madrid", "real-sociedad", 2, 0, "2024-09-01T21:30:00Z"),

    # Serie A Historical
    ("SA_2425_001", "SERIE_A", "2024-08-17T18:30:00Z", "milan", "torino" if "torino" in [t[0] for t in TEAMS] else "fiorentina", 2, 2, "2024-08-17T20:30:00Z"),
    ("SA_2425_002", "SERIE_A", "2024-08-17T18:30:00Z", "inter", "atalanta", 4, 0, "2024-08-17T20:30:00Z"),
    ("SA_2425_003", "SERIE_A", "2024-08-18T18:30:00Z", "roma", "lazio", 1, 0, "2024-08-18T20:30:00Z"),
    ("SA_2425_004", "SERIE_A", "2024-08-18T20:45:00Z", "juventus", "napoli", 3, 0, "2024-08-18T22:45:00Z"),
    ("SA_2425_005", "SERIE_A", "2024-08-24T18:30:00Z", "inter", "fiorentina", 2, 1, "2024-08-24T20:30:00Z"),
    ("SA_2425_006", "SERIE_A", "2024-08-24T20:45:00Z", "napoli", "milan", 2, 1, "2024-08-24T22:45:00Z"),
    ("SA_2425_007", "SERIE_A", "2024-08-25T18:30:00Z", "atalanta", "juventus", 1, 2, "2024-08-25T20:30:00Z"),
    ("SA_2425_008", "SERIE_A", "2024-08-25T20:45:00Z", "roma", "inter", 0, 1, "2024-08-25T22:45:00Z"),

    # Bundesliga Historical
    ("BL_2425_001", "BUNDESLIGA", "2024-08-23T18:30:00Z", "dortmund", "frankfurt", 2, 0, "2024-08-23T20:30:00Z"),
    ("BL_2425_002", "BUNDESLIGA", "2024-08-24T13:30:00Z", "leverkusen", "stuttgart", 3, 2, "2024-08-24T15:30:00Z"),
    ("BL_2425_003", "BUNDESLIGA", "2024-08-24T13:30:00Z", "bayern-munich", "rb-leipzig", 3, 2, "2024-08-24T15:30:00Z"),
    ("BL_2425_004", "BUNDESLIGA", "2024-08-31T16:30:00Z", "leverkusen", "rb-leipzig", 2, 3, "2024-08-31T18:30:00Z"),
    ("BL_2425_005", "BUNDESLIGA", "2024-09-01T15:30:00Z", "bayern-munich", "dortmund", 2, 0, "2024-09-01T17:30:00Z"),
    ("BL_2425_006", "BUNDESLIGA", "2024-09-14T13:30:00Z", "stuttgart", "frankfurt", 1, 1, "2024-09-14T15:30:00Z"),

    # Ligue 1 Historical
    ("L1_2425_001", "LIGUE_1", "2024-08-16T18:45:00Z", "brest", "marseille", 1, 5, "2024-08-16T20:45:00Z"),
    ("L1_2425_002", "LIGUE_1", "2024-08-17T17:00:00Z", "monaco", "lyon", 1, 0, "2024-08-17T19:00:00Z"),
    ("L1_2425_003", "LIGUE_1", "2024-08-18T18:45:00Z", "psg", "lille", 3, 1, "2024-08-18T20:45:00Z"),
    ("L1_2425_004", "LIGUE_1", "2024-08-23T18:45:00Z", "psg", "monaco", 6, 0, "2024-08-23T20:45:00Z"),
    ("L1_2425_005", "LIGUE_1", "2024-08-24T15:00:00Z", "lyon", "nice", 0, 2, "2024-08-24T17:00:00Z"),
    ("L1_2425_006", "LIGUE_1", "2024-08-25T18:45:00Z", "marseille", "lille", 2, 2, "2024-08-25T20:45:00Z"),
]


async def seed_database():
    async with AsyncSessionLocal() as session:
        # 1. Leagues
        for l_id, name, country, active in LEAGUES:
            stmt = select(League).where(League.id == l_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                session.add(League(id=l_id, name=name, country=country, active=active))
            else:
                existing.active = active

        await session.flush()

        # 2. Teams
        for team_id, name, country in TEAMS:
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
        for m_id, l_id, m_date_str, h_team, a_team, h_score, a_score, res_avail_str in HISTORICAL_MATCHES:
            stmt = select(Match).where(Match.id == m_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                m_date = datetime.fromisoformat(m_date_str.replace("Z", "+00:00"))
                res_avail = datetime.fromisoformat(res_avail_str.replace("Z", "+00:00"))
                session.add(Match(
                    id=m_id,
                    league_id=l_id,
                    season="2024-2025",
                    match_date=m_date,
                    home_team_id=h_team,
                    away_team_id=a_team,
                    status="FINISHED",
                    home_score=h_score,
                    away_score=a_score,
                    result_available_at=res_avail,
                ))

        # 5. Scheduled Matches for all 5 leagues
        now = datetime.now(timezone.utc)
        scheduled_fixtures = [
            # EPL
            ("EPL_DEMO_001", "EPL", now + timedelta(days=1), "arsenal", "chelsea"),
            ("EPL_DEMO_002", "EPL", now + timedelta(days=2), "manchester-city", "liverpool"),
            ("EPL_DEMO_003", "EPL", now + timedelta(days=2, hours=3), "tottenham", "manchester-united"),
            ("EPL_DEMO_004", "EPL", now + timedelta(days=3), "aston-villa", "newcastle"),
            # La Liga
            ("LL_DEMO_001", "LA_LIGA", now + timedelta(days=1, hours=2), "real-madrid", "barcelona"),
            ("LL_DEMO_002", "LA_LIGA", now + timedelta(days=2, hours=4), "atletico-madrid", "sevilla"),
            ("LL_DEMO_003", "LA_LIGA", now + timedelta(days=3), "athletic-club", "real-sociedad"),
            # Serie A
            ("SA_DEMO_001", "SERIE_A", now + timedelta(days=1, hours=4), "inter", "milan"),
            ("SA_DEMO_002", "SERIE_A", now + timedelta(days=2, hours=1), "juventus", "roma"),
            ("SA_DEMO_003", "SERIE_A", now + timedelta(days=3, hours=2), "napoli", "atalanta"),
            # Bundesliga
            ("BL_DEMO_001", "BUNDESLIGA", now + timedelta(days=1, hours=1), "bayern-munich", "dortmund"),
            ("BL_DEMO_002", "BUNDESLIGA", now + timedelta(days=2, hours=3), "leverkusen", "rb-leipzig"),
            # Ligue 1
            ("L1_DEMO_001", "LIGUE_1", now + timedelta(days=1, hours=3), "psg", "marseille"),
            ("L1_DEMO_002", "LIGUE_1", now + timedelta(days=2, hours=5), "monaco", "lyon"),
        ]

        for m_id, l_id, m_date, h_team, a_team in scheduled_fixtures:
            stmt = select(Match).where(Match.id == m_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                session.add(Match(
                    id=m_id,
                    league_id=l_id,
                    season="2024-2025",
                    match_date=m_date,
                    home_team_id=h_team,
                    away_team_id=a_team,
                    status="SCHEDULED",
                ))

        await session.commit()
        print("Database seeded with European Top 5 Leagues successfully.")


if __name__ == "__main__":
    asyncio.run(seed_database())
