import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Set

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import SystemSetting
from app.services.net_guard import post_public_https
from app.services.settings_service import (
    get_system_setting,
    load_notification_config,
    load_quant_config,
    upsert_system_setting,
)

logger = logging.getLogger(__name__)
_SENT_CAP = 5000

# A pending claim older than this is assumed to belong to a crashed dispatcher
# and may be re-claimed, so a crash cannot permanently suppress a signal.
_PENDING_STALE_SECONDS = 900


def _format_alerts(signals: List[Dict[str, Any]]) -> str:
    lines = ["MatchLambda value alerts"]
    for signal in signals:
        lines.append(
            f"{signal['home_team']} vs {signal['away_team']} {signal['selection']} "
            f"@ {signal['market_odds']} EV {signal['ev_pct']}%"
        )
    return "\n".join(lines)


def _id_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item]


def _cap(ids: Iterable[str], limit: int = _SENT_CAP) -> List[str]:
    kept: List[str] = []
    seen: Set[str] = set()
    for item in reversed(list(ids)):
        if item in seen:
            continue
        seen.add(item)
        kept.append(item)
        if len(kept) >= limit:
            break
    kept.reverse()
    return kept


def _pending_is_stale(raw: Any) -> bool:
    if not raw:
        return True
    try:
        claimed_dt = datetime.fromisoformat(str(raw))
    except ValueError:
        return True
    if claimed_dt.tzinfo is None:
        claimed_dt = claimed_dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - claimed_dt).total_seconds() > _PENDING_STALE_SECONDS


async def _load_state_locked(session) -> Dict[str, Any]:
    stmt = select(SystemSetting).where(SystemSetting.key == "notification_state").with_for_update()
    row = (await session.execute(stmt)).scalar_one_or_none()
    return dict(row.value) if row is not None and isinstance(row.value, dict) else {}


async def _claim_signals(channel: str, ids: List[str]) -> List[str]:
    """Atomically reserve signal ids for this dispatcher before sending.

    Reserving under a row lock means two concurrent dispatches cannot both push
    the same signal: the loser sees the ids already pending and claims nothing.
    Returns the subset of ``ids`` this caller now owns.
    """
    if not ids:
        return []
    sent_key = f"sent_{channel}"
    pending_key = f"sent_{channel}_pending"
    claimed: List[str] = []
    async with AsyncSessionLocal() as session:
        current = await _load_state_locked(session)
        legacy = set(_id_list(current.get("sent")))
        sent = set(_id_list(current.get(sent_key))) | legacy
        pending_meta = current.get("pending_at") if isinstance(current.get("pending_at"), dict) else {}
        pending = set(_id_list(current.get(pending_key)))
        if pending and _pending_is_stale(pending_meta.get(channel)):
            # Previous claimant likely crashed mid-send; let these be retried.
            pending = set()
        for signal_id in ids:
            if signal_id not in sent and signal_id not in pending:
                pending.add(signal_id)
                claimed.append(signal_id)
        if not claimed:
            return []
        newval = dict(current)
        newval[pending_key] = _cap(pending)
        pending_meta = dict(pending_meta)
        pending_meta[channel] = datetime.now(timezone.utc).isoformat()
        newval["pending_at"] = pending_meta
        await upsert_system_setting(
            session,
            "notification_state",
            newval,
            "Identifiers of value signals already pushed, per channel",
        )
    return claimed


async def _finalize_signals(channel: str, ids: List[str], delivered: bool) -> None:
    """Release the reservation and, on success, mark the ids as sent."""
    if not ids:
        return
    sent_key = f"sent_{channel}"
    pending_key = f"sent_{channel}_pending"
    async with AsyncSessionLocal() as session:
        current = await _load_state_locked(session)
        pending = set(_id_list(current.get(pending_key))) - set(ids)
        sent = set(_id_list(current.get(sent_key)))
        if delivered:
            sent |= set(ids)
        newval = dict(current)
        newval[pending_key] = _cap(pending)
        newval[sent_key] = _cap(sent)
        telegram = set(_id_list(newval.get("sent_telegram")))
        webhook = set(_id_list(newval.get("sent_webhook")))
        newval["sent"] = _cap(telegram & webhook)
        await upsert_system_setting(
            session,
            "notification_state",
            newval,
            "Identifiers of value signals already pushed, per channel",
        )


