import uuid
import httpx
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, or_
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.config import settings
from app.models import League, Team, Match, TeamAlias, ModelParameter, User, AuditLog
from app.api.deps import require_admin_user
from app.services.net_guard import post_public_https, validate_public_https
from app.services.settings_service import (
    get_system_setting,
    save_system_setting,
    record_audit,
    get_recent_audit_logs,
    mask_secret,
    DEFAULT_QUANT_RISK,
    DEFAULT_DATA_PROVIDER,
    DEFAULT_MONETIZATION,
    DEFAULT_NOTIFICATIONS,
    load_provider_config,
)

router = APIRouter()


# ==========================================
# Pydantic Schemas
# ==========================================

def _strip_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


class CreateLeagueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=32, description="Unique league code, e.g. J_LEAGUE, MLS")
    name: str = Field(min_length=2, max_length=128, description="League full name, e.g. J1 League (日职联)")
    country: str = Field(min_length=2, max_length=64, description="Country or Region, e.g. Japan")
    active: bool = True

    @field_validator("id", "name", "country", mode="before")
    @classmethod
    def strip_fields(cls, value: Any) -> Any:
        return _strip_text(value)


class UpdateLeagueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    country: Optional[str] = Field(default=None, min_length=2, max_length=64)
    active: Optional[bool] = None

    @field_validator("name", "country", mode="before")
    @classmethod
    def strip_fields(cls, value: Any) -> Any:
        return _strip_text(value)


class CreateTeamRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=64, description="Unique slug ID, e.g. vissel-kobe")
    canonical_name: str = Field(min_length=2, max_length=128, description="Official team name, e.g. Vissel Kobe")
    country: str = Field(min_length=2, max_length=64, description="Country, e.g. Japan")

    @field_validator("id", "canonical_name", "country", mode="before")
    @classmethod
    def strip_fields(cls, value: Any) -> Any:
        return _strip_text(value)


class CreateAliasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str = Field(min_length=2, max_length=64, description="Target canonical team ID")
    external_name: str = Field(min_length=1, max_length=128, description="Alias text, e.g. 神户胜利船 or Vissel")
    source_name: Optional[str] = Field(default="MANUAL_ADMIN", max_length=32)
    country: Optional[str] = Field(default=None, max_length=64)

    @field_validator("team_id", "external_name", "source_name", "country", mode="before")
    @classmethod
    def strip_fields(cls, value: Any) -> Any:
        return _strip_text(value)


class QuantRiskConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_scanner_min_ev: float = Field(ge=0.01, le=0.30, default=0.05, description="Min +EV threshold (e.g. 0.05 = +5%)")
    kelly_fraction: float = Field(ge=0.1, le=1.0, default=0.5, description="Kelly fraction (0.5 = Half Kelly)")
    max_stake_cap: float = Field(ge=0.01, le=0.20, default=0.05, description="Maximum single bet stake cap")
    dixon_coles_decay_xi: float = Field(ge=0.0001, le=0.01, default=0.0018, description="Time decay rate xi per day")
    min_training_matches: int = Field(ge=10, le=500, default=60, description="Min matches required to fit Dixon-Coles")


class DataProviderConfigRequest(BaseModel):
    # extra="ignore" (not "forbid"): the admin UI loads GET /config/data-provider
    # — which includes the display-only `the_odds_api_key_masked` and
    # `is_key_configured` — and PUTs that same object back. Forbidding extras
    # here would reject every save from the current frontend. Tighten to
    # "forbid" once the frontend strips those keys before PUT.
    model_config = ConfigDict(extra="ignore")

    the_odds_api_key: Optional[str] = Field(default=None, description="The Odds API Key")
    sharp_bookmakers: List[str] = Field(default=["pinnacle", "betfair_ex_uk", "bet365", "williamhill"], description="Primary sharp bookmakers")
    polling_interval_hours: int = Field(ge=1, le=24, default=4, description="Hours between fixture odds pollings")
    live_monitoring_enabled: bool = Field(default=True, description="Enable automatic odds monitoring")


class MonetizationConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_price_usd: float = Field(ge=1.0, le=100.0, default=3.0, description="Entry-level 24h pass price")
    week_price_usd: float = Field(ge=1.0, le=200.0, default=9.0, description="Entry-level 7-day pass price")
    monthly_price_usd: float = Field(ge=1.0, le=1000.0, default=29.0, description="Analyst monthly subscription price")
    season_price_usd: float = Field(ge=1.0, le=5000.0, default=149.0, description="Analyst season subscription price")
    new_user_trial_days: int = Field(ge=0, le=30, default=3, description="Free trial days for newly registered users")
    accepted_tokens: List[str] = Field(default=["USDTTRC20", "USDTERC20", "USDC", "BTC"], description="Allowed crypto tokens")


class LeagueGateConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_finished_matches: int = Field(ge=50, le=5000, default=300, description="PRD §2.1 coverage floor")
    min_odds_coverage: float = Field(ge=0.05, le=1.0, default=0.40, description="Share of finished matches needing a pre-kickoff quote")
    min_eval_samples: int = Field(ge=10, le=1000, default=40, description="Stored-prediction evaluation samples required")
    max_brier_vs_market_ratio: float = Field(ge=1.0, le=2.0, default=1.05, description="Model Brier tolerance versus Shin market baseline")
    provisional_leagues: List[str] = Field(default=["EPL", "CHAMPIONSHIP"], description="Leagues covered by the frozen dataset backtest")

    @field_validator("provisional_leagues", mode="before")
    @classmethod
    def upper_codes(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [str(v).strip().upper() for v in value if str(v).strip()]
        return value


class NotificationsConfigRequest(BaseModel):
    # extra="ignore" (not "forbid"): the admin UI loads GET /config/notifications
    # — which includes the display-only `telegram_bot_token_masked` and
    # `webhook_url_masked` — and PUTs that same object back. Forbidding extras
    # would reject every save from the current frontend. Tighten to "forbid"
    # once the frontend strips those keys before PUT.
    model_config = ConfigDict(extra="ignore")

    telegram_enabled: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_channel_id: Optional[str] = None
    telegram_min_ev: float = Field(ge=0.01, le=0.30, default=0.08, description="EV threshold to trigger auto broadcast")
    webhook_url: Optional[str] = None
    webhook_enabled: bool = False


class NotificationTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str = Field(default="all", description="telegram | webhook | all")
    custom_message: Optional[str] = None


# ==========================================
# 1. League Management
# ==========================================

@router.get("/leagues")
async def list_all_leagues(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    leagues_stmt = select(League).order_by(League.name.asc())
    leagues = (await db.execute(leagues_stmt)).scalars().all()

    result = []
    for l in leagues:
        m_count_stmt = select(func.count(Match.id)).where(Match.league_id == l.id)
        m_count = (await db.execute(m_count_stmt)).scalar() or 0

        p_count_stmt = select(func.count(ModelParameter.id)).where(ModelParameter.league_id == l.id)
        p_count = (await db.execute(p_count_stmt)).scalar() or 0

        result.append({
            "id": l.id,
            "name": l.name,
            "country": l.country,
            "active": l.active,
            "matches_count": m_count,
            "has_model": p_count > 0,
        })

    return {"leagues": result}


@router.post("/leagues", status_code=status.HTTP_201_CREATED)
async def create_new_league(
    req: CreateLeagueRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    clean_id = req.id.strip().upper().replace(" ", "_")
    existing = await db.get(League, clean_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"League with ID '{clean_id}' already exists.",
        )

    league = League(
        id=clean_id,
        name=req.name.strip(),
        country=req.country.strip(),
        active=req.active,
    )
    db.add(league)
    await record_audit(
        db,
        admin_email=admin.email,
        action="CREATE_LEAGUE",
        target=league.id,
        details={"name": league.name, "country": league.country, "active": league.active},
    )
    await db.commit()
    await db.refresh(league)

    return {
        "status": "SUCCESS",
        "message": f"League '{league.name}' ({league.id}) created successfully.",
        "league": {
            "id": league.id,
            "name": league.name,
            "country": league.country,
            "active": league.active,
        },
    }


@router.patch("/leagues/{league_id}")
async def update_league(
    league_id: str,
    req: UpdateLeagueRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    league = await db.get(League, league_id.upper())
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found.")

    old_state = {"name": league.name, "country": league.country, "active": league.active}
    if req.name is not None:
        league.name = req.name.strip()
    if req.country is not None:
        league.country = req.country.strip()
    if req.active is not None:
        league.active = req.active

    await record_audit(
        db,
        admin_email=admin.email,
        action="UPDATE_LEAGUE",
        target=league.id,
        details={"old": old_state, "new": {"name": league.name, "country": league.country, "active": league.active}},
    )
    await db.commit()
    await db.refresh(league)

    return {
        "status": "SUCCESS",
        "message": f"League '{league.id}' updated.",
        "league": {
            "id": league.id,
            "name": league.name,
            "country": league.country,
            "active": league.active,
        },
    }


@router.delete("/leagues/{league_id}")
async def delete_league(
    league_id: str,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    league = (
        await db.execute(select(League).where(League.id == league_id.upper()).with_for_update())
    ).scalar_one_or_none()
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found.")

    m_count = (await db.execute(select(func.count(Match.id)).where(Match.league_id == league.id))).scalar() or 0
    if m_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete league '{league.id}' because it has {m_count} historical matches. Deactivate it instead.",
        )

    await db.execute(delete(ModelParameter).where(ModelParameter.league_id == league.id))
    await db.delete(league)
    try:
        await record_audit(
            db,
            admin_email=admin.email,
            action="DELETE_LEAGUE",
            target=league.id,
            details={"name": league.name},
        )
        await db.commit()
    except IntegrityError:
        # A concurrent import inserted a Match between the count and the
        # delete; surface it as a clear 409 instead of a 500. This can surface
        # at the audit flush/commit, so both are inside the guard.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete league '{league_id.upper()}' because it gained dependent records concurrently. Deactivate it instead.",
        )

    return {"status": "SUCCESS", "message": f"League '{league_id}' deleted successfully."}


# ==========================================
# 2. Team & Alias Management Hub
# ==========================================

@router.post("/teams", status_code=status.HTTP_201_CREATED)
async def create_new_team(
    req: CreateTeamRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    clean_id = req.id.strip().lower().replace(" ", "-")
    existing = await db.get(Team, clean_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Team with ID '{clean_id}' already exists.",
        )

    team = Team(
        id=clean_id,
        canonical_name=req.canonical_name.strip(),
        country=req.country.strip(),
    )
    db.add(team)
    await record_audit(
        db,
        admin_email=admin.email,
        action="CREATE_TEAM",
        target=team.id,
        details={"canonical_name": team.canonical_name, "country": team.country},
    )
    await db.commit()
    await db.refresh(team)

    return {
        "status": "SUCCESS",
        "message": f"Team '{team.canonical_name}' ({team.id}) registered successfully.",
        "team": {
            "id": team.id,
            "canonical_name": team.canonical_name,
            "country": team.country,
        },
    }


@router.get("/aliases")
async def list_aliases(
    search: Optional[str] = Query(None, description="Search alias or canonical team name"),
    team_id: Optional[str] = Query(None, description="Filter by canonical team ID"),
    limit: int = Query(200, ge=1, le=500),
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TeamAlias, Team.canonical_name, Team.country.label("team_country"))
        .join(Team, TeamAlias.team_id == Team.id)
        .order_by(TeamAlias.external_name.asc())
        .limit(limit)
    )
    count_stmt = select(func.count(TeamAlias.id)).select_from(TeamAlias).join(Team, TeamAlias.team_id == Team.id)

    if team_id:
        stmt = stmt.where(TeamAlias.team_id == team_id)
        count_stmt = count_stmt.where(TeamAlias.team_id == team_id)

    if search:
        term = f"%{search.strip()}%"
        search_filter = or_(
            TeamAlias.external_name.ilike(term),
            Team.canonical_name.ilike(term),
            TeamAlias.team_id.ilike(term),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    rows = (await db.execute(stmt)).all()
    aliases = []
    for alias, canonical_name, team_country in rows:
        aliases.append({
            "id": str(alias.id),
            "external_name": alias.external_name,
            "team_id": alias.team_id,
            "canonical_name": canonical_name,
            "source_name": alias.source_name,
            "country": alias.country or team_country,
        })

    total_aliases = (await db.execute(count_stmt)).scalar() or 0
    return {"total": total_aliases, "count": len(aliases), "aliases": aliases}


@router.post("/aliases", status_code=status.HTTP_201_CREATED)
async def create_alias(
    req: CreateAliasRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, req.team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target canonical team '{req.team_id}' not found.",
        )

    clean_name = req.external_name.strip()
    source = req.source_name or "MANUAL_ADMIN"
    country = req.country or team.country

    # Confirmed-name uniqueness matches uq_alias_confirmed_name (source, country, name).
    chk_stmt = select(TeamAlias).where(
        TeamAlias.source_name == source,
        TeamAlias.country == country,
        TeamAlias.external_name == clean_name,
        TeamAlias.external_id.is_(None),
    )
    existing = (await db.execute(chk_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alias '{clean_name}' for source '{source}' already exists, mapped to '{existing.team_id}'.",
        )

    alias = TeamAlias(
        source_name=source,
        external_name=clean_name,
        country=country,
        team_id=team.id,
    )
    db.add(alias)
    try:
        await record_audit(
            db,
            admin_email=admin.email,
            action="CREATE_ALIAS",
            target=clean_name,
            details={"team_id": team.id, "canonical_name": team.canonical_name, "source": source},
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alias '{clean_name}' for source '{source}' already exists.",
        )
    await db.commit()
    await db.refresh(alias)

    return {
        "status": "SUCCESS",
        "message": f"Alias '{clean_name}' successfully linked to '{team.canonical_name}'.",
        "alias": {
            "id": str(alias.id),
            "external_name": alias.external_name,
            "team_id": alias.team_id,
            "canonical_name": team.canonical_name,
            "source_name": alias.source_name,
            "country": alias.country,
        },
    }


@router.delete("/aliases/{alias_id}")
async def delete_alias(
    alias_id: str,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        alias_uuid = uuid.UUID(alias_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid alias UUID.")

    alias = await db.get(TeamAlias, alias_uuid)
    if not alias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found.")

    name = alias.external_name
    team_id = alias.team_id
    await db.delete(alias)
    await record_audit(
        db,
        admin_email=admin.email,
        action="DELETE_ALIAS",
        target=name,
        details={"team_id": team_id},
    )
    await db.commit()

    return {"status": "SUCCESS", "message": f"Alias '{name}' deleted successfully."}


# ==========================================
# 3. Dynamic Quant & Risk Settings
# ==========================================

@router.get("/config/quant-risk")
async def get_quant_risk_config(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await get_system_setting(db, "quant_risk", DEFAULT_QUANT_RISK)
    return {**DEFAULT_QUANT_RISK, **cfg}


@router.put("/config/quant-risk")
async def update_quant_risk_config(
    req: QuantRiskConfigRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    setting = await save_system_setting(
        db=db,
        key="quant_risk",
        value=req.model_dump(),
        admin_email=admin.email,
        description="全局量化模型超参数与凯利风控参数",
    )
    return {
        "status": "SUCCESS",
        "message": "量化风控参数已保存。扫描立即读取；训练、回测和赔率轮询在下一次任务中读取。",
        "config": setting.value,
    }


# ==========================================
# 4. Data Provider & Odds API Quota
# ==========================================

@router.get("/config/data-provider")
async def get_data_provider_config(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    full_cfg = await load_provider_config(db)
    key = full_cfg.get("the_odds_api_key") or ""
    return {
        "the_odds_api_key": "",
        "the_odds_api_key_masked": mask_secret(key),
        "is_key_configured": bool(key),
        "sharp_bookmakers": full_cfg.get("sharp_bookmakers") or DEFAULT_DATA_PROVIDER["sharp_bookmakers"],
        "polling_interval_hours": full_cfg.get("polling_interval_hours", 4),
        "live_monitoring_enabled": bool(full_cfg.get("live_monitoring_enabled", True)),
    }


@router.put("/config/data-provider")
async def update_data_provider_config(
    req: DataProviderConfigRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    curr = await get_system_setting(db, "data_provider", DEFAULT_DATA_PROVIDER)
    new_data = req.model_dump()
    # Keep existing key if not provided
    incoming_key = (new_data.get("the_odds_api_key") or "").strip()
    if not incoming_key or "****" in incoming_key:
        new_data["the_odds_api_key"] = curr.get("the_odds_api_key") or settings.THE_ODDS_API_KEY or ""

    setting = await save_system_setting(
        db=db,
        key="data_provider",
        value=new_data,
        admin_email=admin.email,
        description="实时行情源配置与轮询策略",
    )
    return {
        "status": "SUCCESS",
        "message": "行情数据源配置已更新。",
        "config": {
            **setting.value,
            "the_odds_api_key": "******" if setting.value.get("the_odds_api_key") else "",
        },
    }


@router.get("/provider/quota")
async def check_provider_quota(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Directly queries The Odds API for current live quota status.
    """
    cfg = await load_provider_config(db)
    api_key = cfg.get("the_odds_api_key") or settings.THE_ODDS_API_KEY

    if not api_key:
        return {
            "status": "NOT_CONFIGURED",
            "message": "尚未配置 The Odds API 密钥，请在上方录入有效 API Key。",
            "requests_remaining": None,
            "requests_used": None,
        }

    url = "https://api.the-odds-api.com/v4/sports"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params={"apiKey": api_key})
            if resp.status_code == 200:
                rem = resp.headers.get("x-requests-remaining")
                used = resp.headers.get("x-requests-used")
                return {
                    "status": "HEALTHY",
                    "message": "The Odds API 密钥有效，行情源通信正常。",
                    "requests_remaining": int(rem) if rem and rem.isdigit() else None,
                    "requests_used": int(used) if used and used.isdigit() else None,
                }
            elif resp.status_code == 401:
                return {
                    "status": "UNAUTHORIZED",
                    "message": "The Odds API 鉴权失败：提供的 API Key 无效或已过期。",
                    "requests_remaining": 0,
                    "requests_used": None,
                }
            elif resp.status_code == 429:
                return {
                    "status": "RATE_LIMITED",
                    "message": "本月 API 请求配额已耗尽 (Rate Limit Exceeded)。",
                    "requests_remaining": 0,
                    "requests_used": None,
                }
            else:
                return {
                    "status": "ERROR",
                    "message": f"API 返回非正常响应码 HTTP {resp.status_code}",
                    "requests_remaining": None,
                    "requests_used": None,
                }
        except Exception:
            return {
                "status": "OFFLINE",
                "message": "连接 The Odds API 服务器失败。",
                "requests_remaining": None,
                "requests_used": None,
            }


# ==========================================
# 5. Monetization & Pricing Policy
# ==========================================

@router.get("/config/monetization")
async def get_monetization_config(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await get_system_setting(db, "monetization", DEFAULT_MONETIZATION)
    return {**DEFAULT_MONETIZATION, **cfg}


@router.put("/config/monetization")
async def update_monetization_config(
    req: MonetizationConfigRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    setting = await save_system_setting(
        db=db,
        key="monetization",
        value=req.model_dump(),
        admin_email=admin.email,
        description="会员订阅定价与拉新试用期策略",
    )
    return {
        "status": "SUCCESS",
        "message": "商业化订阅定价与试用期策略已更新。",
        "config": setting.value,
    }


# ==========================================
# 5b. League Eligibility Gate (PRD §2.1)
# ==========================================

@router.get("/config/league-gate")
async def get_league_gate_config(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Gate thresholds plus the latest eligibility snapshot for inspection."""
    from app.services.league_gate import DEFAULT_LEAGUE_GATE, get_eligibility_snapshot, load_gate_config

    thresholds = await load_gate_config(db)
    snapshot = await get_eligibility_snapshot(db)
    return {
        "thresholds": thresholds,
        "defaults": DEFAULT_LEAGUE_GATE,
        "snapshot": snapshot or {"status": "NOT_COMPUTED"},
    }


@router.put("/config/league-gate")
async def update_league_gate_config(
    req: LeagueGateConfigRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    setting = await save_system_setting(
        db=db,
        key="league_gate",
        value=req.model_dump(),
        admin_email=admin.email,
        description="联赛解锁门槛阈值（PRD §2.1）",
    )
    return {"status": "SUCCESS", "config": setting.value}


@router.post("/league-gate/refresh")
async def refresh_league_gate(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Recompute the eligibility snapshot now instead of waiting for the daily beat run."""
    from app.services.league_gate import refresh_and_store_snapshot

    snapshot = await refresh_and_store_snapshot(db)
    await record_audit(
        db,
        admin_email=admin.email,
        action="REFRESH_LEAGUE_GATE",
        target="ALL",
        details={
            "computed_at": snapshot["computed_at"],
            "eligible": sorted(l for l, i in snapshot["leagues"].items() if i["eligible"]),
            "pending": sorted(l for l, i in snapshot["leagues"].items() if not i["eligible"]),
        },
    )
    await db.commit()
    return {"status": "SUCCESS", "snapshot": snapshot}


# ==========================================
# 6. Notifications & Webhook Integration
# ==========================================

@router.get("/config/notifications")
async def get_notifications_config(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await get_system_setting(db, "notifications", DEFAULT_NOTIFICATIONS)
    full_cfg = {**DEFAULT_NOTIFICATIONS, **cfg}
    tok = full_cfg.get("telegram_bot_token") or ""
    hook = full_cfg.get("webhook_url") or ""
    return {
        "telegram_enabled": bool(full_cfg.get("telegram_enabled")),
        "telegram_bot_token": "",
        "telegram_bot_token_masked": mask_secret(tok),
        "telegram_channel_id": full_cfg.get("telegram_channel_id") or "",
        "telegram_min_ev": full_cfg.get("telegram_min_ev", 0.08),
        "webhook_url": "",
        "webhook_url_masked": mask_secret(hook),
        "webhook_enabled": bool(full_cfg.get("webhook_enabled")),
    }


@router.put("/config/notifications")
async def update_notifications_config(
    req: NotificationsConfigRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    curr = await get_system_setting(db, "notifications", DEFAULT_NOTIFICATIONS)
    new_data = req.model_dump()
    incoming_token = (new_data.get("telegram_bot_token") or "").strip()
    if not incoming_token or "****" in incoming_token:
        new_data["telegram_bot_token"] = curr.get("telegram_bot_token") or ""
    incoming_hook = (new_data.get("webhook_url") or "").strip()
    if not incoming_hook or "****" in incoming_hook:
        new_data["webhook_url"] = curr.get("webhook_url") or ""
    elif new_data.get("webhook_url"):
        try:
            new_data["webhook_url"] = validate_public_https(new_data["webhook_url"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    setting = await save_system_setting(
        db=db,
        key="notifications",
        value=new_data,
        admin_email=admin.email,
        description="Telegram Bot 与 Webhook 告警推送配置",
    )
    return {
        "status": "SUCCESS",
        "message": "通知集成配置已保存。",
        "config": {
            **setting.value,
            "telegram_bot_token": "",
            "telegram_bot_token_masked": mask_secret(setting.value.get("telegram_bot_token") or ""),
            "webhook_url": "",
            "webhook_url_masked": mask_secret(setting.value.get("webhook_url") or ""),
        },
    }


@router.post("/notifications/test")
async def test_notifications(
    req: NotificationTestRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await get_system_setting(db, "notifications", DEFAULT_NOTIFICATIONS)
    results = {}
    test_msg = req.custom_message or "⚡ [MatchLambda 测试测试] 量化系统通知推送通道连通性测试成功！"

    # 1. Telegram test
    if req.channel in ("telegram", "all") and cfg.get("telegram_enabled"):
        token = cfg.get("telegram_bot_token")
        chat_id = cfg.get("telegram_channel_id")
        if not token or not chat_id:
            results["telegram"] = {"status": "FAILED", "detail": "Telegram Bot Token 或 Channel ID 未完整配置"}
        else:
            try:
                tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
                resp = await post_public_https(
                    tg_url,
                    {"chat_id": chat_id, "text": test_msg},
                )
                if 200 <= resp.status_code < 300:
                    results["telegram"] = {"status": "SUCCESS", "detail": "Telegram 测试消息已成功送达目标群组/频道"}
                else:
                    results["telegram"] = {"status": "FAILED", "detail": f"Telegram API 错误 HTTP {resp.status_code}"}
            except Exception as exc:
                results["telegram"] = {"status": "ERROR", "detail": f"Telegram 发送异常: {type(exc).__name__}"}
    elif req.channel in ("telegram", "all"):
        results["telegram"] = {"status": "SKIPPED", "detail": "Telegram 推送未开启"}

    # 2. Webhook test
    if req.channel in ("webhook", "all") and cfg.get("webhook_enabled"):
        webhook_url = cfg.get("webhook_url")
        if not webhook_url:
            results["webhook"] = {"status": "FAILED", "detail": "Webhook URL 未配置"}
        else:
            try:
                resp = await post_public_https(webhook_url, {
                    "event": "TEST_NOTIFICATION",
                    "message": test_msg,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                if 200 <= resp.status_code < 300:
                    results["webhook"] = {"status": "SUCCESS", "detail": f"Webhook 响应 HTTP {resp.status_code}"}
                else:
                    results["webhook"] = {"status": "FAILED", "detail": f"Webhook 响应 HTTP {resp.status_code}"}
            except Exception as exc:
                results["webhook"] = {"status": "ERROR", "detail": f"Webhook 请求异常: {type(exc).__name__}"}
    elif req.channel in ("webhook", "all"):
        results["webhook"] = {"status": "SKIPPED", "detail": "Webhook 推送未开启"}

    await record_audit(
        db,
        admin_email=admin.email,
        action="TEST_NOTIFICATION",
        target=req.channel,
        details={"results": results},
    )
    # record_audit flushes only; commit the audit row explicitly.
    await db.commit()

    return {"status": "COMPLETED", "results": results}


# ==========================================
# 7. Cache Management & Audit Logs
# ==========================================

@router.post("/cache/purge")
async def purge_cache(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    purged_count = 0
    purge_error = None
    client = None
    try:
        from redis import asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        for pattern in ("matchlambda:*", "picks:*", "odds:*"):
            async for key in client.scan_iter(match=pattern, count=200):
                purged_count += await client.delete(key)
    except Exception as exc:
        purge_error = type(exc).__name__
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass

    await record_audit(
        db,
        admin_email=admin.email,
        action="PURGE_CACHE",
        target="REDIS",
        details={"purged_keys_count": purged_count, "error": purge_error},
    )
    # record_audit flushes only; commit the audit row explicitly.
    await db.commit()

    if purge_error:
        return {
            "status": "ERROR",
            "message": "系统缓存清理失败。",
            "purged_keys": purged_count,
        }

    return {
        "status": "SUCCESS",
        "message": f"系统缓存清理完成，已清空 {purged_count} 个热点缓存键。",
        "purged_keys": purged_count,
    }


@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    logs = await get_recent_audit_logs(db, limit=limit)
    return {
        "count": len(logs),
        "logs": [
            {
                "id": str(log.id),
                "admin_email": log.admin_email,
                "action": log.action,
                "target": log.target,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


# ==========================================
# 8. System Overview
# ==========================================

@router.get("/system-info")
async def get_system_settings_info(
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    total_leagues = (await db.execute(select(func.count(League.id)))).scalar() or 0
    active_leagues = (await db.execute(select(func.count(League.id)).where(League.active == True))).scalar() or 0
    total_teams = (await db.execute(select(func.count(Team.id)))).scalar() or 0
    total_aliases = (await db.execute(select(func.count(TeamAlias.id)))).scalar() or 0
    total_matches = (await db.execute(select(func.count(Match.id)))).scalar() or 0

    quant_cfg = await get_system_setting(db, "quant_risk", DEFAULT_QUANT_RISK)
    quant_cfg = {**DEFAULT_QUANT_RISK, **quant_cfg}
    xi = float(quant_cfg.get("dixon_coles_decay_xi", 0.0018))
    half_life = round(0.693147 / xi, 1) if xi > 0 else 385.1
    provider_cfg = await load_provider_config(db)
    odds_key = provider_cfg.get("the_odds_api_key") or ""
    redis = urlparse(settings.REDIS_URL)

    return {
        "quant_model": {
            "model_type": "Time-Weighted Bivariate Poisson (Dixon-Coles)",
            "version": "1.3.0",
            "decay_rate_xi": xi,
            "half_life_days": half_life,
            "dejuice_method": "SHIN (with Multiplicative Fallback)",
            "kelly_fraction": quant_cfg.get("kelly_fraction", 0.5),
            "value_scanner_min_ev": quant_cfg.get("value_scanner_min_ev", 0.05),
            "max_stake_cap": quant_cfg.get("max_stake_cap", 0.05),
        },
        "database_metrics": {
            "total_leagues": total_leagues,
            "active_leagues": active_leagues,
            "total_teams": total_teams,
            "total_aliases": total_aliases,
            "total_matches": total_matches,
        },
        "integrations": {
            "the_odds_api": {
                "configured": bool(odds_key),
                "key_preview": mask_secret(odds_key) or "Not configured",
            },
            "nowpayments": {
                "configured": bool(settings.NOWPAYMENTS_API_KEY),
                "key_preview": mask_secret(settings.NOWPAYMENTS_API_KEY or "") or "Not configured",
            },
            "redis_broker": {
                "host": redis.hostname,
                "port": redis.port,
                "db": (redis.path or "").lstrip("/") or None,
            },
        },
    }
