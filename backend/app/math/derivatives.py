import math
from typing import Dict, Any, List, Optional

from scipy.stats import poisson


def _pmf(k: int, mu: float) -> float:
    if k < 0 or mu <= 0:
        return 0.0
    return float(poisson.pmf(k, mu))


def _sf_ge(k: int, mu: float) -> float:
    """P(X >= k) for a Poisson random variable."""
    if k <= 0:
        return 1.0
    if mu <= 0:
        return 0.0
    return float(poisson.sf(k - 1, mu))


def _outside_mass(lam: float, mu: float, window: int = 6) -> float:
    px = _sf_ge(window, lam)
    py = _sf_ge(window, mu)
    return max(0.0, px + py - px * py)


def _tail_margin(lam: float, mu: float, margin: int = 2, window: int = 6) -> float:
    """P(X - Y >= margin) on scores outside the display window.

    Dixon-Coles tau is 1 for every cell outside {0,1}×{0,1}, so the tail is Poisson.
    """
    total = 0.0
    for y in range(window):
        x_min = max(window, y + margin)
        total += _pmf(y, mu) * _sf_ge(x_min, lam)

    spread = max(lam, mu, 1.0)
    k_max = int(spread + 12 * math.sqrt(spread) + window + margin + 5)
    k_max = min(max(k_max, window + 15), 80)
    for y in range(window, k_max + 1):
        total += _pmf(y, mu) * _sf_ge(y + margin, lam)
    return max(0.0, total)


def compute_derived_markets(
    score_matrix: List[List[float]],
    lambda_home: float,
    mu_away: float,
    omitted_mass: float = 0.0,
    prob_home_win: Optional[float] = None,
    prob_draw: Optional[float] = None,
    prob_away_win: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Derives totals, BTTS, Asian lines, and clean sheets.

    Totals add the omitted tail because every score outside 0..5 has at least six goals.
    BTTS and the ±1.5 lines add only the Poisson tail cells that actually win those bets.
    1X2 markets use the full-distribution probabilities when the caller supplies them.
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

    # Scores outside 0..5 have at least six goals. 6-0 and 0-6 stay BTTS No.
    if omitted_mass > 0:
        p_ou_1_5_over += omitted_mass
        p_ou_2_5_over += omitted_mass
        p_ou_3_5_over += omitted_mass
        scoreless_tail = (
            _sf_ge(6, lambda_home) * _pmf(0, mu_away)
            + _sf_ge(6, mu_away) * _pmf(0, lambda_home)
        )
        p_btts_yes += max(0.0, omitted_mass - scoreless_tail)

    p_home_minus_1_5 += _tail_margin(lambda_home, mu_away, margin=2)
    away_by_two_tail = _tail_margin(mu_away, lambda_home, margin=2)
    p_home_plus_1_5 += max(0.0, _outside_mass(lambda_home, mu_away) - away_by_two_tail)
    p_home_clean_sheet += _sf_ge(6, lambda_home) * _pmf(0, mu_away)
    p_away_clean_sheet += _sf_ge(6, mu_away) * _pmf(0, lambda_home)

    p_ou_1_5_over = min(1.0, p_ou_1_5_over)
    p_ou_2_5_over = min(1.0, p_ou_2_5_over)
    p_ou_3_5_over = min(1.0, p_ou_3_5_over)
    p_btts_yes = min(1.0, max(0.0, p_btts_yes))
    p_home_minus_1_5 = min(1.0, max(0.0, p_home_minus_1_5))
    p_home_plus_1_5 = min(1.0, max(0.0, p_home_plus_1_5))
    p_home_clean_sheet = min(1.0, max(0.0, p_home_clean_sheet))
    p_away_clean_sheet = min(1.0, max(0.0, p_away_clean_sheet))

    p_ou_1_5_under = max(0.0, 1.0 - p_ou_1_5_over)
    p_ou_2_5_under = max(0.0, 1.0 - p_ou_2_5_over)
    p_ou_3_5_under = max(0.0, 1.0 - p_ou_3_5_over)
    p_btts_no = max(0.0, 1.0 - p_btts_yes)

    # Full-distribution 1X2 when supplied. A missing 1X2 stays the raw 6×6 sum.
    if prob_home_win is not None and prob_draw is not None and prob_away_win is not None:
        p_home = prob_home_win
        p_draw = prob_draw
        p_away = prob_away_win
    else:
        p_home = sum(score_matrix[h][a] for h in range(len(score_matrix)) for a in range(len(score_matrix[h])) if h > a)
        p_draw = sum(score_matrix[h][h] for h in range(min(len(score_matrix), len(score_matrix[0]))))
        p_away = sum(score_matrix[h][a] for h in range(len(score_matrix)) for a in range(len(score_matrix[h])) if h < a)
    # Double Chance
    p_dc_1x = min(1.0, max(0.0, p_home + p_draw))
    p_dc_x2 = min(1.0, max(0.0, p_draw + p_away))
    p_dc_12 = min(1.0, max(0.0, p_home + p_away))

    # Draw No Bet (DNB)
    p_dnb_denom = p_home + p_away
    p_dnb_home = (p_home / p_dnb_denom) if p_dnb_denom > 0 else 0.5
    p_dnb_away = (p_away / p_dnb_denom) if p_dnb_denom > 0 else 0.5

    def _fair(prob: float) -> float:
        if prob <= 0.0001:
            return 999.0
        return round(1.0 / prob, 2)

    return {
        # Field name kept for API compatibility. Despite the name, this value is
        # the omitted probability mass outside the 0..5 display window
        # (1 - display sum): the accuracy bound of the truncated matrix, not a
        # numerical error estimate of the calculation.
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
