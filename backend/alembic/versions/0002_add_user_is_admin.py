"""Add is_admin column to users table

Revision ID: 0002_add_user_is_admin
Revises: 0001_initial_schema
Create Date: 2026-10-04 02:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_add_user_is_admin'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE users DROP COLUMN IF EXISTS is_admin;
    """)
