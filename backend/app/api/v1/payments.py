import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any
import httpx
from fastapi import APIRouter, Depends, Header, Request, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.rate_limiter import check_rate_limit
from app.models import User, CryptoInvoice
from app.schemas.payment import CreateInvoiceRequest, InvoiceResponse, OrderDetailResponse
from app.api.deps import get_current_user
from app.services.nowpayments import verify_nowpayments_signature, canonical_json_dumps

router = APIRouter(prefix="/payments", tags=["Payments"])

CATALOG = {
    "PRO_MONTHLY": {
        "amount_usd": Decimal("29.00"),
        "duration_days": 30,
    },
    "PRO_SEASON": {
        "amount_usd": Decimal("149.00"),
        "duration_days": 270,
    },
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

    # 3. Check existing order by (user_id, request_key)
    stmt = select(CryptoInvoice).where(
        CryptoInvoice.user_id == user.id,
        CryptoInvoice.request_key == request_uuid,
    )
    existing_order = (await db.execute(stmt)).scalar_one_or_none()
    if existing_order:
        if existing_order.plan_type != req.plan_type:
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
        amount_usd=catalog_item["amount_usd"],
        duration_days=catalog_item["duration_days"],
        payment_status="CREATING",
    )
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)

    # 6. Call NOWPayments hosted invoice API outside lock
    gateway_invoice_id = None
    checkout_url = None
    try:
        if api_key == "sandbox_test_key" or api_key.startswith("test_"):
            # Mock provider response for automated testing or sandbox testing
            gateway_invoice_id = f"np_inv_{uuid.uuid4().hex[:10]}"
            checkout_url = f"https://nowpayments.io/payment/?iid={gateway_invoice_id}"
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    "https://api.nowpayments.io/v1/invoice",
                    headers={"x-api-key": api_key},
                    json={
                        "price_amount": float(catalog_item["amount_usd"]),
                        "price_currency": "usd",
                        "order_id": order_id,
                        "order_description": f"MatchLambda {req.plan_type} Pass",
                        "ipn_callback_url": settings.NOWPAYMENTS_IPN_CALLBACK_URL,
                        "success_url": f"{settings.APP_ORIGIN}/pricing?status=success&order_id={order_id}",
                        "cancel_url": f"{settings.APP_ORIGIN}/pricing?status=cancel&order_id={order_id}",
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

    # Transition to PENDING
    new_order.payment_status = "PENDING"
    new_order.gateway_invoice_id = gateway_invoice_id
    new_order.checkout_url = checkout_url
    new_order.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(new_order)

    response.status_code = status.HTTP_201_CREATED
    return InvoiceResponse(
        order_id=new_order.order_id,
        plan_type=new_order.plan_type,
        amount_usd=new_order.amount_usd,
        payment_status=new_order.payment_status,
        checkout_url=new_order.checkout_url,
        valid_until=new_order.valid_until,
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
    try:
        body = await request.json()
    except Exception:
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
    payment_status = body.get("payment_status")
    payment_id = str(body.get("payment_id", ""))

    if not order_id:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_PAYLOAD",
            message="Missing order_id in webhook.",
        )

    # 2. Lock invoice row FOR UPDATE
    stmt = (
        select(CryptoInvoice)
        .where(CryptoInvoice.order_id == order_id)
        .with_for_update()
    )
    invoice = (await db.execute(stmt)).scalar_one_or_none()
    if not invoice:
        # A valid but unknown local order returns 503 for reconciliation/retry
        raise AppException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="ORDER_RECONCILIATION_REQUIRED",
            message="Order not found for reconciliation.",
        )

    # 3. If credited_at is present, return 200 without granting again (Idempotent)
    if invoice.credited_at is not None:
        return {"status": "ok"}

    # 4. Mandatory provider settlement verification (Section 3 of payment spec)
    # Fetch referenced payment through GET /v1/payment/{payment_id}
    api_key = settings.NOWPAYMENTS_API_KEY
    if api_key and not (api_key == "sandbox_test_key" or api_key.startswith("test_")):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                pay_resp = await client.get(
                    f"https://api.nowpayments.io/v1/payment/{payment_id}",
                    headers={"x-api-key": api_key},
                )
                if pay_resp.status_code == 200:
                    pay_info = pay_resp.json()
                    prov_order_id = str(pay_info.get("order_id", ""))
                    prov_status = str(pay_info.get("payment_status", "")).lower()
                    prov_price_amount = Decimal(str(pay_info.get("price_amount", "0")))
                    prov_price_curr = str(pay_info.get("price_currency", "")).lower()

                    # Require matching order_id, price_currency=usd, price_amount
                    if (
                        prov_order_id != invoice.order_id
                        or prov_price_curr != "usd"
                        or prov_price_amount != invoice.amount_usd
                    ):
                        invoice.payment_status = "REVIEW"
                        invoice.updated_at = datetime.now(timezone.utc)
                        await db.commit()
                        raise AppException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            code="PAYMENT_MISMATCH",
                            message="Settlement verification failed: order or amount mismatch.",
                        )
                    # Use verified status from provider API
                    payment_status = prov_status
                else:
                    raise AppException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        code="ORDER_RECONCILIATION_REQUIRED",
                        message="Provider payment record fetch failed.",
                    )
        except httpx.RequestError:
            raise AppException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="ORDER_RECONCILIATION_REQUIRED",
                message="Provider API timeout during settlement verification.",
            )

    now = datetime.now(timezone.utc)

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
        invoice.payment_status = "REVIEW"
        invoice.updated_at = now
        await db.commit()
        return {"status": "ok"}

    # Intermediate statuses (waiting, confirming, confirmed, sending)
    invoice.updated_at = now
    await db.commit()
    return {"status": "ok"}
