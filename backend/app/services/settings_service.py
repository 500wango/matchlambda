from datetime import datetime, timezone
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models import SystemSetting, AuditLog

logger = logging.getLogger(__name__)


DEFAULT_QUANT_RISK = {
    "value_scanner_min_ev": 0.05,
    "kelly_fraction": 0.5,
    "max_stake_cap": 0.05,
    "dixon_coles_decay_xi": 0.0018,
    "min_training_matches": 60,
}

DEFAULT_DATA_PROVIDER = {
    "the_odds_api_key": "",
    "sharp_bookmakers": ["pinnacle", "betfair_ex_uk", "bet365", "williamhill"],
    "polling_interval_hours": 4,
    "live_monitoring_enabled": True,
}

DEFAULT_MONETIZATION = {
    "day_price_usd": 3.0,
    "week_price_usd": 9.0,
    "monthly_price_usd": 29.0,
    "season_price_usd": 149.0,
    "new_user_trial_days": 3,
    "accepted_tokens": ["USDTTRC20", "USDTERC20", "USDC", "BTC"],
}

DEFAULT_NOTIFICATIONS = {
    "telegram_enabled": False,
    "telegram_bot_token": "",
    "telegram_channel_id": "",
    "telegram_min_ev": 0.08,
    "webhook_url": "",
    "webhook_enabled": False,
}

SECRET_FIELDS = {"the_odds_api_key", "telegram_bot_token", "webhook_url"}

# Keys whose stored value must match the shape of a known default config. Keeping
# this registry lets the write path reject a malformed config before it poisons
# every later read (see load_* helpers).
KNOWN_SETTING_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "quant_risk": DEFAULT_QUANT_RISK,
    "data_provider": DEFAULT_DATA_PROVIDER,
    "monetization": DEFAULT_MONETIZATION,
    "notifications": DEFAULT_NOTIFICATIONS,
}


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) >= 8:
        return f"{value[:4]}****{value[-4:]}"
    return "Configured"


def redact_secrets(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, dict):
        redacted = {}
        for key, value in payload.items():
            if key in SECRET_FIELDS and isinstance(value, str) and value:
                redacted[key] = mask_secret(value)
            else:
                redacted[key] = redact_secrets(value)
        return redacted
    if isinstance(payload, list):
        return [redact_secrets(item) for item in payload]
    return payload


def _missing_settings_table(exc: Exception) -> bool:
    message = str(exc).lower()
    missing = "does not exist" in message or "undefinedtable" in message
    return "system_settings" in message and missing


def _coerce_value(sample: Any, raw: Any, key: str) -> Any:
    if isinstance(sample, bool):
        if not isinstance(raw, bool):
            raise ValueError(f"{key} must be a boolean.")
        return raw
    if isinstance(sample, int) and not isinstance(sample, bool):
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"{key} must be an integer.")
        return int(raw)
    if isinstance(sample, float):
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"{key} must be a number.")
        return float(raw)
    if isinstance(sample, str):
        if not isinstance(raw, str):
            raise ValueError(f"{key} must be a string.")
        return raw
    if isinstance(sample, list):
        if not isinstance(raw, list):
            raise ValueError(f"{key} must be a list.")
        return list(raw)
    return raw


def _coerce_config(default: Dict[str, Any], stored: Any) -> Dict[str, Any]:
    if stored is None:
        return dict(default)
    if not isinstance(stored, dict):
        raise ValueError("Stored setting must be a JSON object.")
    merged = dict(default)
    for key, sample in default.items():
        if key not in stored:
            continue
        merged[key] = _coerce_value(sample, stored[key], key)
    return merged


def validate_setting_value(key: str, value: Any) -> Any:
    """Reject structurally invalid config before it is written.

    Known config keys are validated against their default shape (types and
    container kinds) so a typo cannot poison every later read; unknown keys
    (operational state such as ``ops_state``) only need to be a JSON object.
    Returns ``value`` unchanged on success and raises ``ValueError`` otherwise.
    """
    if not isinstance(value, dict):
        raise ValueError("Setting value must be a JSON object.")
    default = KNOWN_SETTING_DEFAULTS.get(key)
    if default is not None:
        # Raises ValueError with a per-field message on a wrong type/shape.
        _coerce_config(default, value)
    return value


