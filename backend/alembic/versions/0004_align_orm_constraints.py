"""Align check names, audit id default, and match status index with the ORM.

Revision ID: 0004_align_orm_constraints
Revises: 0003_add_settings_and_audit_logs
Create Date: 2026-10-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_align_orm_constraints"
down_revision: Union[str, None] = "0003_add_settings_and_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, target name, unique fragment of pg_get_constraintdef)
_CHECK_RENAMES = [
    ("matches", "chk_match_status", "POSTPONED"),
    ("matches", "chk_match_home_score", "home_score >="),
    ("matches", "chk_match_away_score", "away_score >="),
    ("matches", "chk_match_different_teams", "home_team_id <> away_team_id"),
    ("matches", "chk_match_result_consistency", "result_available_at"),
    ("odds_snapshots", "chk_odds_home", "home_odds >"),
    ("odds_snapshots", "chk_odds_draw", "draw_odds >"),
    ("odds_snapshots", "chk_odds_away", "away_odds >"),
    ("odds_snapshots", "chk_odds_dejuice_method", "MULTIPLICATIVE"),
    ("odds_snapshots", "chk_odds_prob_home", "implied_prob_home >="),
    ("odds_snapshots", "chk_odds_prob_draw", "implied_prob_draw >="),
    ("odds_snapshots", "chk_odds_prob_away", "implied_prob_away >="),
    ("odds_snapshots", "chk_odds_quote_before_recorded", "quote_at <="),
    ("odds_snapshots", "chk_odds_prob_sum", "0.00000001"),
    ("model_parameters", "chk_model_xi_decay", "xi_decay"),
    ("model_parameters", "chk_model_training_cutoff", "training_cutoff"),
    ("model_parameters", "chk_model_team_attack_object", "team_attack"),
    ("model_parameters", "chk_model_team_defense_object", "team_defense"),
    ("predictions", "chk_prediction_lambda_home", "lambda_home"),
    ("predictions", "chk_prediction_mu_away", "mu_away"),
    ("predictions", "chk_prediction_prob_home", "prob_home_win >="),
    ("predictions", "chk_prediction_prob_draw", "prob_draw >="),
    ("predictions", "chk_prediction_prob_away", "prob_away_win >="),
    ("predictions", "chk_prediction_omitted_mass", "omitted_mass"),
    ("predictions", "chk_prediction_as_of_kickoff", "as_of", "generated_at"),
    ("predictions", "chk_prediction_generated_at", "generated_at"),
    ("predictions", "chk_prediction_prob_sum", "0.00000001"),
    ("predictions", "chk_prediction_score_matrix_array", "score_matrix"),
    ("predictions", "chk_prediction_top_scores_array", "top_scores"),
    ("users", "users_email_check", "btrim"),
    ("users", "chk_user_plan_tier", "plan_tier"),
    ("users", "chk_user_analyst_expires", "plan_expires_at IS NOT NULL"),
    ("crypto_invoices", "chk_invoice_plan_type", "plan_type"),
    ("crypto_invoices", "chk_invoice_amount", "amount_usd"),
    ("crypto_invoices", "chk_invoice_plan_duration", "duration_days"),
    ("crypto_invoices", "chk_invoice_payment_status", "payment_status"),
    ("crypto_invoices", "chk_invoice_paid_credited", "credited_at"),
    ("crypto_invoices", "chk_invoice_paid_ids", "gateway_payment_id"),
]

_UNIQUE_RENAMES = [
    ("crypto_invoices", "crypto_invoices_gateway_invoice_id_key", "uq_crypto_invoices_gateway_invoice_id"),
    ("crypto_invoices", "crypto_invoices_gateway_payment_id_key", "uq_crypto_invoices_gateway_payment_id"),
    ("crypto_invoices", "crypto_invoices_order_id_key", "uq_crypto_invoices_order_id"),
    ("crypto_invoices", "crypto_invoices_user_id_request_key_key", "uq_invoice_user_request"),
    ("odds_snapshots", "odds_snapshots_source_name_bookmaker_match_id_quote_at_key", "uq_odds_snapshot"),
    ("predictions", "predictions_match_id_as_of_key", "uq_prediction_match_as_of"),
    ("users", "users_email_key", "uq_users_email"),
]


def _rename_checks() -> None:
    bind = op.get_bind()
    for item in _CHECK_RENAMES:
        table, target, needle = item[0], item[1], item[2]
        excluded = item[3] if len(item) > 3 else None
        rows = bind.execute(
            sa.text(
                """
                SELECT conname, pg_get_constraintdef(oid) AS constraint_def
                FROM pg_constraint
                WHERE conrelid = CAST(:table AS regclass) AND contype = 'c'
                """
            ),
            {"table": table},
        ).fetchall()
        by_name = {row.conname: row.constraint_def for row in rows}
        if target in by_name:
            continue
        matches = []
        for name, definition in by_name.items():
            text_def = definition.lower()
            if needle.lower() not in text_def:
                continue
            if excluded and excluded.lower() in text_def:
                continue
            if not name.replace("_", "").isalnum():
                continue
            matches.append(name)
        if len(matches) != 1:
            continue
        bind.execute(sa.text(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{matches[0]}" TO "{target}"'))


def _rename_uniques() -> None:
    bind = op.get_bind()
    for table, old_name, new_name in _UNIQUE_RENAMES:
        has_new = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint WHERE conrelid = CAST(:table AS regclass) AND conname = :name"
            ),
            {"table": table, "name": new_name},
        ).scalar()
        if has_new:
            continue
        has_old = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint WHERE conrelid = CAST(:table AS regclass) AND conname = :name"
            ),
            {"table": table, "name": old_name},
        ).scalar()
        if has_old:
            bind.execute(sa.text(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'))


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_matches_status_date ON matches (status, match_date)")
    op.execute("ALTER TABLE audit_logs ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    _rename_checks()
    _rename_uniques()
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'users_email_check' AND conrelid = 'users'::regclass
            ) THEN
                ALTER TABLE users
                ADD CONSTRAINT users_email_check CHECK (email = LOWER(BTRIM(email)));
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_matches_status_date")
    op.execute("ALTER TABLE audit_logs ALTER COLUMN id DROP DEFAULT")
