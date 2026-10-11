"""Merge cross-country duplicate teams and enforce one model parameter per training set.

Two review findings are addressed here:

* ``model_parameters`` grew without bound because the training-data reference
  embedded the wall clock. This migration removes any pre-existing duplicate
  ``(league_id, training_data_ref)`` rows (re-pointing ``predictions`` at the
  survivor first) and adds ``uq_model_param_league_ref`` so the invariant is
  enforced by the database from now on.
* Several clubs existed twice — one row with a real nationality and an
  identical-named clone under ``Europe`` — which made the resolver ambiguous
  and silently dropped UCL/UEL events. This migration picks one canonical team
  per duplicate cluster (preferring the real-nation, match-bearing row),
  re-points ``matches``/``team_aliases`` at it, drops alias rows that would
  collide with an existing unique alias, and deletes the clones.

Both steps are idempotent: a second run finds no duplicates and the constraint
guard is a no-op.

Downgrade: the ``uq_model_param_league_ref`` constraint is dropped. The team
merge is **not reversible** — the deleted clone rows (and the ids that pointed
at them) are gone — so ``downgrade`` deliberately leaves the merged data
intact rather than corrupting it; it only reverses the additive schema change.

Revision ID: 0006_dedup_teams_model_param
Revises: 0005_day_week_plans
Create Date: 2026-10-11 12:00:00.000000

"""
from typing import Dict, List, Sequence, Union
from collections import defaultdict

from alembic import op
import sqlalchemy as sa

revision: str = "0006_dedup_teams_model_param"
down_revision: Union[str, None] = "0005_day_week_plans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INTERNATIONAL = {"europe", "world", "international", "uefa", "global"}
_UNIQUE_CONSTRAINT = "uq_model_param_league_ref"


def _is_international(country: str) -> bool:
    return (country or "").strip().lower() in _INTERNATIONAL


