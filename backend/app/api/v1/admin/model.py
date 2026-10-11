import logging

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models import League, Match, ModelParameter, Team, User
from app.api.deps import require_admin_user
from app.tasks.pipeline import train_league_task
from app.services.settings_service import record_audit

logger = logging.getLogger(__name__)

router = APIRouter()


class RetrainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    league_id: str = "EPL"
    refresh_predictions: bool = True


@router.get("/overview")
async def get_model_overview(
    league_id: Optional[str] = None,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns latest Dixon-Coles parameters, training metadata, and team attack/defense ratings.
    """
    stmt = select(League).where(League.active == True)
    if league_id:
        stmt = stmt.where(League.id == league_id)
    leagues = (await db.execute(stmt)).scalars().all()

    canonical_teams_stmt = select(Team)
    teams = (await db.execute(canonical_teams_stmt)).scalars().all()
    team_name_map = {t.id: t.canonical_name for t in teams}

    overview = []
    for l in leagues:
        param_stmt = (
            select(ModelParameter)
            .where(ModelParameter.league_id == l.id)
            .order_by(ModelParameter.calculated_at.desc())
        )
        param = (await db.execute(param_stmt)).scalars().first()

        match_count_stmt = select(func.count(Match.id)).where(
            Match.league_id == l.id,
            Match.status == "FINISHED",
        )
        completed_matches = (await db.execute(match_count_stmt)).scalar() or 0

        if not param:
            overview.append({
                "league_id": l.id,
                "league_name": l.name,
                "status": "NOT_TRAINED",
                "completed_matches": completed_matches,
                "latest_parameter": None,
                "team_ratings": [],
            })
            continue

        # Format team attack/defense
        attack_ratings = param.team_attack or {}
        defense_ratings = param.team_defense or {}

        team_rows = []
        for tid in set(list(attack_ratings.keys()) + list(defense_ratings.keys())):
            att = attack_ratings.get(tid, 0.0)
            defe = defense_ratings.get(tid, 0.0)
            team_rows.append({
                "team_id": tid,
                "team_name": team_name_map.get(tid, tid),
                "attack_alpha": round(att, 4),
                "defense_beta": round(defe, 4),
                "net_rating": round(att + defe, 4),
            })
        team_rows.sort(key=lambda t: t["attack_alpha"], reverse=True)

        overview.append({
            "league_id": l.id,
            "league_name": l.name,
            "status": "ACTIVE",
            "completed_matches": completed_matches,
            "latest_parameter": {
                "id": str(param.id),
                "model_version": param.model_version,
                "calculated_at": param.calculated_at.isoformat(),
                "training_cutoff": param.training_cutoff.isoformat(),
                "home_advantage_gamma": round(param.home_advantage, 4),
                "rho": round(param.rho, 5),
                "xi_decay": param.xi_decay,
                "training_data_ref": param.training_data_ref,
            },
            "team_ratings": team_rows,
        })

    return {"leagues": overview}


@router.post("/retrain")
async def retrain_model(
    req: RetrainRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers immediate refitting of Dixon-Coles model and refreshes upcoming fixture predictions.
    """
    league = await db.get(League, req.league_id)
    if not league:
        raise HTTPException(status_code=404, detail=f"League '{req.league_id}' not found.")

    try:
        async_result = train_league_task.delay(req.league_id, req.refresh_predictions)
    except Exception:
        logger.exception("Could not enqueue training for %s", req.league_id)
        raise HTTPException(status_code=503, detail="Training queue is unavailable.")

    await record_audit(
        db,
        admin_email=admin.email,
        action="RETRAIN_MODEL",
        target=req.league_id,
        details={
            "task_id": async_result.id,
            "refresh_predictions": req.refresh_predictions,
        },
    )
    # record_audit flushes only; commit the audit row explicitly.
    await db.commit()

    return {
        "status": "QUEUED",
        "league_id": req.league_id,
        "task_id": async_result.id,
        "refresh_predictions": req.refresh_predictions,
    }
