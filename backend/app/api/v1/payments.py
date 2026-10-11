import json
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any
import httpx
from fastapi import APIRouter, Depends, Header, Request, status, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.rate_limiter import check_rate_limit, client_address
from app.models import User, CryptoInvoice
from app.schemas.payment import CreateInvoiceRequest, InvoiceResponse, OrderDetailResponse
from app.api.deps import get_current_user
from app.services.nowpayments import verify_nowpayments_signature
from app.services.notifier import dispatch_ops_alert
from app.services.settings_service import load_monetization_config

router = APIRouter(prefix="/payments", tags=["Payments"])

CATALOG = {
    "PRO_DAY": {
        "amount_usd": Decimal("3.00"),
        "duration_days": 1,
        "price_key": "day_price_usd",
    },
    "PRO_WEEK": {
        "amount_usd": Decimal("9.00"),
        "duration_days": 7,
        "price_key": "week_price_usd",
    },
    "PRO_MONTHLY": {
        "amount_usd": Decimal("29.00"),
        "duration_days": 30,
        "price_key": "monthly_price_usd",
    },
    "PRO_SEASON": {
        "amount_usd": Decimal("149.00"),
        "duration_days": 270,
        "price_key": "season_price_usd",
    },
}


class _MalformedAmount(ValueError):
    """Raised when a value cannot be interpreted as a USD amount."""


def _quantize_usd(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise _MalformedAmount(f"Not a valid USD amount: {value!r}") from exc


def _plan_amount(mon_cfg: Dict[str, Any], plan_type: str) -> Decimal:
    catalog_item = CATALOG[plan_type]
    key = catalog_item["price_key"]
    if key not in mon_cfg or mon_cfg[key] is None or mon_cfg[key] == "":
        return catalog_item["amount_usd"]
    try:
        return _quantize_usd(mon_cfg[key])
    except _MalformedAmount:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="Configured plan price is invalid.",
        )


def _existing_order_response(
    existing_order: CryptoInvoice,
    plan_type: str,
    response: Response,
) -> InvoiceResponse:
    """Reuse the reply for an idempotency key already persisted by this user."""
    if existing_order.plan_type != plan_type:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_CONFLICT",
            message="Repeated idempotency key with conflicting plan_type.",
        )

    # If still in CREATING state
    if existing_order.payment_status == "CREATING":
        response.status_code = status.HTTP_202_ACCEPTED
        return InvoiceResponse(
            order_id=existing_order.order_id,
            plan_type=existing_order.plan_type,
            amount_usd=existing_order.amount_usd,
            payment_status=existing_order.payment_status,
            checkout_url=None,
            valid_until=existing_order.valid_until,
        )

    # Existing ready/final order returns 200
    response.status_code = status.HTTP_200_OK
    return InvoiceResponse(
        order_id=existing_order.order_id,
        plan_type=existing_order.plan_type,
        amount_usd=existing_order.amount_usd,
        payment_status=existing_order.payment_status,
        checkout_url=existing_order.checkout_url,
        valid_until=existing_order.valid_until,
    )


@router.get("/pricing")
async def get_public_pricing(db: AsyncSession = Depends(get_db)):
    mon_cfg = await load_monetization_config(db)
    monthly = _plan_amount(mon_cfg, "PRO_MONTHLY")
    season = _plan_amount(mon_cfg, "PRO_SEASON")
    return {
        "day_price_usd": float(_plan_amount(mon_cfg, "PRO_DAY")),
        "week_price_usd": float(_plan_amount(mon_cfg, "PRO_WEEK")),
        "monthly_price_usd": float(monthly),
        "season_price_usd": float(season),
        "new_user_trial_days": int(mon_cfg.get("new_user_trial_days", 3)),
        "accepted_tokens": list(mon_cfg.get("accepted_tokens") or []),
    }


