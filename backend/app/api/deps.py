import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.exceptions import AppException
from app.models import User


def is_active_analyst(user: User) -> bool:
    if user.plan_tier != "ANALYST" or not user.plan_expires_at:
        return False
    return user.plan_expires_at > datetime.now(timezone.utc)


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        # Optional auth: a bad header must not block anonymous routes.
        return None

    token = parts[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    user_id_str = payload["sub"]
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        return None

    return await db.get(User, user_uuid)


async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    if not user:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHENTICATED",
            message="Authentication required.",
        )
    return user


async def require_analyst_user(
    user: User = Depends(get_current_user),
) -> User:
    if not is_active_analyst(user):
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="PASS_REQUIRED",
            message="An active analyst pass is required.",
        )
    return user


async def require_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    if not getattr(user, "is_admin", False):
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="Administrator privileges required.",
        )
    return user
