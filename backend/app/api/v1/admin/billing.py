import hashlib
import uuid
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, desc, text
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models import User, CryptoInvoice
from app.api.deps import require_admin_user
from app.services.settings_service import record_audit

router = APIRouter()


class UserAdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_tier: Optional[str] = None
    add_days: Optional[int] = Field(default=None, ge=-3650, le=3650)
    is_admin: Optional[bool] = None


def _advisory_key(namespace: str) -> int:
    """Stable 63-bit positive advisory-lock key distinct from other modules.

    A hashed namespace prefix keeps billing's locks from colliding with the
    bootstrap lock (services/bootstrap.py) or any other fixed key.
    """
    digest = hashlib.blake2b(namespace.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") >> 1


# Global lock kept only for the admin-demotion path so the "last admin" count
# check stays race-free. Subscription edits on different users run in parallel.
_LAST_ADMIN_LOCK = _advisory_key("matchlambda:admin:billing:last_admin")


def _user_lock_key(u_uuid: uuid.UUID) -> int:
    # Deterministic namespaced 63-bit positive bigint derived from the user
    # UUID (Python's hash() is salted per process and would not be safe across
    # workers).
    return _advisory_key(f"matchlambda:admin:billing:user:{u_uuid}")


@router.get("/invoices")
async def list_crypto_invoices(
    limit: int = Query(50, ge=1, le=500),
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists cryptocurrency payment invoices with associated user details and statuses.
    """
    stmt = (
        select(CryptoInvoice)
        .options(selectinload(CryptoInvoice.user))
        .order_by(desc(CryptoInvoice.created_at))
        .limit(limit)
    )
    invoices = (await db.execute(stmt)).scalars().all()

    return [
        {
            "id": str(inv.id),
            "order_id": inv.order_id,
            "user_id": str(inv.user_id),
            "user_email": inv.user.email if inv.user else "unknown",
            "amount_usd": float(inv.amount_usd),
            "plan_type": inv.plan_type,
            "duration_days": inv.duration_days,
            "payment_status": inv.payment_status,
            "gateway_status": inv.gateway_status,
            "gateway_invoice_id": inv.gateway_invoice_id,
            "gateway_payment_id": inv.gateway_payment_id,
            "checkout_url": inv.checkout_url,
            "credited_at": inv.credited_at.isoformat() if inv.credited_at else None,
            "created_at": inv.created_at.isoformat(),
        }
        for inv in invoices
    ]


@router.post("/invoices/{order_id}/grant")
async def manual_grant_invoice(
    order_id: str,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manual payment override: marks an invoice as PAID and grants Analyst pass to the user.
    Used for blockchain stuck transactions, underpaid/overpaid edge cases, or manual customer service.
    """
    stmt = select(CryptoInvoice).where(CryptoInvoice.order_id == order_id).with_for_update()
    inv = (await db.execute(stmt)).scalars().first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if inv.credited_at is not None:
        raise HTTPException(status_code=409, detail="Invoice already credited.")

    user_stmt = select(User).where(User.id == inv.user_id).with_for_update()
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Associated user not found.")

    now = datetime.now(timezone.utc)
    inv.payment_status = "PAID"
    inv.credited_at = now
    if not inv.gateway_invoice_id:
        inv.gateway_invoice_id = f"MANUAL_{uuid.uuid4().hex[:12]}"
    if not inv.gateway_payment_id:
        inv.gateway_payment_id = f"MANUAL_PAY_{uuid.uuid4().hex[:12]}"

    current_base = user.plan_expires_at if (user.plan_tier == "ANALYST" and user.plan_expires_at and user.plan_expires_at > now) else now
    new_expiry = current_base + timedelta(days=inv.duration_days)

    user.plan_tier = "ANALYST"
    user.plan_expires_at = new_expiry

    await record_audit(
        db,
        admin_email=admin.email,
        action="MANUAL_GRANT_INVOICE",
        target=inv.order_id,
        details={
            "user_email": user.email,
            "duration_days": inv.duration_days,
            "plan_expires_at": new_expiry.isoformat(),
        },
    )
    # The audit row now only flushes; commit here so the grant and its audit
    # entry land together. On failure the whole grant is rolled back.
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Could not persist the manual grant.")

    return {
        "status": "SUCCESS",
        "order_id": inv.order_id,
        "user_email": user.email,
        "plan_tier": user.plan_tier,
        "plan_expires_at": user.plan_expires_at.isoformat(),
    }


@router.get("/users")
async def list_users(
    limit: int = Query(100, ge=1, le=500),
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists users with current subscription tier, expiration, and admin status.
    """
    stmt = select(User).order_by(desc(User.created_at)).limit(limit)
    users = (await db.execute(stmt)).scalars().all()

    now = datetime.now(timezone.utc)
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "plan_tier": u.plan_tier,
            "is_active_analyst": bool(u.plan_tier == "ANALYST" and u.plan_expires_at and u.plan_expires_at > now),
            "plan_expires_at": u.plan_expires_at.isoformat() if u.plan_expires_at else None,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.post("/users/{user_id}/grant")
async def adjust_user_subscription(
    user_id: str,
    req: UserAdjustmentRequest,
    admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Directly adjusts a user's subscription, adds days, or toggles administrator privileges.
    """
    try:
        u_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user UUID.")

    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _user_lock_key(u_uuid)})
    user = (
        await db.execute(select(User).where(User.id == u_uuid).with_for_update())
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    now = datetime.now(timezone.utc)
    previous = {
        "plan_tier": user.plan_tier,
        "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "is_admin": user.is_admin,
    }

    if req.plan_tier:
        if req.plan_tier not in ("FREE", "ANALYST"):
            raise HTTPException(status_code=400, detail="Invalid plan tier. Must be FREE or ANALYST.")
        user.plan_tier = req.plan_tier
        if user.plan_tier == "ANALYST" and (user.plan_expires_at is None or user.plan_expires_at <= now):
            user.plan_expires_at = now + timedelta(days=30)
        elif user.plan_tier == "FREE":
            user.plan_expires_at = None

    if req.add_days and req.add_days > 0:
        base = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > now else now
        user.plan_expires_at = base + timedelta(days=req.add_days)
        user.plan_tier = "ANALYST"

    if req.is_admin is not None:
        if req.is_admin is False and user.is_admin:
            # Serialize concurrent demotions across all users before counting.
            await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LAST_ADMIN_LOCK})
            other_admins = (
                await db.execute(
                    select(func.count()).select_from(User).where(User.is_admin.is_(True), User.id != user.id)
                )
            ).scalar() or 0
            if other_admins < 1:
                raise HTTPException(status_code=409, detail="Cannot remove the last administrator.")
        user.is_admin = req.is_admin

    await record_audit(
        db,
        admin_email=admin.email,
        action="ADJUST_USER",
        target=str(user.id),
        details={
            "user_email": user.email,
            "old": previous,
            "new": {
                "plan_tier": user.plan_tier,
                "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
                "is_admin": user.is_admin,
            },
        },
    )
    # record_audit flushes only; commit so the adjustment and its audit row
    # are one atomic transaction.
    await db.commit()

    return {
        "status": "SUCCESS",
        "user_id": str(user.id),
        "email": user.email,
        "plan_tier": user.plan_tier,
        "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "is_admin": user.is_admin,
    }