async def _send_telegram(cfg: Dict[str, Any], text: str) -> bool:
    token = cfg.get("telegram_bot_token") or ""
    chat_id = cfg.get("telegram_channel_id") or ""
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = await post_public_https(url, {"chat_id": chat_id, "text": text})
    return 200 <= resp.status_code < 300


async def _send_webhook(cfg: Dict[str, Any], signals: List[Dict[str, Any]]) -> bool:
    webhook_url = cfg.get("webhook_url") or ""
    if not webhook_url:
        return False
    resp = await post_public_https(webhook_url, {"event": "VALUE_ALERTS", "signals": signals})
    return 200 <= resp.status_code < 300


async def dispatch_ops_alert(title: str, detail: str) -> None:
    """Notify operators of a payment anomaly on every configured channel.

    Delivery toggles for value alerts do not gate this path: if a bot token or
    webhook URL is configured, the operator wants to hear about it. Never
    raises -- callers sit in webhook ACK handlers where an alert failure must
    not change the HTTP response. Dedup is the caller's job (state gates).
    """
    try:
        async with AsyncSessionLocal() as session:
            cfg = await load_notification_config(session)
    except Exception as exc:
        logger.warning("Ops alert config load failed: %s", type(exc).__name__)
        return
    text = f"MatchLambda OPS ALERT\n{title}\n{detail}"
    try:
        await _send_telegram(cfg, text)
    except Exception as exc:
        logger.warning("Ops alert telegram failed: %s", type(exc).__name__)
    try:
        webhook_url = cfg.get("webhook_url") or ""
        if webhook_url:
            await post_public_https(
                webhook_url,
                {"event": "OPS_ALERT", "title": title, "detail": detail},
            )
    except Exception as exc:
        logger.warning("Ops alert webhook failed: %s", type(exc).__name__)


async def dispatch_value_alerts() -> None:
    """Push fresh +EV signals.

    Each channel is claimed before sending and marked sent only when the post is
    accepted; a failed send releases the claim so the signal is retried next run.
    """
    from app.api.v1.alpha import collect_value_signals

    async with AsyncSessionLocal() as session:
        notes = await load_notification_config(session)
        telegram_on = bool(notes.get("telegram_enabled"))
        webhook_on = bool(notes.get("webhook_enabled"))
        if not telegram_on and not webhook_on:
            return

        quant = await load_quant_config(session)
        raw_min_ev = notes.get("telegram_min_ev")
        min_ev = float(quant["value_scanner_min_ev"] if raw_min_ev is None else raw_min_ev)
        found = await collect_value_signals(
            session,
            min_ev=min_ev,
            max_odds=12.0,
            bankroll=1000.0,
            strategy="HALF_KELLY",
            limit=20,
            kelly_fraction=float(quant["kelly_fraction"]),
            max_stake_cap=float(quant["max_stake_cap"]),
        )
        signals = found["signals"]
        state = await get_system_setting(session, "notification_state", {"sent": []})
        legacy = set(_id_list(state.get("sent")))
        sent_telegram = set(_id_list(state.get("sent_telegram"))) | legacy
        sent_webhook = set(_id_list(state.get("sent_webhook"))) | legacy

    candidate_telegram = [
        signal["signal_id"] for signal in signals
        if telegram_on and signal["signal_id"] not in sent_telegram
    ]
    candidate_webhook = [
        signal["signal_id"] for signal in signals
        if webhook_on and signal["signal_id"] not in sent_webhook
    ]

    claimed_telegram = await _claim_signals("telegram", candidate_telegram)
    claimed_webhook = await _claim_signals("webhook", candidate_webhook)
    if not claimed_telegram and not claimed_webhook:
        return

    by_id = {signal["signal_id"]: signal for signal in signals}

    if claimed_telegram:
        telegram_ok = False
        try:
            telegram_ok = await _send_telegram(
                notes, _format_alerts([by_id[i] for i in claimed_telegram])
            )
        except Exception as exc:
            logger.warning("Telegram alert failed: %s", type(exc).__name__)
        await _finalize_signals("telegram", claimed_telegram, telegram_ok)

    if claimed_webhook:
        webhook_ok = False
        try:
            webhook_ok = await _send_webhook(notes, [by_id[i] for i in claimed_webhook])
        except Exception as exc:
            logger.warning("Webhook alert failed: %s", type(exc).__name__)
        await _finalize_signals("webhook", claimed_webhook, webhook_ok)
