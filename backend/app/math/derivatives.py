import math
from typing import Dict, Any, List, Optional


def compute_derived_markets(
    score_matrix: List[List[float]],
    lambda_home: float,
    mu_away: float,
    omitted_mass: float = 0.0,
) -> Dict[str, Any]:
    """
    Derives advanced betting markets directly from the 6x6 bivariate Poisson probability matrix:
    - Totals (Over / Under 1.5, 2.5, 3.5 Goals)
    - Both Teams To Score (BTTS: Yes / No)
    - Double Chance (1X, X2, 12)
    - Draw No Bet (DNB: Home / Away)
    - Asian Handicap (Home -0.5, +0.5, -1.5, +1.5)
    - Clean Sheets & Goal Expectancy
    """
    if not score_matrix or len(score_matrix) < 6:
        return {}

    # Total Goals Distributions
    p_ou_1_5_over = 0.0
    p_ou_2_5_over = 0.0
    p_ou_3_5_over = 0.0

    # BTTS
    p_btts_yes = 0.0

    # Asian Handicap / Spreads
    p_home_minus_1_5 = 0.0
    p_home_plus_1_5 = 0.0

    # Clean Sheets
    p_home_clean_sheet = 0.0
    p_away_clean_sheet = 0.0

    # Summing across 6x6 grid
    for h in range(len(score_matrix)):
        for a in range(len(score_matrix[h])):
            p = float(score_matrix[h][a])
            total_goals = h + a

            if total_goals > 1.5:
                p_ou_1_5_over += p
            if total_goals > 2.5:
                p_ou_2_5_over += p
            if total_goals > 3.5:
                p_ou_3_5_over += p

            if h >= 1 and a >= 1:
                p_btts_yes += p

            diff = h - a
            if diff >= 2:
                p_home_minus_1_5 += p
            if (a - h) <= 1:
                p_home_plus_1_5 += p

            if a == 0:
                p_home_clean_sheet += p
            if h == 0:
                p_away_clean_sheet += p

    # Any omitted score has at least six total goals, but its BTTS state is unknown.
    if omitted_mass > 0:
        p_ou_1_5_over += omitted_mass
        p_ou_2_5_over += omitted_mass
        p_ou_3_5_over += omitted_mass

    p_ou_1_5_under = max(0.001, 1.0 - p_ou_1_5_over)
    p_ou_2_5_under = max(0.001, 1.0 - p_ou_2_5_over)
    p_ou_3_5_under = max(0.001, 1.0 - p_ou_3_5_over)
    p_btts_no = max(0.001, 1.0 - p_btts_yes)

    # 1X2 probabilities directly from matrix
    p_home = sum(score_matrix[h][a] for h in range(len(score_matrix)) for a in range(len(score_matrix[h])) if h > a)
    p_draw = sum(score_matrix[h][h] for h in range(min(len(score_matrix), len(score_matrix[0]))))
    p_away = sum(score_matrix[h][a] for h in range(len(score_matrix)) for a in range(len(score_matrix[h])) if h < a)
    total_1x2 = p_home + p_draw + p_away
    if total_1x2 > 0:
        p_home /= total_1x2
        p_draw /= total_1x2
        p_away /= total_1x2

    # Double Chance
    p_dc_1x = min(0.999, p_home + p_draw)
    p_dc_x2 = min(0.999, p_draw + p_away)
    p_dc_12 = min(0.999, p_home + p_away)

    # Draw No Bet (DNB)
    p_dnb_denom = p_home + p_away
    p_dnb_home = (p_home / p_dnb_denom) if p_dnb_denom > 0 else 0.5
    p_dnb_away = (p_away / p_dnb_denom) if p_dnb_denom > 0 else 0.5

    def _fair(prob: float) -> float:
        if prob <= 0.0001:
            return 999.0
        return round(1.0 / prob, 2)

    return {
        "probability_error_bound": round(omitted_mass, 12),
        "expected_goals": {
            "home": round(lambda_home, 3),
            "away": round(mu_away, 3),
            "total": round(lambda_home + mu_away, 3),
            "spread": round(lambda_home - mu_away, 3),
        },
        "totals": {
            "over_1_5": {"prob": round(p_ou_1_5_over, 4), "fair_odds": _fair(p_ou_1_5_over)},
            "under_1_5": {"prob": round(p_ou_1_5_under, 4), "fair_odds": _fair(p_ou_1_5_under)},
            "over_2_5": {"prob": round(p_ou_2_5_over, 4), "fair_odds": _fair(p_ou_2_5_over)},
            "under_2_5": {"prob": round(p_ou_2_5_under, 4), "fair_odds": _fair(p_ou_2_5_under)},
            "over_3_5": {"prob": round(p_ou_3_5_over, 4), "fair_odds": _fair(p_ou_3_5_over)},
            "under_3_5": {"prob": round(p_ou_3_5_under, 4), "fair_odds": _fair(p_ou_3_5_under)},
        },
        "btts": {
            "yes": {"prob": round(p_btts_yes, 4), "fair_odds": _fair(p_btts_yes)},
            "no": {"prob": round(p_btts_no, 4), "fair_odds": _fair(p_btts_no)},
        },
        "double_chance": {
            "1x": {"prob": round(p_dc_1x, 4), "fair_odds": _fair(p_dc_1x)},
            "x2": {"prob": round(p_dc_x2, 4), "fair_odds": _fair(p_dc_x2)},
            "12": {"prob": round(p_dc_12, 4), "fair_odds": _fair(p_dc_12)},
        },
        "draw_no_bet": {
            "home": {"prob": round(p_dnb_home, 4), "fair_odds": _fair(p_dnb_home)},
            "away": {"prob": round(p_dnb_away, 4), "fair_odds": _fair(p_dnb_away)},
        },
        "asian_handicap": {
            "home_minus_0_5": {"prob": round(p_home, 4), "fair_odds": _fair(p_home)},
            "home_plus_0_5": {"prob": round(p_dc_1x, 4), "fair_odds": _fair(p_dc_1x)},
            "home_minus_1_5": {"prob": round(p_home_minus_1_5, 4), "fair_odds": _fair(p_home_minus_1_5)},
            "home_plus_1_5": {"prob": round(p_home_plus_1_5, 4), "fair_odds": _fair(p_home_plus_1_5)},
        },
        "clean_sheets": {
            "home": {"prob": round(p_home_clean_sheet, 4), "fair_odds": _fair(p_home_clean_sheet)},
            "away": {"prob": round(p_away_clean_sheet, 4), "fair_odds": _fair(p_away_clean_sheet)},
        },
    }
