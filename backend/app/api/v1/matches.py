import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import AppException
from app.models import Match, Team, Prediction, OddsSnapshot, ModelParameter, User
from app.schemas.fixture import (
    FixturesResponse, FixtureItem, TeamInfo,
    PredictionSummary, ComparisonSummary, OutcomeItem
)
from app.schemas.analysis import (
    MatchAnalysisResponse, PredictionDetail, ComparisonDetail, TopScoreItem
)
from app.api.deps import get_current_user_optional, require_analyst_user, is_active_analyst
from app.math.ev import calculate_ev, calculate_half_kelly, has_value_signal

router = APIRouter(prefix="/matches", tags=["Matches"])

SUPPORTED_LEAGUES = {"EPL", "LA_LIGA", "SERIE_A", "BUNDESLIGA", "LIGUE_1"}


@router.get("/leagues")
async def get_leagues(db: AsyncSession = Depends(get_db)):
    """
    Returns list of all active European leagues supported by the engine.
    """
    from app.models import League
    stmt = select(League).where(League.active == True)
    leagues = (await db.execute(stmt)).scalars().all()
    return [
        {"id": l.id, "name": l.name, "country": l.country}
        for l in leagues
    ]


def build_outcomes(pred: Prediction, odds: OddsSnapshot) -> Tuple[List[OutcomeItem], bool]:
    # HOME, DRAW, AWAY in exact order
    h_ev = calculate_ev(pred.prob_home_win, float(odds.home_odds))
    d_ev = calculate_ev(pred.prob_draw, float(odds.draw_odds))
    a_ev = calculate_ev(pred.prob_away_win, float(odds.away_odds))

    h_hk = calculate_half_kelly(pred.prob_home_win, float(odds.home_odds))
    d_hk = calculate_half_kelly(pred.prob_draw, float(odds.draw_odds))
    a_hk = calculate_half_kelly(pred.prob_away_win, float(odds.away_odds))

    outcomes = [
        OutcomeItem(
            outcome="HOME",
            model_prob=pred.prob_home_win,
            market_prob=odds.implied_prob_home,
            odds=float(odds.home_odds),
            ev=h_ev,
            half_kelly=h_hk,
        ),
        OutcomeItem(
            outcome="DRAW",
            model_prob=pred.prob_draw,
            market_prob=odds.implied_prob_draw,
            odds=float(odds.draw_odds),
            ev=d_ev,
            half_kelly=d_hk,
        ),
        OutcomeItem(
            outcome="AWAY",
            model_prob=pred.prob_away_win,
            market_prob=odds.implied_prob_away,
            odds=float(odds.away_odds),
            ev=a_ev,
            half_kelly=a_hk,
        ),
    ]
    has_val = any(has_value_signal(item.ev) for item in outcomes)
    return outcomes, has_val


def evaluate_fixture_analysis(
    match: Match,
    pred: Optional[Prediction],
    odds: Optional[OddsSnapshot],
    now: datetime,
) -> Dict[str, Any]:
    """
    Evaluates freshness and returns (data_status, reason, pred_summary, comp_summary, full_pred, full_comp)
    """
    if not pred:
        return {
            "data_status": "UNAVAILABLE",
            "reason": "NO_PREDICTION",
            "prediction": None,
            "comparison": None,
            "has_value": False,
        }

    # Stale checks
    if match.status != "SCHEDULED":
        return {
            "data_status": "STALE",
            "reason": "MATCH_NOT_SCHEDULED",
            "prediction": pred,
            "comparison": None,
            "has_value": False,
        }

    if match.match_date != pred.kickoff_at_prediction:
        return {
            "data_status": "STALE",
            "reason": "FIXTURE_CHANGED",
            "prediction": pred,
            "comparison": None,
            "has_value": False,
        }

    pred_age = (now - pred.as_of).total_seconds() / 3600.0
    if pred_age > 13.0:
        return {
            "data_status": "STALE",
            "reason": "STALE_PREDICTION",
            "prediction": pred,
            "comparison": None,
            "has_value": False,
        }

    # Prediction is AVAILABLE
    if not odds:
        return {
            "data_status": "AVAILABLE",
            "reason": "MISSING_QUOTE",
            "prediction": pred,
            "comparison": None,
            "has_value": False,
        }

    # Check quote freshness
    quote_age = (now - odds.quote_at).total_seconds() / 3600.0
    if quote_age > 13.0 or not (odds.quote_at <= odds.recorded_at <= pred.as_of):
        return {
            "data_status": "AVAILABLE",
            "reason": "STALE_QUOTE",
            "prediction": pred,
            "comparison": None,
            "has_value": False,
        }

    # Both current and eligible
    outcomes, has_val = build_outcomes(pred, odds)
    return {
        "data_status": "AVAILABLE",
        "reason": None,
        "prediction": pred,
        "comparison": (odds, outcomes, has_val),
        "has_value": has_val,
    }


