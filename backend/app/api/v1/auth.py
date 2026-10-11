import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    password_needs_rehash,
    create_access_token,
    ph,
)
from app.core.exceptions import AppException
from app.core.rate_limiter import check_rate_limit, consume_rate_limit, client_address
from app.models import User
from app.schemas.auth import RegisterRequest, RegisterResponse, LoginRequest, TokenResponse, UserResponse
from app.api.deps import get_current_user, is_active_analyst

logger = logging.getLogger("matchlambda")

router = APIRouter(prefix="", tags=["Auth"])

# Verified on every missing-user login so the response time does not reveal whether the email exists.
_DUMMY_PASSWORD_HASH = ph.hash("matchlambda-timing-equalizer")


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = client_address(request)
    await check_rate_limit(f"register:{client_ip}", limit=10, window_seconds=60)

    stmt = select(User).where(User.email == req.email)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="EMAIL_EXISTS",
            message="Email already registered.",
        )

    from app.services.settings_service import load_monetization_config
    from datetime import datetime, timezone, timedelta

    mon_cfg = await load_monetization_config(db)
    trial_days = int(mon_cfg.get("new_user_trial_days", 3))

    # Anti-abuse: cap the free trial grants per client IP per day. Over-quota
    # registrations still succeed, they simply start on the FREE tier.
    trial_granted = trial_days > 0
    if trial_granted and settings.TRIAL_MAX_PER_IP_PER_DAY > 0:
        allowed = await consume_rate_limit(
            f"trial_grant:{client_ip}",
            limit=settings.TRIAL_MAX_PER_IP_PER_DAY,
            window_seconds=86400,
        )
        if not allowed:
            trial_granted = False
            logger.warning(
                "Withheld free trial for new account from %s: daily trial limit "
                "(%d) exceeded.",
                client_ip,
                settings.TRIAL_MAX_PER_IP_PER_DAY,
            )

    plan_tier = "ANALYST" if trial_granted else "FREE"
    plan_expires_at = (datetime.now(timezone.utc) + timedelta(days=trial_days)) if trial_granted else None

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        plan_tier=plan_tier,
        plan_expires_at=plan_expires_at,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="EMAIL_EXISTS",
            message="Email already registered.",
        )
    await db.refresh(user)

    return RegisterResponse(id=user.id, email=user.email)


@router.post("/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = client_address(request)
    await check_rate_limit(f"login:{client_ip}", limit=10, window_seconds=60)

    stmt = select(User).where(User.email == req.email)
    user = (await db.execute(stmt)).scalar_one_or_none()
    # Always run argon2 so a missing account is not faster than a wrong password.
    if user is None:
        verify_password(req.password, _DUMMY_PASSWORD_HASH)
        authenticated = False
    else:
        authenticated = verify_password(req.password, user.password_hash)
        if authenticated and password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(req.password)
            await db.commit()
    if not authenticated:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHENTICATED",
            message="Invalid credentials.",
        )

    token, expires_in = create_access_token(str(user.id))
    return TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in)


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(user: User = Depends(get_current_user)):
    effective = "ANALYST" if is_active_analyst(user) else "FREE"
    return UserResponse(
        id=user.id,
        email=user.email,
        effective_plan=effective,
        plan_expires_at=user.plan_expires_at,
        is_admin=getattr(user, "is_admin", False),
    )