@router.post("/create-invoice", response_model=InvoiceResponse)
async def create_invoice(
    req: CreateInvoiceRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Rate limit by user_id: max 5 invoices per minute
    await check_rate_limit(f"create_invoice:{user.id}", limit=5, window_seconds=60)
    # 1. Validate UUID idempotency key
    try:
        request_uuid = uuid.UUID(idempotency_key)
    except ValueError:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="Idempotency-Key header must be a valid UUID.",
        )

    # 2. Check catalog
    catalog_item = CATALOG.get(req.plan_type)
    if not catalog_item:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message=f"Unsupported plan_type '{req.plan_type}'.",
        )

    mon_cfg = await load_monetization_config(db)
    amount_usd = _plan_amount(mon_cfg, req.plan_type)
    if amount_usd < Decimal("1.00"):
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="Configured plan price must be at least 1.00 USD.",
        )
    accepted_tokens = [str(token).strip() for token in (mon_cfg.get("accepted_tokens") or []) if str(token).strip()]

    # 3. Check existing order by (user_id, request_key)
    stmt = select(CryptoInvoice).where(
        CryptoInvoice.user_id == user.id,
        CryptoInvoice.request_key == request_uuid,
    )
    existing_order = (await db.execute(stmt)).scalar_one_or_none()
    if existing_order:
        return _existing_order_response(existing_order, req.plan_type, response)

    # 4. Check gateway configuration before creating an order
    api_key = settings.NOWPAYMENTS_API_KEY
    if not api_key:
        raise AppException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="PAYMENTS_UNAVAILABLE",
            message="Crypto payments are currently unavailable.",
        )

    # 5. Persist order in CREATING state
    order_id = f"MLQ_{uuid.uuid4().hex[:12].upper()}"
    new_order = CryptoInvoice(
        user_id=user.id,
        order_id=order_id,
        request_key=request_uuid,
        plan_type=req.plan_type,
        amount_usd=amount_usd,
        duration_days=catalog_item["duration_days"],
        payment_status="CREATING",
    )
    db.add(new_order)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent request with the same Idempotency-Key won the unique
        # constraint race. Re-read the winning row and answer like the
        # existing-order branch instead of surfacing a 500.
        await db.rollback()
        existing_order = (await db.execute(stmt)).scalar_one_or_none()
        if existing_order is None:
            raise
        return _existing_order_response(existing_order, req.plan_type, response)
    await db.refresh(new_order)

    # 6. Call NOWPayments hosted invoice API outside lock
    gateway_invoice_id = None
    checkout_url = None
    try:
        if settings.PAYMENTS_SANDBOX_MODE:
            # Mock provider response for automated testing or sandbox testing
            gateway_invoice_id = f"np_inv_{uuid.uuid4().hex[:10]}"
            checkout_url = f"https://nowpayments.io/payment/?iid={gateway_invoice_id}"
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    "https://api.nowpayments.io/v1/invoice",
                    headers={"x-api-key": api_key},
                    json={
                        "price_amount": float(amount_usd),
                        "price_currency": "usd",
                        "order_id": order_id,
                        "order_description": f"MatchLambda {req.plan_type} Pass",
                        "ipn_callback_url": settings.NOWPAYMENTS_IPN_CALLBACK_URL,
                        "success_url": f"{settings.APP_ORIGIN}/pricing?status=success&order_id={order_id}",
                        "cancel_url": f"{settings.APP_ORIGIN}/pricing?status=cancel&order_id={order_id}",
                        **({"pay_currency": accepted_tokens[0].lower()} if len(accepted_tokens) == 1 else {}),
                    },
                )
                if res.status_code in (200, 201):
                    data = res.json()
                    gateway_invoice_id = str(data.get("id"))
                    checkout_url = data.get("invoice_url")
                else:
                    new_order.payment_status = "FAILED"
                    await db.commit()
                    raise AppException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        code="PROVIDER_UNAVAILABLE",
                        message="Failed to create provider invoice.",
                    )
    except httpx.RequestError:
        # Uncertain timeout keeps CREATING for operator reconciliation
        response.status_code = status.HTTP_202_ACCEPTED
        return InvoiceResponse(
            order_id=new_order.order_id,
            plan_type=new_order.plan_type,
            amount_usd=new_order.amount_usd,
            payment_status="CREATING",
            checkout_url=None,
            valid_until=None,
        )

    # A webhook may already have moved this row to PAID. Never overwrite that.
    order_pk = new_order.id
    locked_stmt = (
        select(CryptoInvoice)
        .where(CryptoInvoice.id == order_pk)
        .with_for_update()
    )
    locked = (await db.execute(locked_stmt)).scalar_one()
    if locked.credited_at is None and locked.payment_status == "CREATING":
        locked.payment_status = "PENDING"
        locked.gateway_invoice_id = gateway_invoice_id or None
        locked.checkout_url = checkout_url
        locked.updated_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        locked = (
            await db.execute(select(CryptoInvoice).where(CryptoInvoice.id == order_pk))
        ).scalar_one()
    await db.refresh(locked)

    response.status_code = (
        status.HTTP_201_CREATED if locked.payment_status == "PENDING" else status.HTTP_200_OK
    )
    return InvoiceResponse(
        order_id=locked.order_id,
        plan_type=locked.plan_type,
        amount_usd=locked.amount_usd,
        payment_status=locked.payment_status,
        checkout_url=locked.checkout_url,
        valid_until=locked.valid_until,
    )


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order_detail(
    order_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CryptoInvoice).where(
        CryptoInvoice.order_id == order_id,
        CryptoInvoice.user_id == user.id,
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Order '{order_id}' not found.",
        )

    return OrderDetailResponse(
        order_id=order.order_id,
        plan_type=order.plan_type,
        amount_usd=order.amount_usd,
        payment_status=order.payment_status,
        checkout_url=order.checkout_url,
        valid_until=order.valid_until,
        credited_at=order.credited_at,
        plan_expires_at=user.plan_expires_at,
    )