@router.get("/fixtures", response_model=FixturesResponse)
async def get_fixtures(
    league_id: Optional[str] = Query(None),
    days_ahead: int = Query(3, ge=1, le=7),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    has_value: Optional[bool] = Query(None),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    if league_id is not None:
        from app.models import League
        stmt_chk = select(League.id).where(League.id == league_id, League.active == True)
        valid_league = (await db.execute(stmt_chk)).scalar_one_or_none()
        if not valid_league:
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="VALIDATION_ERROR",
                message=f"Unsupported league_id '{league_id}'.",
            )

    # Check has_value filter access
    if has_value is not None:
        if not user:
            raise AppException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="UNAUTHENTICATED",
                message="Authentication required to filter by has_value.",
            )
        if not is_active_analyst(user):
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="PASS_REQUIRED",
                message="An active analyst pass is required to filter by has_value.",
            )

    is_analyst = user is not None and is_active_analyst(user)
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days_ahead)

    # Base query for scheduled matches
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

    if league_id:
        query = query.where(Match.league_id == league_id)

    query = query.order_by(Match.match_date.asc(), Match.id.asc())

    all_matches = (await db.execute(query)).scalars().all()

    # Process fixtures
    evaluated_items = []
    for m in all_matches:
        # Latest prediction by as_of
        latest_pred = None
        if m.predictions:
            latest_pred = max(m.predictions, key=lambda p: p.as_of)

        odds_snap = latest_pred.odds_snapshot if latest_pred else None

        eval_res = evaluate_fixture_analysis(m, latest_pred, odds_snap, now)

        # Apply has_value filter if requested
        if has_value is not None:
            if eval_res["has_value"] != has_value:
                continue

        base_item = {
            "match_id": m.id,
            "league_id": m.league_id,
            "match_date": m.match_date,
            "home_team": TeamInfo(id=m.home_team.id, name=m.home_team.canonical_name),
            "away_team": TeamInfo(id=m.away_team.id, name=m.away_team.canonical_name),
            "status": m.status,
        }

        if is_analyst:
            pred_summary = None
            if eval_res["prediction"]:
                p = eval_res["prediction"]
                pred_summary = PredictionSummary(
                    id=p.id,
                    as_of=p.as_of,
                    lambda_home=p.lambda_home,
                    mu_away=p.mu_away,
                    prob_home_win=p.prob_home_win,
                    prob_draw=p.prob_draw,
                    prob_away_win=p.prob_away_win,
                )

            comp_summary = None
            if eval_res["comparison"]:
                odds_obj, outcomes, has_val = eval_res["comparison"]
                comp_summary = ComparisonSummary(
                    odds_snapshot_id=odds_obj.id,
                    bookmaker=odds_obj.bookmaker,
                    quote_at=odds_obj.quote_at,
                    has_value=has_val,
                    outcomes=outcomes,
                )

            item = FixtureItem(
                **base_item,
                data_status=eval_res["data_status"],
                reason=eval_res["reason"],
                prediction=pred_summary,
                comparison=comp_summary,
            )
        else:
            # Anonymous or free user receives strictly base fields
            item = FixtureItem(**base_item)

        evaluated_items.append(item)

    total = len(evaluated_items)
    page_items = evaluated_items[offset : offset + limit]

    return FixturesResponse(
        total=total,
        limit=limit,
        offset=offset,
        fixtures=page_items,
    )


@router.get("/{match_id}/analysis", response_model=MatchAnalysisResponse)
async def get_match_analysis(
    match_id: str,
    user: User = Depends(require_analyst_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Match)
        .options(
            selectinload(Match.predictions).selectinload(Prediction.odds_snapshot),
            selectinload(Match.predictions).selectinload(Prediction.model_parameters),
        )
        .where(Match.id == match_id)
    )
    match = (await db.execute(query)).scalars().first()
    if not match:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Match '{match_id}' not found.",
        )

    now = datetime.now(timezone.utc)
    latest_pred = None
    if match.predictions:
        latest_pred = max(match.predictions, key=lambda p: p.as_of)

    odds_snap = latest_pred.odds_snapshot if latest_pred else None
    eval_res = evaluate_fixture_analysis(match, latest_pred, odds_snap, now)

    pred_detail = None
    if eval_res["prediction"]:
        p = eval_res["prediction"]
        pred_detail = PredictionDetail(
            id=p.id,
            model_parameters_id=p.model_parameters_id,
            model_version=p.model_parameters.model_version,
            training_cutoff=p.model_parameters.training_cutoff,
            as_of=p.as_of,
            generated_at=p.generated_at,
            kickoff_at_prediction=p.kickoff_at_prediction,
            lambda_home=p.lambda_home,
            mu_away=p.mu_away,
            rho=p.model_parameters.rho,
            prob_home_win=p.prob_home_win,
            prob_draw=p.prob_draw,
            prob_away_win=p.prob_away_win,
            score_matrix=p.score_matrix,
            omitted_mass=p.omitted_mass,
            top_scores=[TopScoreItem(**ts) for ts in p.top_scores],
        )

    comp_detail = None
    if eval_res["comparison"]:
        odds_obj, outcomes, has_val = eval_res["comparison"]
        # Overround as fraction S - 1
        overround = (1.0 / float(odds_obj.home_odds)) + (1.0 / float(odds_obj.draw_odds)) + (1.0 / float(odds_obj.away_odds)) - 1.0
        comp_detail = ComparisonDetail(
            odds_snapshot_id=odds_obj.id,
            source_name=odds_obj.source_name,
            bookmaker=odds_obj.bookmaker,
            quote_at=odds_obj.quote_at,
            recorded_at=odds_obj.recorded_at,
            dejuice_method=odds_obj.dejuice_method,
            overround=overround,
            has_value=has_val,
            outcomes=outcomes,
        )

    return MatchAnalysisResponse(
        match_id=match.id,
        data_status=eval_res["data_status"],
        reason=eval_res["reason"],
        prediction=pred_detail,
        comparison=comp_detail,
    )
