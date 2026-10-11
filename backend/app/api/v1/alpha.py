import math
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import AppException
from app.models import Match, Prediction, User
from app.api.deps import require_analyst_user
from app.core.rate_limiter import check_rate_limit
from app.api.v1.matches import evaluate_fixture_analysis
from app.math.freshness import latest_eligible_quote
from app.math.ev import calculate_ev
from app.math.backtest import run_historical_backtest
from app.math.picks import compile_daily_picks, MAX_SIGNAL_EV
from app.math.staking import capped_kelly_fraction
from app.services.league_gate import eligible_league_ids, get_eligibility_snapshot
from app.services.settings_service import load_quant_config

router = APIRouter(prefix="", tags=["Quant Alpha"])

# Display names for The Odds API bookmaker keys (scanner signal labels).
BOOKMAKER_LABELS = {
    "pinnacle": "Pinnacle",
    "betfair_ex_uk": "Betfair Exchange",
    "betfair": "Betfair",
    "bet365": "Bet365",
    "williamhill": "William Hill",
}


@router.get("/picks/daily")
@router.get("/alpha/picks")
async def get_daily_picks_endpoint(
    league_id: Optional[str] = Query(None, description="League filter (e.g. 'TOP5', 'EPL', 'NORDIC', 'ALL', or specific ID)"),
    days_ahead: int = Query(10, ge=1, le=30),
    lang: str = Query("zh", pattern="^(zh|en)$", description="Language: 'zh' for Chinese, 'en' for English"),
    user: User = Depends(require_analyst_user),
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
            selectinload(Match.odds_snapshots),
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

    query = query.order_by(Match.match_date.asc()).limit(250)
    matches = (await db.execute(query)).scalars().all()

    # PRD §2.1: only gate-approved leagues surface in picks and parlays.
    # eligible_league_ids is fail-closed (empty set, never None, when the
    # snapshot is missing), so status is derived from the snapshot itself.
    snapshot = await get_eligibility_snapshot(db)
    gate_enforced = bool(snapshot and isinstance(snapshot.get("leagues"), dict))
    eligible = await eligible_league_ids(db)
    gated_out = 0

    eligible_matches = []
    for match in matches:
        if match.league_id not in eligible:
            gated_out += 1
            continue
        pred = max(match.predictions, key=lambda item: item.as_of, default=None)
        if not pred:
            continue
        odds = latest_eligible_quote(match.odds_snapshots, pred.as_of)
        evaluation = evaluate_fixture_analysis(match, pred, odds, now)
        if evaluation["data_status"] == "AVAILABLE" and evaluation["prediction"]:
            eligible_matches.append(match)

    result = compile_daily_picks(eligible_matches, league_id=league_id, lang=lang)
    result["data_status"] = "AVAILABLE" if eligible_matches else "UNAVAILABLE"
    result["source"] = "eligible_prediction_snapshots"
    result["league_gate"] = "ENFORCED" if gate_enforced else "INACTIVE"
    result["gate_excluded_fixtures"] = gated_out
    return result



async def collect_value_signals(
    db: AsyncSession,
    *,
    min_ev: float,
    max_odds: float,
    bankroll: float,
    strategy: str,
    limit: int,
    kelly_fraction: float,
    max_stake_cap: float,
    league_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Eligible pre-kickoff 1X2 signals using the configured Kelly cap."""
    now = now or datetime.now(timezone.utc)
    end_date = now + timedelta(days=21)

    query = (
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.odds_snapshots),
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

    query = query.order_by(Match.match_date.asc()).limit(250)
    matches = (await db.execute(query)).scalars().all()

    # PRD §2.1 gate: pending leagues never produce scanner or push signals.
    # eligible_league_ids is fail-closed, so an empty set means the gate is
    # enforcing but nothing currently qualifies (never "allow everything").
    eligible = await eligible_league_ids(db)
    matches = [m for m in matches if m.league_id in eligible]

    signals: List[Dict[str, Any]] = []

    for m in matches:
        if not m.predictions:
            continue
        latest_pred = max(m.predictions, key=lambda p: p.as_of)
        odds = latest_eligible_quote(m.odds_snapshots, latest_pred.as_of)
        evaluation = evaluate_fixture_analysis(m, latest_pred, odds, now)
        if not evaluation["comparison"]:
            continue
        odds, _, _ = evaluation["comparison"]

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
            # Same ceiling as the curated picks: an EV above MAX_SIGNAL_EV is
            # treated as an uncalibrated tail anomaly, not an edge.
            if ev > MAX_SIGNAL_EV:
                continue

            b = o_dec - 1.0
            full_k = max(0.0, ev / b) if b > 0 else 0.0

            stake_frac = capped_kelly_fraction(full_k, strategy, kelly_fraction, max_stake_cap)

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
                "bookmaker": BOOKMAKER_LABELS.get(odds.bookmaker, odds.bookmaker.capitalize()),
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
                "prediction_as_of": latest_pred.as_of.isoformat(),
                "quote_at": odds.quote_at.isoformat(),
                "data_status": "AVAILABLE",
            })

    signals.sort(key=lambda s: s["ev"], reverse=True)
    return {
        "signals": signals[:limit],
        "total_signals_found": len(signals),
        "scanned_matches_count": len(matches),
    }


@router.get("/alpha/scanner")
async def get_alpha_scanner(
    league_id: Optional[str] = Query(None, description="League filter (e.g. 'TOP5', 'EPL', or None for all)"),
    min_ev: Optional[float] = Query(None, ge=0.01, le=1.0, description="Minimum unrounded EV threshold"),
    max_odds: float = Query(12.0, ge=1.01, le=50.0),
    bankroll: float = Query(1000.0, ge=10.0, le=10000000.0),
    strategy: str = Query("HALF_KELLY", pattern="^(FULL_KELLY|HALF_KELLY|QUARTER_KELLY|FIXED_1_PCT|FLAT_UNIT)$"),
    limit: int = Query(40, ge=1, le=100),
    user: User = Depends(require_analyst_user),
    db: AsyncSession = Depends(get_db),
):
    """Compares eligible pre-kickoff 1X2 quotes with stored model probability estimates."""
    quant = await load_quant_config(db)
    if min_ev is None:
        min_ev = float(quant["value_scanner_min_ev"])
    now = datetime.now(timezone.utc)
    found = await collect_value_signals(
        db,
        min_ev=min_ev,
        max_odds=max_odds,
        bankroll=bankroll,
        strategy=strategy,
        limit=limit,
        kelly_fraction=float(quant["kelly_fraction"]),
        max_stake_cap=float(quant["max_stake_cap"]),
        league_id=league_id,
        now=now,
    )
    gate_snapshot = await get_eligibility_snapshot(db)
    gate_enforced = bool(gate_snapshot and isinstance(gate_snapshot.get("leagues"), dict))
    return {
        "timestamp": now.isoformat(),
        "data_status": "AVAILABLE" if found["signals"] else "UNAVAILABLE",
        "freshness_window_hours": 13,
        "league_gate": "ENFORCED" if gate_enforced else "INACTIVE",
        "min_ev": min_ev,
        "max_signal_ev": MAX_SIGNAL_EV,
        "total_signals_found": found["total_signals_found"],
        "scanned_matches_count": found["scanned_matches_count"],
        "bankroll": bankroll,
        "strategy": strategy,
        "signals": found["signals"],
    }


@router.get("/analytics/backtest")
async def get_historical_backtest(
    initial_bankroll: float = Query(10000.0, ge=100.0),
    staking_strategy: str = Query("HALF_KELLY", pattern="^(FULL_KELLY|HALF_KELLY|QUARTER_KELLY|FIXED_1_PCT|FLAT_UNIT)$"),
    min_ev: float = Query(0.05, ge=0.01, le=0.50),
    max_ev: float = Query(0.40, ge=0.01, le=1.0),
    min_odds: float = Query(1.30, ge=1.01),
    max_odds: float = Query(7.00, le=30.0),
    league_id: Optional[str] = Query(None),
    dataset: str = Query("HISTORICAL_10Y"),
    years: int = Query(10, ge=1, le=12),
    user: User = Depends(require_analyst_user),
    db: AsyncSession = Depends(get_db),
):
    if min_ev > max_ev or min_odds > max_odds:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="Minimum filters must not exceed their maximums.",
        )
    quant = await load_quant_config(db)
    return await run_historical_backtest(
        db=db,
        initial_bankroll=initial_bankroll,
        staking_strategy=staking_strategy,
        min_ev=min_ev,
        max_ev=max_ev,
        min_odds=min_odds,
        max_odds=max_odds,
        league_filter=league_id,
        dataset=dataset,
        years=years,
        kelly_fraction=float(quant["kelly_fraction"]),
        max_stake_cap=float(quant["max_stake_cap"]),
    )


@router.post("/analytics/monte-carlo")
async def run_monte_carlo_simulation(
    bankroll: float = Query(10000.0, ge=100.0),
    kelly_fraction: Optional[float] = Query(None, ge=0.1, le=1.0),
    strategy: str = Query("HALF_KELLY", pattern="^(FULL_KELLY|HALF_KELLY|QUARTER_KELLY|FIXED_1_PCT|FLAT_UNIT)$"),
    avg_ev: float = Query(0.065, ge=0.01, le=0.25),
    avg_odds: float = Query(2.10, ge=1.2, le=5.0),
    num_bets: int = Query(100, ge=20, le=200),
    num_simulations: int = Query(1000, ge=100, le=1000),
    user: User = Depends(require_analyst_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate independent-bet scenarios from the supplied average assumptions."""
    await check_rate_limit(f"monte_carlo:{user.id}", limit=6, window_seconds=60)
    quant = await load_quant_config(db)
    if kelly_fraction is None:
        kelly_fraction = float(quant["kelly_fraction"])
    stake_cap = float(quant["max_stake_cap"])
    rng = random.Random()
    win_prob = (1.0 + avg_ev) / avg_odds
    if not 0.0 < win_prob < 1.0:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="avg_ev and avg_odds imply an invalid win probability.",
        )

    final_bankrolls = []
    trajectories = []  # Pick 10 sample paths for rendering

    ruin_count = 0
    double_count = 0

    for sim_idx in range(num_simulations):
        current_b = bankroll
        path = [round(current_b, 2)]
        ruined = False

        b = avg_odds - 1.0
        full_k = avg_ev / b if b > 0 else 0.0
        # Same staking math as the scanner/backtest: the named strategy is the
        # single source of truth, capped by the config ceiling.
        stake_pct = capped_kelly_fraction(full_k, strategy, kelly_fraction, stake_cap)

        for _ in range(num_bets):
            if current_b <= bankroll * 0.2:  # Ruin threshold at 80% loss
                ruined = True
                break

            stake = current_b * stake_pct
            if rng.random() < win_prob:
                current_b += stake * b
            else:
                current_b -= stake

            if sim_idx < 8:
                path.append(round(current_b, 2))

        final_bankrolls.append(current_b)
        ruin_count += int(ruined or current_b <= bankroll * 0.2)
        if current_b >= bankroll * 2.0:
            double_count += 1

        if sim_idx < 8:
            trajectories.append(path)

    final_bankrolls.sort()
    p5 = final_bankrolls[int(0.05 * len(final_bankrolls))]
    p50 = final_bankrolls[int(0.50 * len(final_bankrolls))]
    p95 = final_bankrolls[int(0.95 * len(final_bankrolls))]

    return {
        "simulation_only": True,
        "data_source": "USER_SUPPLIED_ASSUMPTIONS",
        "inputs": {
            "initial_bankroll": bankroll,
            "kelly_fraction": kelly_fraction,
            "staking_strategy": strategy,
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