@router.post("/webhook")
async def payments_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_nowpayments_sig: Optional[str] = Header(None, alias="x-nowpayments-sig"),
):
    # Rate limit by client IP before touching the body so a flood cannot make
    # us read (and HMAC) arbitrary payloads.
    await check_rate_limit(f"webhook:{client_address(request)}", limit=60, window_seconds=60)

    max_body = settings.WEBHOOK_MAX_BODY_BYTES
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            too_large = int(declared_length) > max_body
        except ValueError:
            too_large = True
        if too_large:
            raise AppException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                code="PAYLOAD_TOO_LARGE",
                message="Webhook payload exceeds the maximum allowed size.",
            )

    # Stream with a hard cap as well: a chunked request without Content-Length
    # must not be able to bypass the limit.
    raw_body = bytearray()
    async for chunk in request.stream():
        raw_body.extend(chunk)
        if len(raw_body) > max_body:
            raise AppException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                code="PAYLOAD_TOO_LARGE",
                message="Webhook payload exceeds the maximum allowed size.",
            )

    try:
        body = json.loads(bytes(raw_body).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_PAYLOAD",
            message="Malformed JSON body.",
        )
    if not isinstance(body, dict):
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_PAYLOAD",
            message="Malformed JSON body.",
        )

    # 1. Signature authentication
    secret = settings.NOWPAYMENTS_IPN_SECRET
    if not secret or not x_nowpayments_sig:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_SIGNATURE",
            message="Missing signature or webhook secret unconfigured.",
        )

    if not verify_nowpayments_signature(body, x_nowpayments_sig, secret):
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_SIGNATURE",
            message="Invalid HMAC-SHA512 signature.",
        )

    order_id = body.get("order_id")
    payment_status = str(body.get("payment_status") or "").lower()
    raw_payment_id = body.get("payment_id")
    payment_id = str(raw_payment_id).strip() if raw_payment_id not in (None, "") else ""

    if not order_id:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_PAYLOAD",
            message="Missing order_id in webhook.",
        )

    # Provider lookup happens before the row lock so a slow HTTP call cannot
    # hold the invoice lock or a pooled connection for the whole timeout.
    api_key = settings.NOWPAYMENTS_API_KEY
    # Sandbox is an explicit deployment opt-in, never inferred from the API key
    # prefix: a "test_"-prefixed production key must not silently disable the
    # provider reconciliation lookup.
    sandbox = settings.PAYMENTS_SANDBOX_MODE
    provider_pay_currency = ""
    if payment_status == "finished" and not sandbox:
        if not api_key or not payment_id:
            raise AppException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="ORDER_RECONCILIATION_REQUIRED",
                message="Finished payments require a provider lookup.",
            )
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                pay_resp = await client.get(
                    f"https://api.nowpayments.io/v1/payment/{payment_id}",
                    headers={"x-api-key": api_key},
                )
        except httpx.RequestError:
            raise AppException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="ORDER_RECONCILIATION_REQUIRED",
                message="Provider API timeout during settlement verification.",
            )
        if pay_resp.status_code != 200:
            raise AppException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="ORDER_RECONCILIATION_REQUIRED",
                message="Provider payment record fetch failed.",
            )
        pay_info = pay_resp.json()
        prov_order_id = str(pay_info.get("order_id", ""))
        prov_status = str(pay_info.get("payment_status", "")).lower()
        try:
            prov_price_amount = _quantize_usd(pay_info.get("price_amount", "0"))
        except _MalformedAmount:
            raise AppException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="ORDER_RECONCILIATION_REQUIRED",
                message="Provider returned a malformed price amount.",
            )
        prov_price_curr = str(pay_info.get("price_currency", "")).lower()
        provider_pay_currency = str(pay_info.get("pay_currency") or "").strip().upper()
        preview = (
            await db.execute(select(CryptoInvoice).where(CryptoInvoice.order_id == order_id))
        ).scalar_one_or_none()
        if preview is None:
            raise AppException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="ORDER_RECONCILIATION_REQUIRED",
                message="Order not found for reconciliation.",
            )
        try:
            local_amount = _quantize_usd(preview.amount_usd)
        except _MalformedAmount:
            raise AppException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="ORDER_RECONCILIATION_REQUIRED",
                message="Invoice amount is malformed.",
            )
        if prov_order_id != preview.order_id or prov_price_curr != "usd" or prov_price_amount != local_amount:
            stmt = (
                select(CryptoInvoice)
                .where(CryptoInvoice.order_id == order_id)
                .with_for_update()
            )
            invoice = (await db.execute(stmt)).scalar_one_or_none()
            if invoice and invoice.credited_at is None:
                was_review = invoice.payment_status == "REVIEW"
                invoice.payment_status = "REVIEW"
                invoice.updated_at = datetime.now(timezone.utc)
                await db.commit()
                if not was_review:
                    await dispatch_ops_alert(
                        "Provider reconciliation mismatch",
                        f"order={order_id} provider=({prov_order_id}, {prov_price_amount} {prov_price_curr}) "
                        f"local=({preview.order_id}, {local_amount} usd)",
                    )
            return {"status": "ok"}
        payment_status = prov_status

    # Lock invoice row FOR UPDATE only after network I/O.
    stmt = (
        select(CryptoInvoice)
        .where(CryptoInvoice.order_id == order_id)
        .with_for_update()
    )
    invoice = (await db.execute(stmt)).scalar_one_or_none()
    if not invoice:
        raise AppException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="ORDER_RECONCILIATION_REQUIRED",
            message="Order not found for reconciliation.",
        )

    if invoice.credited_at is not None:
        return {"status": "ok"}

    now = datetime.now(timezone.utc)

    # Defense in depth for sandbox mode: even with the explicit opt-in flag,
    # a finished webhook carrying a conflicting amount goes to human review.
    if payment_status == "finished" and sandbox and body.get("price_amount") not in (None, ""):
        try:
            amounts_match = _quantize_usd(body["price_amount"]) == _quantize_usd(invoice.amount_usd)
        except _MalformedAmount:
            # Treat an unparseable amount as a mismatch -> human review.
            amounts_match = False
        if not amounts_match:
            was_review = invoice.payment_status == "REVIEW"
            invoice.payment_status = "REVIEW"
            invoice.updated_at = now
            await db.commit()
            if not was_review:
                await dispatch_ops_alert(
                    "Sandbox webhook amount conflicts with invoice",
                    f"order={order_id} webhook_price={body['price_amount']} invoice_amount={invoice.amount_usd}",
                )
            return {"status": "ok"}

    pay_currency = str(body.get("pay_currency") or provider_pay_currency or "").strip().upper()
    if payment_status == "finished" and not payment_id:
        was_review = invoice.payment_status == "REVIEW"
        invoice.payment_status = "REVIEW"
        invoice.updated_at = now
        await db.commit()
        if not was_review:
            await dispatch_ops_alert(
                "Finished webhook missing payment_id",
                f"order={order_id} cannot verify settlement without provider payment_id",
            )
        return {"status": "ok"}
    if payment_status == "finished":
        mon_cfg = await load_monetization_config(db)
        accepted = {str(token).strip().upper() for token in (mon_cfg.get("accepted_tokens") or []) if str(token).strip()}
        if accepted and pay_currency not in accepted:
            was_review = invoice.payment_status == "REVIEW"
            invoice.payment_status = "REVIEW"
            invoice.updated_at = now
            await db.commit()
            if not was_review:
                await dispatch_ops_alert(
                    "Payment in unexpected token",
                    f"order={order_id} pay_currency={pay_currency or 'UNKNOWN'} accepted={sorted(accepted)}",
                )
            # Acknowledge (200) to stop provider retries; operator reconciles REVIEW.
            return {"status": "ok"}

    # 4. Only verified finished payment can be credited
    if payment_status == "finished":
        # Lock user row FOR UPDATE (invoice then user is the consistent lock order)
        user_stmt = select(User).where(User.id == invoice.user_id).with_for_update()
        user = (await db.execute(user_stmt)).scalar_one_or_none()
        if not user:
            raise AppException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="ORDER_RECONCILIATION_REQUIRED",
                message="User for invoice not found.",
            )

        # Set plan_expires_at = max(existing expiry or now, now) + purchased duration
        current_base = user.plan_expires_at if (user.plan_tier == "ANALYST" and user.plan_expires_at and user.plan_expires_at > now) else now
        user.plan_expires_at = current_base + timedelta(days=invoice.duration_days)
        user.plan_tier = "ANALYST"

        invoice.payment_status = "PAID"
        invoice.credited_at = now
        invoice.gateway_payment_id = payment_id
        invoice.updated_at = now

        await db.commit()
        return {"status": "ok"}

    elif payment_status in ("failed", "expired"):
        invoice.payment_status = payment_status.upper()
        invoice.updated_at = now
        await db.commit()
        return {"status": "ok"}

    elif payment_status in ("partially_paid", "refunded"):
        was_review = invoice.payment_status == "REVIEW"
        invoice.payment_status = "REVIEW"
        invoice.updated_at = now
        await db.commit()
        if not was_review:
            await dispatch_ops_alert(
                "Payment requires manual reconciliation",
                f"order={order_id} provider_status={payment_status}",
            )
        return {"status": "ok"}

    # Intermediate statuses (waiting, confirming, confirmed, sending)
    invoice.updated_at = now
    await db.commit()
    return {"status": "ok"}