# --------------------------------------------------------------------------- #
# model_parameters: dedup + unique constraint
# --------------------------------------------------------------------------- #
def _dedup_model_parameters(bind) -> int:
    """Keep the newest row per (league_id, training_data_ref); re-point predictions."""
    before = bind.execute(sa.text("SELECT count(*) FROM model_parameters")).scalar() or 0
    # Re-point predictions that reference a duplicate onto the surviving row.
    bind.execute(sa.text(
        """
        WITH ranked AS (
            SELECT id,
                   first_value(id) OVER (
                       PARTITION BY league_id, training_data_ref
                       ORDER BY calculated_at DESC, id DESC
                   ) AS keep_id,
                   row_number() OVER (
                       PARTITION BY league_id, training_data_ref
                       ORDER BY calculated_at DESC, id DESC
                   ) AS rn
            FROM model_parameters
        )
        UPDATE predictions p
        SET model_parameters_id = r.keep_id
        FROM ranked r
        WHERE p.model_parameters_id = r.id AND r.rn > 1
        """
    ))
    bind.execute(sa.text(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY league_id, training_data_ref
                       ORDER BY calculated_at DESC, id DESC
                   ) AS rn
            FROM model_parameters
        )
        DELETE FROM model_parameters mp
        USING ranked r
        WHERE mp.id = r.id AND r.rn > 1
        """
    ))
    after = bind.execute(sa.text("SELECT count(*) FROM model_parameters")).scalar() or 0
    return before - after


def _ensure_model_param_unique(bind) -> None:
    exists = bind.execute(sa.text(
        "SELECT 1 FROM pg_constraint "
        "WHERE conname = :name AND conrelid = 'model_parameters'::regclass"
    ), {"name": _UNIQUE_CONSTRAINT}).scalar()
    if exists:
        return
    # Table was just de-duplicated, so this cannot fail on existing data.
    bind.execute(sa.text(
        f"ALTER TABLE model_parameters ADD CONSTRAINT {_UNIQUE_CONSTRAINT} "
        "UNIQUE (league_id, training_data_ref)"
    ))


# --------------------------------------------------------------------------- #
# teams: merge cross-country duplicate clusters
# --------------------------------------------------------------------------- #
def _build_team_merge_map(bind) -> Dict[str, str]:
    teams = bind.execute(
        sa.text("SELECT id, canonical_name, country FROM teams")
    ).fetchall()
    if len(teams) < 2:
        return {}

    parent: Dict[str, str] = {row[0]: row[0] for row in teams}
    country_of: Dict[str, str] = {row[0]: row[2] for row in teams}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # (1) same canonical name, different country (e.g. "AC Milan" Italy/Europe).
    by_name: Dict[str, List] = defaultdict(list)
    for row in teams:
        by_name[row[1]].append(row)
    for group in by_name.values():
        if len(group) > 1 and len({row[2] for row in group}) > 1:
            for row in group[1:]:
                union(group[0][0], row[0])

    # (2) same (source_name, external_name) confirmed alias, different country.
    aliases = bind.execute(sa.text(
        "SELECT team_id, source_name, external_name, external_id FROM team_aliases"
    )).fetchall()
    by_alias: Dict[tuple, set] = defaultdict(set)
    for row in aliases:
        if row[3] is None:
            by_alias[(row[1], row[2])].add(row[0])
    for team_ids in by_alias.values():
        candidates = [tid for tid in team_ids if tid in country_of]
        if len(candidates) > 1 and len({country_of[tid] for tid in candidates}) > 1:
            for tid in candidates[1:]:
                union(candidates[0], tid)

    components: Dict[str, List] = defaultdict(list)
    for row in teams:
        components[find(row[0])].append(row)

    match_counts = {
        row[0]: row[1]
        for row in bind.execute(sa.text(
            "SELECT team_id, count(*) FROM ("
            "  SELECT home_team_id AS team_id FROM matches"
            "  UNION ALL SELECT away_team_id FROM matches"
            ") s GROUP BY team_id"
        )).fetchall()
    }
    alias_counts = {
        row[0]: row[1]
        for row in bind.execute(sa.text(
            "SELECT team_id, count(*) FROM team_aliases GROUP BY team_id"
        )).fetchall()
    }

    merge_map: Dict[str, str] = {}
    for group in components.values():
        if len(group) < 2:
            continue

        def rank(row):
            return (
                1 if _is_international(row[2]) else 0,  # prefer a real nation
                -match_counts.get(row[0], 0),           # then the row with history
                -alias_counts.get(row[0], 0),
                row[0],                                 # stable tie-break
            )

        keep = min(group, key=rank)
        for row in group:
            if row[0] != keep[0]:
                merge_map[row[0]] = keep[0]
    return merge_map


def _assert_no_self_matches(bind, merge_map: Dict[str, str]) -> None:
    """Never let a merge collapse a match's two sides onto the same team."""
    for row in bind.execute(sa.text("SELECT id, home_team_id, away_team_id FROM matches")).fetchall():
        new_home = merge_map.get(row[1], row[1])
        new_away = merge_map.get(row[2], row[2])
        if new_home == new_away:
            raise RuntimeError(
                f"Refusing team merge: match {row[0]} would have identical home/away ({new_home})."
            )