async def get_system_setting(
    db: AsyncSession,
    key: str,
    default: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        setting = (await db.execute(stmt)).scalar_one_or_none()
    except (ProgrammingError, OperationalError) as exc:
        await db.rollback()
        if _missing_settings_table(exc):
            return default or {}
        raise
    if setting is None:
        return default or {}
    if not isinstance(setting.value, dict):
        raise ValueError(f"Setting '{key}' must be a JSON object.")
    return setting.value


async def load_quant_config(db: AsyncSession) -> Dict[str, Any]:
    try:
        stored = await get_system_setting(db, "quant_risk", DEFAULT_QUANT_RISK)
        return _coerce_config(DEFAULT_QUANT_RISK, stored)
    except ValueError as exc:
        logger.error("quant_risk config is invalid (%s); falling back to defaults", exc)
        return dict(DEFAULT_QUANT_RISK)


async def load_provider_config(db: AsyncSession) -> Dict[str, Any]:
    try:
        stored = await get_system_setting(db, "data_provider", DEFAULT_DATA_PROVIDER)
        merged = _coerce_config(DEFAULT_DATA_PROVIDER, stored)
    except ValueError as exc:
        logger.error("data_provider config is invalid (%s); falling back to defaults", exc)
        merged = dict(DEFAULT_DATA_PROVIDER)
    if not merged.get("the_odds_api_key"):
        merged["the_odds_api_key"] = settings.THE_ODDS_API_KEY or ""
    return merged


async def load_monetization_config(db: AsyncSession) -> Dict[str, Any]:
    try:
        stored = await get_system_setting(db, "monetization", DEFAULT_MONETIZATION)
        return _coerce_config(DEFAULT_MONETIZATION, stored)
    except ValueError as exc:
        logger.error("monetization config is invalid (%s); falling back to defaults", exc)
        return dict(DEFAULT_MONETIZATION)


async def load_notification_config(db: AsyncSession) -> Dict[str, Any]:
    try:
        stored = await get_system_setting(db, "notifications", DEFAULT_NOTIFICATIONS)
        return _coerce_config(DEFAULT_NOTIFICATIONS, stored)
    except ValueError as exc:
        logger.error("notifications config is invalid (%s); falling back to defaults", exc)
        return dict(DEFAULT_NOTIFICATIONS)


async def upsert_system_setting(
    db: AsyncSession,
    key: str,
    value: Dict[str, Any],
    description: Optional[str] = None,
) -> None:
    """Persist operational state that is not an admin secret and is not audited."""
    validate_setting_value(key, value)
    try:
        stmt = select(SystemSetting).where(SystemSetting.key == key).with_for_update()
        setting = (await db.execute(stmt)).scalar_one_or_none()
        if setting:
            setting.value = value
            setting.updated_at = datetime.now(timezone.utc)
        else:
            db.add(SystemSetting(
                key=key,
                value=value,
                description=description,
                updated_at=datetime.now(timezone.utc),
            ))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        stmt = select(SystemSetting).where(SystemSetting.key == key).with_for_update()
        setting = (await db.execute(stmt)).scalar_one_or_none()
        if setting is None:
            raise
        setting.value = value
        setting.updated_at = datetime.now(timezone.utc)
        await db.commit()
    except (ProgrammingError, OperationalError) as exc:
        await db.rollback()
        if _missing_settings_table(exc):
            return
        raise


async def save_system_setting(
    db: AsyncSession,
    key: str,
    value: Dict[str, Any],
    admin_email: str,
    description: Optional[str] = None,
) -> SystemSetting:
    validate_setting_value(key, value)
    # Retry once on the first-insert race: two admins creating the same key at
    # the same moment both see "no row" and one INSERT loses on the PK. The
    # loser re-reads under a row lock and updates instead of raising a 500.
    for attempt in range(2):
        stmt = select(SystemSetting).where(SystemSetting.key == key).with_for_update()
        setting = (await db.execute(stmt)).scalar_one_or_none()
        old_value = None
        if setting:
            old_value = setting.value
            setting.value = value
            if description:
                setting.description = description
            setting.updated_at = datetime.now(timezone.utc)
        else:
            setting = SystemSetting(
                key=key,
                value=value,
                description=description,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(setting)

        audit = AuditLog(
            admin_email=admin_email,
            action="UPDATE_SETTING",
            target=key,
            details={
                "old": redact_secrets(old_value),
                "new": redact_secrets(value),
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            if attempt == 1:
                raise
            continue
        await db.refresh(setting)
        return setting
    raise RuntimeError("unreachable")  # pragma: no cover


async def record_audit(
    db: AsyncSession,
    admin_email: str,
    action: str,
    target: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> AuditLog:
    """Stage an audit row on the caller's transaction.

    By default this only ``flush()``es so the audit entry commits atomically
    with whatever the admin action wrote; the caller owns the transaction
    boundary and must ``await db.commit()``. Pass ``commit=True`` only when the
    caller has nothing else staged and wants this row persisted immediately.
    """
    audit = AuditLog(
        admin_email=admin_email,
        action=action,
        target=target,
        details=redact_secrets(details or {}),
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    if commit:
        await db.commit()
    else:
        await db.flush()
    await db.refresh(audit)
    return audit


async def get_recent_audit_logs(
    db: AsyncSession,
    limit: int = 50,
) -> List[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    logs = list((await db.execute(stmt)).scalars().all())
    for log in logs:
        log.details = redact_secrets(log.details)
    return logs
