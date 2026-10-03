import math
import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import AppException
from app.models import Match, Team, Prediction, OddsSnapshot, User
from app.api.deps import get_current_user_optional, is_active_analyst
from app.math.ev import calculate_ev, calculate_half_kelly
from app.math.derivatives import compute_derived_markets
from app.math.backtest import run_historical_backtest, BacktestRequest
from app.math.picks import compile_daily_picks

router = APIRouter(prefix="", tags=["Quant Alpha"])


@router.get("/picks/daily")
@router.get("/alpha/picks")
async def get_daily_picks_endpoint(
    league_id: Optional[str] = Query(None, description="League filter (e.g. 'TOP5', 'EPL', 'NORDIC', 'ALL', or specific ID)"),
    days_ahead: int = Query(10, ge=1, le=30),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Curated Daily AI Picks & Accumulators for Casual and Recreational Bettors.
    Categories:
    - ⭐ 今日稳胆 (Banker / High Confidence)
    - 🔥 每日精选 (Pick of the Day / Value)
    - 💣 搏冷高赔 (Underdog & Draw Value)
    - ⚽ 进球狂欢 (Goal Feast / Over 2.5)
    - 🔗 智能 2 串 1 / 3 串 1 方案 (Smart Parlay Generator)
    """
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days_ahead)

    query = (
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.predictions).selectinload(Prediction.odds_snapshot),
            selectinload(Match.predictions).selectinload(Prediction.model_parameters),
        )
        .where(
            Match.status == "SCHEDULED",
            Match.match_date >= now,
            Match.match_date < end_date,
        )
    )

    TOP_5_LEAGUES = ["EPL", "LA_LIGA", "SERIE_A", "BUNDESLIGA", "LIGUE_1"]
    NORDIC_LEAGUES = ["ALLSVENSKAN", "ELITESERIEN", "SUPERLIGA", "AUSTRIAN_BUNDESLIGA"]
    EURO_OTHER = ["CHAMPIONSHIP", "EREDIVISIE", "PRIMEIRA_LIGA"]
    GLOBAL_LEAGUES = ["MLS", "BRASILEIRAO", "SAUDI_PRO_LEAGUE"]
    CUPS = ["UCL", "UEL"]

    if league_id:
        lid_clean = league_id.strip().upper()
        if lid_clean in ("TOP5", "TOP_5", "五大联赛"):
            query = query.where(Match.league_id.in_(TOP_5_LEAGUES))
        elif lid_clean in ("NORDIC", "北欧"):
            query = query.where(Match.league_id.in_(NORDIC_LEAGUES))
        elif lid_clean in ("EURO_OTHER", "欧洲其他"):
            query = query.where(Match.league_id.in_(EURO_OTHER))
        elif lid_clean in ("GLOBAL", "全球"):
            query = query.where(Match.league_id.in_(GLOBAL_LEAGUES))
        elif lid_clean in ("CUPS", "杯赛"):
            query = query.where(Match.league_id.in_(CUPS))
        elif lid_clean not in ("ALL", "*"):
            query = query.where(Match.league_id == lid_clean)

    query = query.order_by(Match.match_date.asc())
    matches = (await db.execute(query)).scalars().all()

    return compile_daily_picks(matches, league_id=league_id)



@router.get("/alpha/scanner")
async def get_alpha_scanner(
    league_id: Optional[str] = Query(None, description="League filter (e.g. 'TOP5', 'EPL', or None for all)"),
    min_ev: float = Query(0.03, ge=-0.50, le=1.0, description="Minimum EV threshold (e.g. 0.03 for 3%)"),
    max_odds: float = Query(12.0, ge=1.01, le=50.0),
    bankroll: float = Query(1000.0, ge=10.0, le=10000000.0),
    strategy: str = Query("HALF_KELLY", pattern="^(FULL_KELLY|HALF_KELLY|QUARTER_KELLY|FIXED_1_PCT|FLAT_UNIT)$"),
    limit: int = Query(40, ge=1, le=100),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time Quantitative +EV Value Scanner.
    Scans live upcoming fixtures, cross-references Dixon-Coles true Poisson probabilities
    against Pinnacle & sharp market quotes, and extracts actionable +EV betting signals.
    """
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=21)

    query = (
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.predictions).selectinload(Prediction.odds_snapshot),
            selectinload(Match.predictions).selectinload(Prediction.model_parameters),
        )
        .where(
            Match.status == "SCHEDULED",
            Match.match_date >= now,
            Match.match_date < end_date,
        )
    )

    TOP_5_LEAGUES = ["EPL", "LA_LIGA", "SERIE_A", "BUNDESLIGA", "LIGUE_1"]
    if league_id:
        lid_clean = league_id.strip().upper()
        if lid_clean in ("TOP5", "TOP_5", "五大联赛"):
            query = query.where(Match.league_id.in_(TOP_5_LEAGUES))
        elif lid_clean not in ("ALL", "*"):
            query = query.where(Match.league_id == lid_clean)

    query = query.order_by(Match.match_date.asc())
    matches = (await db.execute(query)).scalars().all()

    signals: List[Dict[str, Any]] = []

    for m in matches:
        if not m.predictions:
            continue
        latest_pred = max(m.predictions, key=lambda p: p.as_of)
        odds = latest_pred.odds_snapshot
        if not odds:
            continue

        home_odds = float(odds.home_odds)
        draw_odds = float(odds.draw_odds)
        away_odds = float(odds.away_odds)

        # 1X2 market evaluations
        outcomes = [
            ("HOME", f"{m.home_team.canonical_name} (主胜)", latest_pred.prob_home_win, home_odds, odds.implied_prob_home),
            ("DRAW", "平局 (Draw)", latest_pred.prob_draw, draw_odds, odds.implied_prob_draw),
            ("AWAY", f"{m.away_team.canonical_name} (客胜)", latest_pred.prob_away_win, away_odds, odds.implied_prob_away),
        ]

        for code, label, p_model, o_dec, p_market in outcomes:
            if o_dec > max_odds or o_dec <= 1.0:
                continue

            ev = calculate_ev(p_model, o_dec)
            if ev < min_ev:
                continue

            b = o_dec - 1.0
            full_k = max(0.0, ev / b) if b > 0 else 0.0

            if strategy == "FULL_KELLY":
                stake_frac = min(0.08, full_k)
            elif strategy == "HALF_KELLY":
                stake_frac = min(0.05, 0.5 * full_k)
            elif strategy == "QUARTER_KELLY":
                stake_frac = min(0.025, 0.25 * full_k)
            elif strategy == "FIXED_1_PCT":
                stake_frac = 0.01
            else:  # FLAT_UNIT
                stake_frac = 0.015

            stake_amt = round(bankroll * stake_frac, 2)
            exp_profit = round(stake_amt * ev, 2)

            grade = "A+" if ev >= 0.15 else "A" if ev >= 0.08 else "B+"

            signals.append({
                "signal_id": f"SIG_{m.id}_{code}",
                "match_id": m.id,
                "league_id": m.league_id,
                "home_team": m.home_team.canonical_name,
                "away_team": m.away_team.canonical_name,
                "match_date": m.match_date.isoformat(),
                "market_type": "1X2 (Regulation)",
                "selection": code,
                "selection_label": label,
                "bookmaker": odds.bookmaker.capitalize(),
                "market_odds": o_dec,
                "model_prob": round(p_model, 4),
                "market_prob": round(p_market, 4),
                "fair_odds": round(1.0 / p_model, 2) if p_model > 0 else 99.0,
                "edge_pct": round((p_model - p_market) * 100, 2),
                "ev": round(ev, 4),
                "ev_pct": round(ev * 100, 1),
                "half_kelly_pct": round(stake_frac * 100, 2),
                "suggested_stake": stake_amt,
                "expected_profit": exp_profit,
                "confidence_grade": grade,
            })

    # Sort by EV descending
    signals.sort(key=lambda s: s["ev"], reverse=True)
    top_signals = signals[:limit]

    return {
        "timestamp": now.isoformat(),
        "total_signals_found": len(signals),
        "scanned_matches_count": len(matches),
        "bankroll": bankroll,
        "strategy": strategy,
        "signals": top_signals,
    }


