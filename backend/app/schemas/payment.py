from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class CreateInvoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Forbid client-supplied price or duration fields

    plan_type: Literal["PRO_DAY", "PRO_WEEK", "PRO_MONTHLY", "PRO_SEASON"]


class InvoiceResponse(BaseModel):
    order_id: str
    plan_type: str
    amount_usd: Decimal
    payment_status: str
    checkout_url: Optional[str] = None
    valid_until: Optional[datetime] = None


class OrderDetailResponse(BaseModel):
    order_id: str
    plan_type: str
    amount_usd: Decimal
    payment_status: str
    checkout_url: Optional[str] = None
    valid_until: Optional[datetime] = None
    credited_at: Optional[datetime] = None
    plan_expires_at: Optional[datetime] = None