def _dedupe_alias_collisions(bind, merge_map: Dict[str, str]) -> int:
    """Drop alias rows that would violate a unique alias index after re-pointing."""
    if not merge_map:
        return 0
    alias_rows = bind.execute(sa.text(
        "SELECT id, source_name, external_id, external_name, country, team_id FROM team_aliases"
    )).fetchall()
    groups: Dict[tuple, List] = defaultdict(list)
    for row in alias_rows:
        team_id = row[5]
        if team_id not in merge_map and team_id not in merge_map.values():
            continue
        if row[2] is not None:
            key = ("ext", row[1], row[2])
        else:
            key = ("name", row[1], row[4], row[3])
        groups[key].append(row)

    deleted = 0
    for rows in groups.values():
        if len(rows) < 2:
            continue
        teams_involved = {row[5] for row in rows}
        # Prefer the alias already owned by a survivor team; otherwise lowest id.
        survivors = [row for row in rows if row[5] not in merge_map]
        rows_sorted = sorted(rows, key=lambda r: (r[5] in merge_map, str(r[0])))
        keeper = survivors[0] if survivors else rows_sorted[0]
        for row in rows:
            if row is keeper:
                continue
            bind.execute(sa.text("DELETE FROM team_aliases WHERE id = :id"), {"id": str(row[0])})
            deleted += 1
    return deleted


def _apply_team_merge(bind, merge_map: Dict[str, str]) -> None:
    if not merge_map:
        return
    _assert_no_self_matches(bind, merge_map)
    _dedupe_alias_collisions(bind, merge_map)
    for old_id, keep_id in merge_map.items():
        bind.execute(
            sa.text("UPDATE matches SET home_team_id = :keep WHERE home_team_id = :old"),
            {"keep": keep_id, "old": old_id},
        )
        bind.execute(
            sa.text("UPDATE matches SET away_team_id = :keep WHERE away_team_id = :old"),
            {"keep": keep_id, "old": old_id},
        )
        bind.execute(
            sa.text("UPDATE team_aliases SET team_id = :keep WHERE team_id = :old"),
            {"keep": keep_id, "old": old_id},
        )
        bind.execute(sa.text("DELETE FROM teams WHERE id = :old"), {"old": old_id})


# --------------------------------------------------------------------------- #
# settings seeds: keep stored defaults in sync with the code defaults
# --------------------------------------------------------------------------- #
def _sync_setting_seeds(bind) -> None:
    bind.execute(sa.text(
        """
        UPDATE system_settings
        SET value = jsonb_set(value, '{sharp_bookmakers}',
                              (value -> 'sharp_bookmakers') || '"williamhill"'::jsonb)
        WHERE key = 'data_provider'
          AND jsonb_typeof(value -> 'sharp_bookmakers') = 'array'
          AND NOT (value -> 'sharp_bookmakers' ? 'williamhill')
        """
    ))
    bind.execute(sa.text(
        """
        UPDATE system_settings
        SET value = jsonb_set(value, '{day_price_usd}', '3.0'::jsonb)
        WHERE key = 'monetization' AND NOT (value ? 'day_price_usd')
        """
    ))
    bind.execute(sa.text(
        """
        UPDATE system_settings
        SET value = jsonb_set(value, '{week_price_usd}', '9.0'::jsonb)
        WHERE key = 'monetization' AND NOT (value ? 'week_price_usd')
        """
    ))


def upgrade() -> None:
    bind = op.get_bind()
    # Order matters: the model-parameter constraint is independent, the team
    # merge must finish before any later reference relies on one id per club.
    removed_models = _dedup_model_parameters(bind)
    _ensure_model_param_unique(bind)
    merge_map = _build_team_merge_map(bind)
    _apply_team_merge(bind, merge_map)
    _sync_setting_seeds(bind)
    print(
        f"[0006] removed {removed_models} duplicate model_parameters row(s); "
        f"merged {len(merge_map)} duplicate team(s)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(sa.text(
        "SELECT 1 FROM pg_constraint "
        "WHERE conname = :name AND conrelid = 'model_parameters'::regclass"
    ), {"name": _UNIQUE_CONSTRAINT}).scalar()
    if exists:
        bind.execute(sa.text(
            f"ALTER TABLE model_parameters DROP CONSTRAINT {_UNIQUE_CONSTRAINT}"
        ))
    # The team merge cannot be undone (clone rows were deleted); to avoid
    # corrupting data the downgrade intentionally leaves it in place. The seed
    # additions are additive and also left untouched.
