import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import League, Team, TeamAlias, Match

LEAGUES = [
    # Top 5 Domestic European Leagues
    ("EPL", "Premier League", "England", True),
    ("LA_LIGA", "La Liga", "Spain", True),
    ("SERIE_A", "Serie A", "Italy", True),
    ("BUNDESLIGA", "Bundesliga", "Germany", True),
    ("LIGUE_1", "Ligue 1", "France", True),
    # UEFA Continental Competitions
    ("UCL", "UEFA Champions League", "Europe", True),
    ("UEL", "UEFA Europa League", "Europe", True),
    # Nordic & Central European Leagues (瑞超, 挪超, 丹麦超, 奥甲)
    ("ALLSVENSKAN", "Allsvenskan", "Sweden", True),
    ("ELITESERIEN", "Eliteserien", "Norway", True),
    ("SUPERLIGA", "Superliga", "Denmark", True),
    ("AUSTRIAN_BUNDESLIGA", "Austrian Bundesliga", "Austria", True),
    # Other Major European Leagues
    ("CHAMPIONSHIP", "Championship", "England", True),
    ("EREDIVISIE", "Eredivisie", "Netherlands", True),
    ("PRIMEIRA_LIGA", "Primeira Liga", "Portugal", True),
    # Americas & Global Leagues
    ("MLS", "Major League Soccer", "USA", True),
    ("BRASILEIRAO", "Série A (Brasileirão)", "Brazil", True),
    ("SAUDI_PRO_LEAGUE", "Saudi Pro League", "Saudi Arabia", True),
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

    # Allsvenskan (瑞超 - Sweden)
    ("malmo", "Malmö FF", "Sweden"),
    ("djurgarden", "Djurgårdens IF", "Sweden"),
    ("hammarby", "Hammarby IF", "Sweden"),
    ("aik", "AIK", "Sweden"),
    ("elfsborg", "IF Elfsborg", "Sweden"),
    ("hacken", "BK Häcken", "Sweden"),

    # Eliteserien (挪超 - Norway)
    ("bodo-glimt", "Bodø/Glimt", "Norway"),
    ("brann", "SK Brann", "Norway"),
    ("rosenborg", "Rosenborg BK", "Norway"),
    ("molde", "Molde FK", "Norway"),
    ("viking", "Viking FK", "Norway"),
    ("tromso", "Tromsø IL", "Norway"),

    # Superliga (丹麦超 - Denmark)
    ("copenhagen", "FC Copenhagen", "Denmark"),
    ("midtjylland", "FC Midtjylland", "Denmark"),
    ("brondby", "Brøndby IF", "Denmark"),
    ("aarhus", "AGF Aarhus", "Denmark"),
    ("nordsjaelland", "FC Nordsjælland", "Denmark"),
    ("silkeborg", "Silkeborg IF", "Denmark"),

    # Austrian Bundesliga (奥甲/奥超 - Austria)
    ("salzburg", "Red Bull Salzburg", "Austria"),
    ("sturm-graz", "SK Sturm Graz", "Austria"),
    ("rapid-wien", "Rapid Wien", "Austria"),
    ("austria-wien", "Austria Wien", "Austria"),
    ("lask", "LASK", "Austria"),
    ("wolfsberger", "Wolfsberger AC", "Austria"),

    # English Championship
    ("leeds", "Leeds United", "England"),
    ("burnley", "Burnley", "England"),
    ("sheffield-united", "Sheffield United", "England"),
    ("sunderland", "Sunderland", "England"),
    ("west-brom", "West Bromwich Albion", "England"),
    ("norwich", "Norwich City", "England"),

    # Eredivisie (Netherlands)
    ("ajax", "Ajax", "Netherlands"),
    ("psv", "PSV Eindhoven", "Netherlands"),
    ("feyenoord", "Feyenoord", "Netherlands"),
    ("az-alkmaar", "AZ Alkmaar", "Netherlands"),
    ("twente", "FC Twente", "Netherlands"),

    # Primeira Liga (Portugal)
    ("sporting", "Sporting CP", "Portugal"),
    ("benfica", "Benfica", "Portugal"),
    ("porto", "FC Porto", "Portugal"),
    ("braga", "SC Braga", "Portugal"),

    # MLS (USA)
    ("inter-miami", "Inter Miami", "USA"),
    ("la-galaxy", "LA Galaxy", "USA"),
    ("lafc", "LAFC", "USA"),
    ("columbus-crew", "Columbus Crew", "USA"),

    # Brasileirão (Brazil)
    ("palmeiras", "Palmeiras", "Brazil"),
    ("flamengo", "Flamengo", "Brazil"),
    ("botafogo", "Botafogo", "Brazil"),
    ("sao-paulo", "São Paulo", "Brazil"),

    # Saudi Pro League (Saudi Arabia)
    ("al-hilal", "Al-Hilal", "Saudi Arabia"),
    ("al-nassr", "Al-Nassr", "Saudi Arabia"),
    ("al-ittihad", "Al-Ittihad", "Saudi Arabia"),
    ("al-ahli", "Al-Ahli", "Saudi Arabia"),
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
    # Nordic & Central European Aliases
    ("the_odds_api", None, "Malmo FF", "Sweden", "malmo"),
    ("the_odds_api", None, "Djurgardens IF", "Sweden", "djurgarden"),
    ("the_odds_api", None, "Bodo Glimt", "Norway", "bodo-glimt"),
    ("the_odds_api", None, "Rosenborg", "Norway", "rosenborg"),
    ("the_odds_api", None, "FC Copenhagen", "Denmark", "copenhagen"),
    ("the_odds_api", None, "Brondby", "Denmark", "brondby"),
    ("the_odds_api", None, "RB Salzburg", "Austria", "salzburg"),
    ("the_odds_api", None, "Sturm Graz", "Austria", "sturm-graz"),
    # Other International Aliases
    ("the_odds_api", None, "Leeds", "England", "leeds"),
    ("the_odds_api", None, "Burnley FC", "England", "burnley"),
    ("the_odds_api", None, "Ajax Amsterdam", "Netherlands", "ajax"),
    ("the_odds_api", None, "Sporting Lisbon", "Portugal", "sporting"),
    ("the_odds_api", None, "FC Porto", "Portugal", "porto"),
    ("the_odds_api", None, "Inter Miami CF", "USA", "inter-miami"),
    ("the_odds_api", None, "LAFC", "USA", "lafc"),
    ("the_odds_api", None, "Al Nassr", "Saudi Arabia", "al-nassr"),
    ("the_odds_api", None, "Al Hilal", "Saudi Arabia", "al-hilal"),
]