@router.get("/analytics/backtest")
async def get_historical_backtest(
    initial_bankroll: float = Query(10000.0, ge=100.0),
    staking_strategy: str = Query("HALF_KELLY"),
    min_ev: float = Query(0.04, ge=0.01, le=0.50),
    max_ev: float = Query(0.40, ge=0.05, le=1.0),
    min_odds: float = Query(1.30, ge=1.01),
    max_odds: float = Query(7.00, le=30.0),
    league_id: Optional[str] = Query(None),
):
    """
    Returns empirical multi-season backtest results, equity curves, drawdown statistics,
    and CLV (Closing Line Value) benchmarks.
    """
    return run_historical_backtest(
        initial_bankroll=initial_bankroll,
        staking_strategy=staking_strategy,
        min_ev=min_ev,
        max_ev=max_ev,
        min_odds=min_odds,
        max_odds=max_odds,
        league_filter=league_id,
    )


@router.post("/analytics/monte-carlo")
async def run_monte_carlo_simulation(
    bankroll: float = Query(10000.0, ge=100.0),
    kelly_fraction: float = Query(0.5, ge=0.1, le=1.0),
    avg_ev: float = Query(0.065, ge=0.01, le=0.25),
    avg_odds: float = Query(2.10, ge=1.2, le=5.0),
    num_bets: int = Query(100, ge=20, le=500),
    num_simulations: int = Query(1000, ge=100, le=5000),
):
    """
    Monte Carlo Portfolio Simulation.
    Simulates thousands of independent betting trajectories based on Kelly sizing
    to compute Value at Risk (VaR), drawdown distributions, and doubling probability.
    """
    rng = random.Random()
    win_prob = (1.0 + avg_ev) / avg_odds

    final_bankrolls = []
    trajectories = []  # Pick 10 sample paths for rendering

    ruin_count = 0
    double_count = 0

    for sim_idx in range(num_simulations):
        current_b = bankroll
        path = [round(current_b, 2)]

        b = avg_odds - 1.0
        full_k = avg_ev / b if b > 0 else 0.0
        stake_pct = min(0.08, kelly_fraction * full_k)

        for _ in range(num_bets):
            if current_b <= bankroll * 0.2:  # Ruin threshold at 80% loss
                ruin_count += 1
                break

            stake = current_b * stake_pct
            if rng.random() < win_prob:
                current_b += stake * b
            else:
                current_b -= stake

            if sim_idx < 8 and len(path) < 101:
                path.append(round(current_b, 2))

        final_bankrolls.append(current_b)
        if current_b >= bankroll * 2.0:
            double_count += 1

        if sim_idx < 8:
            trajectories.append(path)

    final_bankrolls.sort()
    p5 = final_bankrolls[int(0.05 * len(final_bankrolls))]
    p50 = final_bankrolls[int(0.50 * len(final_bankrolls))]
    p95 = final_bankrolls[int(0.95 * len(final_bankrolls))]

    return {
        "inputs": {
            "initial_bankroll": bankroll,
            "kelly_fraction": kelly_fraction,
            "avg_ev_pct": round(avg_ev * 100, 2),
            "avg_odds": avg_odds,
            "num_bets": num_bets,
            "num_simulations": num_simulations,
        },
        "statistics": {
            "expected_bankroll_median": round(p50, 2),
            "expected_pnl_median": round(p50 - bankroll, 2),
            "median_growth_pct": round(((p50 - bankroll) / bankroll) * 100, 2),
            "worst_case_p5": round(p5, 2),
            "best_case_p95": round(p95, 2),
            "probability_doubling_pct": round((double_count / num_simulations) * 100, 1),
            "risk_of_ruin_pct": round((ruin_count / num_simulations) * 100, 2),
        },
        "sample_trajectories": trajectories,
    }
