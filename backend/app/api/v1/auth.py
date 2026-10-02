from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import AppException
from app.models import User
from app.schemas.auth import RegisterRequest, RegisterResponse, LoginRequest, TokenResponse, UserResponse
from app.api.deps import get_current_user, is_active_analyst

router = APIRouter(prefix="", tags=["Auth"])


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.email == req.email)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="EMAIL_EXISTS",
            message="Email already registered.",
        )

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        plan_tier="FREE",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return RegisterResponse(id=user.id, email=user.email)


@router.post("/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.email == req.email)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
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
    )