# Historical completed matches across all 17 leagues
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
    ("LL_2425_001", "LA_LIGA", "2024-08-15T19:00:00Z", "athletic-club", "sevilla", 1, 1, "2024-08-15T21:00:00Z"),
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
    ("SA_2425_001", "SERIE_A", "2024-08-17T18:30:00Z", "milan", "fiorentina", 2, 2, "2024-08-17T20:30:00Z"),
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

    # UCL Historical
    ("UCL_2425_001", "UCL", "2024-09-17T19:00:00Z", "real-madrid", "stuttgart", 3, 1, "2024-09-17T21:00:00Z"),
    ("UCL_2425_002", "UCL", "2024-09-17T19:00:00Z", "bayern-munich", "psg", 4, 1, "2024-09-17T21:00:00Z"),
    ("UCL_2425_003", "UCL", "2024-09-18T19:00:00Z", "manchester-city", "inter", 1, 0, "2024-09-18T21:00:00Z"),
    ("UCL_2425_004", "UCL", "2024-09-19T19:00:00Z", "monaco", "barcelona", 2, 1, "2024-09-19T21:00:00Z"),
    ("UCL_2425_005", "UCL", "2024-10-01T19:00:00Z", "arsenal", "psg", 2, 0, "2024-10-01T21:00:00Z"),
    ("UCL_2425_006", "UCL", "2024-10-01T19:00:00Z", "leverkusen", "milan", 1, 0, "2024-10-01T21:00:00Z"),
    ("UCL_2425_007", "UCL", "2024-10-02T19:00:00Z", "liverpool", "rb-leipzig", 2, 0, "2024-10-02T21:00:00Z"),
    ("UCL_2425_008", "UCL", "2024-10-02T19:00:00Z", "lille", "real-madrid", 1, 0, "2024-10-02T21:00:00Z"),

    # UEL Historical
    ("UEL_2425_001", "UEL", "2024-09-25T19:00:00Z", "manchester-united", "twente", 1, 1, "2024-09-25T21:00:00Z"),
    ("UEL_2425_002", "UEL", "2024-09-26T19:00:00Z", "roma", "athletic-club", 1, 1, "2024-09-26T21:00:00Z"),
    ("UEL_2425_003", "UEL", "2024-09-26T19:00:00Z", "tottenham", "frankfurt", 3, 0, "2024-09-26T21:00:00Z"),
    ("UEL_2425_004", "UEL", "2024-10-03T16:45:00Z", "lazio", "nice", 4, 1, "2024-10-03T18:45:00Z"),
    ("UEL_2425_005", "UEL", "2024-10-03T19:00:00Z", "porto", "manchester-united", 3, 3, "2024-10-03T21:00:00Z"),
    ("UEL_2425_006", "UEL", "2024-10-03T19:00:00Z", "athletic-club", "az-alkmaar", 2, 0, "2024-10-03T21:00:00Z"),

    # Allsvenskan (瑞超) Historical
    ("ALL_2425_001", "ALLSVENSKAN", "2024-08-10T15:00:00Z", "malmo", "hammarby", 2, 1, "2024-08-10T17:00:00Z"),
    ("ALL_2425_002", "ALLSVENSKAN", "2024-08-11T13:00:00Z", "djurgarden", "aik", 1, 0, "2024-08-11T15:00:00Z"),
    ("ALL_2425_003", "ALLSVENSKAN", "2024-08-11T15:30:00Z", "elfsborg", "hacken", 3, 1, "2024-08-11T17:30:00Z"),
    ("ALL_2425_004", "ALLSVENSKAN", "2024-08-18T13:00:00Z", "aik", "malmo", 0, 0, "2024-08-18T15:00:00Z"),
    ("ALL_2425_005", "ALLSVENSKAN", "2024-08-18T15:30:00Z", "hammarby", "elfsborg", 2, 0, "2024-08-18T17:30:00Z"),
    ("ALL_2425_006", "ALLSVENSKAN", "2024-08-25T13:00:00Z", "hacken", "djurgarden", 1, 2, "2024-08-25T15:00:00Z"),
    ("ALL_2425_007", "ALLSVENSKAN", "2024-09-01T13:00:00Z", "malmo", "djurgarden", 4, 0, "2024-09-01T15:00:00Z"),
    ("ALL_2425_008", "ALLSVENSKAN", "2024-09-01T15:30:00Z", "hammarby", "aik", 2, 1, "2024-09-01T17:30:00Z"),

    # Eliteserien (挪超) Historical
    ("ELI_2425_001", "ELITESERIEN", "2024-08-10T16:00:00Z", "bodo-glimt", "molde", 3, 1, "2024-08-10T18:00:00Z"),
    ("ELI_2425_002", "ELITESERIEN", "2024-08-11T15:00:00Z", "brann", "viking", 2, 1, "2024-08-11T17:00:00Z"),
    ("ELI_2425_003", "ELITESERIEN", "2024-08-11T17:15:00Z", "rosenborg", "tromso", 1, 0, "2024-08-11T19:15:00Z"),
    ("ELI_2425_004", "ELITESERIEN", "2024-08-18T15:00:00Z", "molde", "brann", 1, 2, "2024-08-18T17:00:00Z"),
    ("ELI_2425_005", "ELITESERIEN", "2024-08-18T17:15:00Z", "viking", "rosenborg", 2, 1, "2024-08-18T19:15:00Z"),
    ("ELI_2425_006", "ELITESERIEN", "2024-08-25T15:00:00Z", "tromso", "bodo-glimt", 0, 2, "2024-08-25T17:00:00Z"),
    ("ELI_2425_007", "ELITESERIEN", "2024-09-01T15:00:00Z", "bodo-glimt", "brann", 1, 1, "2024-09-01T17:00:00Z"),
    ("ELI_2425_008", "ELITESERIEN", "2024-09-01T17:15:00Z", "rosenborg", "molde", 2, 1, "2024-09-01T19:15:00Z"),

    # Superliga (丹麦超) Historical
    ("SUP_2425_001", "SUPERLIGA", "2024-08-09T17:00:00Z", "copenhagen", "aarhus", 3, 2, "2024-08-09T19:00:00Z"),
    ("SUP_2425_002", "SUPERLIGA", "2024-08-11T14:00:00Z", "midtjylland", "nordsjaelland", 2, 0, "2024-08-11T16:00:00Z"),
    ("SUP_2425_003", "SUPERLIGA", "2024-08-11T16:00:00Z", "brondby", "silkeborg", 1, 1, "2024-08-11T18:00:00Z"),
    ("SUP_2425_004", "SUPERLIGA", "2024-08-18T14:00:00Z", "nordsjaelland", "copenhagen", 1, 1, "2024-08-18T16:00:00Z"),
    ("SUP_2425_005", "SUPERLIGA", "2024-08-18T16:00:00Z", "aarhus", "brondby", 0, 1, "2024-08-18T18:00:00Z"),
    ("SUP_2425_006", "SUPERLIGA", "2024-08-25T14:00:00Z", "silkeborg", "midtjylland", 1, 3, "2024-08-25T16:00:00Z"),
    ("SUP_2425_007", "SUPERLIGA", "2024-09-01T14:00:00Z", "copenhagen", "brondby", 2, 1, "2024-09-01T16:00:00Z"),
    ("SUP_2425_008", "SUPERLIGA", "2024-09-01T16:00:00Z", "midtjylland", "aarhus", 2, 0, "2024-09-01T18:00:00Z"),

    # Austrian Bundesliga (奥甲/奥超) Historical
    ("AB_2425_001", "AUSTRIAN_BUNDESLIGA", "2024-08-03T15:00:00Z", "salzburg", "austria-wien", 2, 0, "2024-08-03T17:00:00Z"),
    ("AB_2425_002", "AUSTRIAN_BUNDESLIGA", "2024-08-04T15:00:00Z", "sturm-graz", "rapid-wien", 1, 0, "2024-08-04T17:00:00Z"),
    ("AB_2425_003", "AUSTRIAN_BUNDESLIGA", "2024-08-04T15:00:00Z", "lask", "wolfsberger", 1, 2, "2024-08-04T17:00:00Z"),
    ("AB_2425_004", "AUSTRIAN_BUNDESLIGA", "2024-08-10T17:30:00Z", "rapid-wien", "salzburg", 1, 1, "2024-08-10T19:30:00Z"),
    ("AB_2425_005", "AUSTRIAN_BUNDESLIGA", "2024-08-11T15:00:00Z", "austria-wien", "lask", 2, 1, "2024-08-11T17:00:00Z"),
    ("AB_2425_006", "AUSTRIAN_BUNDESLIGA", "2024-08-17T17:30:00Z", "wolfsberger", "sturm-graz", 0, 2, "2024-08-17T19:30:00Z"),
    ("AB_2425_007", "AUSTRIAN_BUNDESLIGA", "2024-08-24T17:30:00Z", "salzburg", "sturm-graz", 2, 1, "2024-08-24T19:30:00Z"),
    ("AB_2425_008", "AUSTRIAN_BUNDESLIGA", "2024-08-25T15:00:00Z", "rapid-wien", "austria-wien", 2, 1, "2024-08-25T17:00:00Z"),

    # Championship Historical
    ("CH_2425_001", "CHAMPIONSHIP", "2024-08-10T11:30:00Z", "leeds", "norwich", 3, 3, "2024-08-10T13:30:00Z"),
    ("CH_2425_002", "CHAMPIONSHIP", "2024-08-10T14:00:00Z", "west-brom", "burnley", 1, 2, "2024-08-10T16:00:00Z"),
    ("CH_2425_003", "CHAMPIONSHIP", "2024-08-10T14:00:00Z", "sheffield-united", "sunderland", 2, 0, "2024-08-10T16:00:00Z"),
    ("CH_2425_004", "CHAMPIONSHIP", "2024-08-17T14:00:00Z", "burnley", "leeds", 1, 0, "2024-08-17T16:00:00Z"),
    ("CH_2425_005", "CHAMPIONSHIP", "2024-08-17T14:00:00Z", "sunderland", "west-brom", 2, 1, "2024-08-17T16:00:00Z"),
    ("CH_2425_006", "CHAMPIONSHIP", "2024-08-24T14:00:00Z", "norwich", "sheffield-united", 1, 1, "2024-08-24T16:00:00Z"),

    # Eredivisie Historical
    ("ER_2425_001", "EREDIVISIE", "2024-08-10T18:00:00Z", "psv", "twente", 4, 1, "2024-08-10T20:00:00Z"),
    ("ER_2425_002", "EREDIVISIE", "2024-08-10T20:00:00Z", "feyenoord", "az-alkmaar", 2, 1, "2024-08-10T22:00:00Z"),
    ("ER_2425_003", "EREDIVISIE", "2024-08-11T12:30:00Z", "ajax", "twente", 2, 0, "2024-08-11T14:30:00Z"),
    ("ER_2425_004", "EREDIVISIE", "2024-08-18T14:45:00Z", "az-alkmaar", "ajax", 1, 1, "2024-08-18T16:45:00Z"),
    ("ER_2425_005", "EREDIVISIE", "2024-08-25T12:30:00Z", "twente", "feyenoord", 1, 2, "2024-08-25T14:30:00Z"),
    ("ER_2425_006", "EREDIVISIE", "2024-09-01T14:45:00Z", "psv", "feyenoord", 3, 2, "2024-09-01T16:45:00Z"),

    # Primeira Liga Historical
    ("PL_2425_001", "PRIMEIRA_LIGA", "2024-08-09T19:15:00Z", "sporting", "braga", 3, 1, "2024-08-09T21:15:00Z"),
    ("PL_2425_002", "PRIMEIRA_LIGA", "2024-08-10T19:30:00Z", "porto", "benfica", 2, 0, "2024-08-10T21:30:00Z"),
    ("PL_2425_003", "PRIMEIRA_LIGA", "2024-08-17T17:00:00Z", "braga", "porto", 1, 2, "2024-08-17T19:00:00Z"),
    ("PL_2425_004", "PRIMEIRA_LIGA", "2024-08-17T19:30:00Z", "benfica", "sporting", 1, 1, "2024-08-17T21:30:00Z"),
    ("PL_2425_005", "PRIMEIRA_LIGA", "2024-08-24T19:30:00Z", "sporting", "porto", 2, 0, "2024-08-24T21:30:00Z"),
    ("PL_2425_006", "PRIMEIRA_LIGA", "2024-09-01T17:00:00Z", "benfica", "braga", 3, 0, "2024-09-01T19:00:00Z"),

    # MLS Historical
    ("MLS_2425_001", "MLS", "2024-07-20T23:30:00Z", "inter-miami", "columbus-crew", 2, 1, "2024-07-21T01:30:00Z"),
    ("MLS_2425_002", "MLS", "2024-07-21T02:30:00Z", "lafc", "la-galaxy", 1, 2, "2024-07-21T04:30:00Z"),
    ("MLS_2425_003", "MLS", "2024-08-10T23:30:00Z", "columbus-crew", "lafc", 3, 1, "2024-08-11T01:30:00Z"),
    ("MLS_2425_004", "MLS", "2024-08-11T02:30:00Z", "la-galaxy", "inter-miami", 1, 3, "2024-08-11T04:30:00Z"),
    ("MLS_2425_005", "MLS", "2024-08-24T23:30:00Z", "inter-miami", "lafc", 2, 0, "2024-08-25T01:30:00Z"),
    ("MLS_2425_006", "MLS", "2024-08-25T02:30:00Z", "columbus-crew", "la-galaxy", 2, 2, "2024-08-25T04:30:00Z"),

    # Brasileirão Historical
    ("BR_2425_001", "BRASILEIRAO", "2024-07-15T21:00:00Z", "botafogo", "palmeiras", 1, 0, "2024-07-15T23:00:00Z"),
    ("BR_2425_002", "BRASILEIRAO", "2024-07-16T23:00:00Z", "flamengo", "sao-paulo", 2, 1, "2024-07-17T01:00:00Z"),
    ("BR_2425_003", "BRASILEIRAO", "2024-07-24T21:00:00Z", "palmeiras", "flamengo", 0, 0, "2024-07-24T23:00:00Z"),
    ("BR_2425_004", "BRASILEIRAO", "2024-07-25T23:00:00Z", "sao-paulo", "botafogo", 1, 2, "2024-07-26T01:00:00Z"),
    ("BR_2425_005", "BRASILEIRAO", "2024-08-11T21:00:00Z", "botafogo", "flamengo", 4, 1, "2024-08-11T23:00:00Z"),
    ("BR_2425_006", "BRASILEIRAO", "2024-08-18T21:00:00Z", "palmeiras", "sao-paulo", 2, 1, "2024-08-18T23:00:00Z"),

    # Saudi Pro League Historical
    ("SPL_2425_001", "SAUDI_PRO_LEAGUE", "2024-08-22T18:00:00Z", "al-nassr", "al-ahli", 1, 1, "2024-08-22T20:00:00Z"),
    ("SPL_2425_002", "SAUDI_PRO_LEAGUE", "2024-08-23T18:00:00Z", "al-hilal", "al-ittihad", 3, 1, "2024-08-23T20:00:00Z"),
    ("SPL_2425_003", "SAUDI_PRO_LEAGUE", "2024-08-30T18:00:00Z", "al-ittihad", "al-ahli", 2, 1, "2024-08-30T20:00:00Z"),
    ("SPL_2425_004", "SAUDI_PRO_LEAGUE", "2024-08-31T18:00:00Z", "al-hilal", "al-nassr", 2, 0, "2024-08-31T20:00:00Z"),
    ("SPL_2425_005", "SAUDI_PRO_LEAGUE", "2024-09-13T18:00:00Z", "al-nassr", "al-ittihad", 3, 1, "2024-09-13T20:00:00Z"),
    ("SPL_2425_006", "SAUDI_PRO_LEAGUE", "2024-09-20T18:00:00Z", "al-ahli", "al-hilal", 1, 2, "2024-09-20T20:00:00Z"),
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
                existing.name = name
                existing.country = country
                existing.active = active

        await session.flush()

        # 2. Teams
        for team_id, name, country in TEAMS:
            stmt = select(Team).where(Team.id == team_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                session.add(Team(id=team_id, canonical_name=name, country=country))
            else:
                existing.canonical_name = name
                existing.country = country

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

        # 5. Scheduled Matches across all 17 leagues
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

            # UCL
            ("UCL_DEMO_001", "UCL", now + timedelta(days=1, hours=5), "real-madrid", "manchester-city"),
            ("UCL_DEMO_002", "UCL", now + timedelta(days=2, hours=2), "bayern-munich", "psg"),
            ("UCL_DEMO_003", "UCL", now + timedelta(days=3, hours=1), "arsenal", "inter"),

            # UEL
            ("UEL_DEMO_001", "UEL", now + timedelta(days=1, hours=6), "manchester-united", "tottenham"),
            ("UEL_DEMO_002", "UEL", now + timedelta(days=2, hours=4), "roma", "athletic-club"),
            ("UEL_DEMO_003", "UEL", now + timedelta(days=3, hours=3), "lazio", "nice"),

            # Allsvenskan (瑞超)
            ("ALL_DEMO_001", "ALLSVENSKAN", now + timedelta(days=1, hours=3), "malmo", "djurgarden"),
            ("ALL_DEMO_002", "ALLSVENSKAN", now + timedelta(days=2, hours=1), "hammarby", "aik"),
            ("ALL_DEMO_003", "ALLSVENSKAN", now + timedelta(days=3, hours=2), "elfsborg", "hacken"),

            # Eliteserien (挪超)
            ("ELI_DEMO_001", "ELITESERIEN", now + timedelta(days=1, hours=4), "bodo-glimt", "brann"),
            ("ELI_DEMO_002", "ELITESERIEN", now + timedelta(days=2, hours=2), "rosenborg", "molde"),
            ("ELI_DEMO_003", "ELITESERIEN", now + timedelta(days=3, hours=3), "viking", "tromso"),

            # Superliga (丹麦超)
            ("SUP_DEMO_001", "SUPERLIGA", now + timedelta(days=1, hours=2), "copenhagen", "midtjylland"),
            ("SUP_DEMO_002", "SUPERLIGA", now + timedelta(days=2, hours=4), "brondby", "aarhus"),
            ("SUP_DEMO_003", "SUPERLIGA", now + timedelta(days=3, hours=1), "nordsjaelland", "silkeborg"),

            # Austrian Bundesliga (奥甲/奥超)
            ("AB_DEMO_001", "AUSTRIAN_BUNDESLIGA", now + timedelta(days=1, hours=1), "salzburg", "sturm-graz"),
            ("AB_DEMO_002", "AUSTRIAN_BUNDESLIGA", now + timedelta(days=2, hours=3), "rapid-wien", "austria-wien"),
            ("AB_DEMO_003", "AUSTRIAN_BUNDESLIGA", now + timedelta(days=3, hours=4), "lask", "wolfsberger"),

            # Championship
            ("CH_DEMO_001", "CHAMPIONSHIP", now + timedelta(days=1, hours=2), "leeds", "sheffield-united"),
            ("CH_DEMO_002", "CHAMPIONSHIP", now + timedelta(days=2, hours=3), "burnley", "sunderland"),
            ("CH_DEMO_003", "CHAMPIONSHIP", now + timedelta(days=3, hours=2), "west-brom", "norwich"),

            # Eredivisie
            ("ER_DEMO_001", "EREDIVISIE", now + timedelta(days=1, hours=1), "psv", "ajax"),
            ("ER_DEMO_002", "EREDIVISIE", now + timedelta(days=2, hours=4), "feyenoord", "twente"),
            ("ER_DEMO_003", "EREDIVISIE", now + timedelta(days=3, hours=4), "az-alkmaar", "psv"),

            # Primeira Liga
            ("PL_DEMO_001", "PRIMEIRA_LIGA", now + timedelta(days=1, hours=4), "benfica", "sporting"),
            ("PL_DEMO_002", "PRIMEIRA_LIGA", now + timedelta(days=2, hours=2), "porto", "braga"),

            # MLS
            ("MLS_DEMO_001", "MLS", now + timedelta(days=1, hours=6), "inter-miami", "columbus-crew"),
            ("MLS_DEMO_002", "MLS", now + timedelta(days=2, hours=5), "lafc", "la-galaxy"),

            # Brasileirão
            ("BR_DEMO_001", "BRASILEIRAO", now + timedelta(days=1, hours=3), "botafogo", "flamengo"),
            ("BR_DEMO_002", "BRASILEIRAO", now + timedelta(days=2, hours=1), "palmeiras", "sao-paulo"),

            # Saudi Pro League
            ("SPL_DEMO_001", "SAUDI_PRO_LEAGUE", now + timedelta(days=1, hours=2), "al-hilal", "al-ittihad"),
            ("SPL_DEMO_002", "SAUDI_PRO_LEAGUE", now + timedelta(days=2, hours=4), "al-nassr", "al-ahli"),
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
        print("Database seeded with all 17 leagues including Nordic & Central European leagues successfully.")


if __name__ == "__main__":
    asyncio.run(seed_database())
