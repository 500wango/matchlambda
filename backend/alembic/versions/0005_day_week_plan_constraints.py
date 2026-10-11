"""Extend invoice plan checks for the entry-level PRO_DAY / PRO_WEEK passes.

PRD v1.4.0 introduced $3/1-day and $9/7-day units; the old checks only
allowed PRO_MONTHLY/PRO_SEASON and rejected the new rows outright. The
existing constraint names differ across environments (initial schema used
the implicit ``crypto_invoices_plan_type_check``), so the swap targets any
CHECK whose definition mentions plan_type and re-creates the canonical
``chk_invoice_plan_type`` / ``chk_invoice_plan_duration`` pair.

Revision ID: 0005_day_week_plans
Revises: 0004_align_orm_constraints
Create Date: 2026-10-05 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_day_week_plans"
down_revision: Union[str, None] = "0004_align_orm_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PLAN_CHECK_QUERY = sa.text(
    """
    SELECT conname FROM pg_constraint
    WHERE conrelid = 'crypto_invoices'::regclass AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%plan_type%'
    """
)


def _drop_plan_checks() -> None:
    bind = op.get_bind()
    for row in bind.execute(_PLAN_CHECK_QUERY).fetchall():
        bind.execute(sa.text(f'ALTER TABLE crypto_invoices DROP CONSTRAINT "{row.conname}"'))


def upgrade() -> None:
    _drop_plan_checks()
    op.execute(
        """
        ALTER TABLE crypto_invoices ADD CONSTRAINT chk_invoice_plan_type
        CHECK (plan_type IN ('PRO_DAY', 'PRO_WEEK', 'PRO_MONTHLY', 'PRO_SEASON'))
        """
    )
    op.execute(
        """
        ALTER TABLE crypto_invoices ADD CONSTRAINT chk_invoice_plan_duration CHECK (
            (plan_type = 'PRO_DAY' AND duration_days = 1)
            OR (plan_type = 'PRO_WEEK' AND duration_days = 7)
            OR (plan_type = 'PRO_MONTHLY' AND duration_days = 30)
            OR (plan_type = 'PRO_SEASON' AND duration_days = 270)
        )
        """
    )


def downgrade() -> None:
    # Day/week invoices cannot survive the downgrade; block instead of orphaning rows.
    bind = op.get_bind()
    count = bind.execute(
        sa.text("SELECT count(*) FROM crypto_invoices WHERE plan_type IN ('PRO_DAY', 'PRO_WEEK')")
    ).scalar()
    if count:
        raise RuntimeError(f"{count} PRO_DAY/PRO_WEEK invoices exist; delete them before downgrading.")
    _drop_plan_checks()
    op.execute(
        """
        ALTER TABLE crypto_invoices ADD CONSTRAINT chk_invoice_plan_type
        CHECK (plan_type IN ('PRO_MONTHLY', 'PRO_SEASON'))
        """
    )
    op.execute(
        """
        ALTER TABLE crypto_invoices ADD CONSTRAINT chk_invoice_plan_duration CHECK (
            (plan_type = 'PRO_MONTHLY' AND duration_days = 30)
            OR (plan_type = 'PRO_SEASON' AND duration_days = 270)
        )
        """
    )
