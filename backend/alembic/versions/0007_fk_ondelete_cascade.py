"""Add ON DELETE CASCADE to match/team-owned foreign keys.

Rows that are owned by a parent (a match's source mapping, odds snapshots and
predictions; a team's aliases) have no meaning without that parent, so deleting
the parent should remove them instead of raising a foreign-key error. Parent
references that carry independent business value -- ``predictions`` ->
``model_parameters``, and every ``league``/``team``/``user`` reference -- keep
the default restrictive behaviour on purpose.

The migration locates each FK by its (table, column) rather than a fixed
constraint name, so it works across environments, and it skips constraints that
already cascade. ``downgrade`` restores ``NO ACTION``.

Revision ID: 0007_fk_ondelete_cascade
Revises: 0006_dedup_teams_model_param
Create Date: 2026-10-11 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_fk_ondelete_cascade"
down_revision: Union[str, None] = "0006_dedup_teams_model_param"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, referenced_table, referenced_column)
_CASCADE_FKS = [
    ("team_aliases", "team_id", "teams", "id"),
    ("match_sources", "match_id", "matches", "id"),
    ("odds_snapshots", "match_id", "matches", "id"),
    ("predictions", "match_id", "matches", "id"),
]

_FIND_FK = sa.text(
    """
    SELECT con.conname, con.confdeltype
    FROM pg_constraint con
    JOIN pg_attribute att
      ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
    WHERE con.conrelid = CAST(:table AS regclass)
      AND con.contype = 'f'
      AND att.attname = :column
      AND array_length(con.conkey, 1) = 1
    """
)


def _set_ondelete(bind, table: str, column: str, ref_table: str, ref_column: str, code: str) -> bool:
    """Set the FK's ON DELETE action; returns True when a change was made.

    ``code`` is the pg_constraint.confdeltype value: 'c' = CASCADE, 'a' = NO ACTION.
    """
    row = bind.execute(_FIND_FK, {"table": table, "column": column}).fetchone()
    if row is None:
        return False
    name, current = row[0], row[1]
    if current == code:
        return False
    action = "CASCADE" if code == "c" else "NO ACTION"
    bind.execute(sa.text(f'ALTER TABLE "{table}" DROP CONSTRAINT "{name}"'))
    bind.execute(sa.text(
        f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" '
        f'FOREIGN KEY ("{column}") REFERENCES "{ref_table}"("{ref_column}") ON DELETE {action}'
    ))
    return True


def upgrade() -> None:
    bind = op.get_bind()
    changed = 0
    for table, column, ref_table, ref_column in _CASCADE_FKS:
        if _set_ondelete(bind, table, column, ref_table, ref_column, "c"):
            changed += 1
    print(f"[0007] added ON DELETE CASCADE to {changed} foreign key(s)")


def downgrade() -> None:
    bind = op.get_bind()
    for table, column, ref_table, ref_column in _CASCADE_FKS:
        _set_ondelete(bind, table, column, ref_table, ref_column, "a")
