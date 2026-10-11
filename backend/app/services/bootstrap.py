import logging

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import AuditLog, User

logger = logging.getLogger(__name__)
_BOOTSTRAP_LOCK = 748219330154


async def ensure_initial_admin() -> None:
    """Promote or create the first administrator from the environment.

    Runs only while the database has zero admins. The password never leaves
    the server environment.
    """
    email = (settings.INITIAL_ADMIN_EMAIL or "").strip().lower()
    if not email:
        return

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _BOOTSTRAP_LOCK})
            admin_count = (
                await db.execute(select(func.count()).select_from(User).where(User.is_admin.is_(True)))
            ).scalar() or 0
            if admin_count > 0:
                await db.rollback()
                return

            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            created = False
            if user is None:
                password = settings.INITIAL_ADMIN_PASSWORD or ""
                if not password:
                    return
                user = User(
                    email=email,
                    password_hash=hash_password(password),
                    plan_tier="FREE",
                    is_admin=True,
                )
                db.add(user)
                created = True
            else:
                user.is_admin = True

            await db.commit()

            db.add(AuditLog(
                admin_email=email,
                action="BOOTSTRAP_ADMIN",
                target=email,
                details={"created": created},
            ))
            await db.commit()
    except (ProgrammingError, OperationalError, IntegrityError) as exc:
        # A missing schema, or a concurrent insert of the same email, must not crash startup.
        logger.warning("Initial admin bootstrap skipped: %s", type(exc).__name__)
