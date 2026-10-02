"""Initial schema 1.3.0 from 03_DATABASE_SCHEMA.sql

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-03 02:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE leagues (
        id VARCHAR(32) PRIMARY KEY,
        name VARCHAR(128) NOT NULL,
        country VARCHAR(64) NOT NULL,
        active BOOLEAN NOT NULL DEFAULT FALSE
    );

    CREATE TABLE teams (
        id VARCHAR(64) PRIMARY KEY,
        canonical_name VARCHAR(128) NOT NULL,
        country VARCHAR(64) NOT NULL
    );

    CREATE TABLE team_aliases (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source_name VARCHAR(32) NOT NULL,
        external_id VARCHAR(128),
        external_name VARCHAR(128) NOT NULL,
        country VARCHAR(64) NOT NULL,
        team_id VARCHAR(64) NOT NULL REFERENCES teams(id)
    );
    CREATE UNIQUE INDEX uq_alias_source_id
        ON team_aliases (source_name, external_id) WHERE external_id IS NOT NULL;
    CREATE UNIQUE INDEX uq_alias_confirmed_name
        ON team_aliases (source_name, country, external_name) WHERE external_id IS NULL;

    CREATE TABLE matches (
        id VARCHAR(64) PRIMARY KEY,
        league_id VARCHAR(32) NOT NULL REFERENCES leagues(id),
        season VARCHAR(16) NOT NULL,
        match_date TIMESTAMPTZ NOT NULL,
        home_team_id VARCHAR(64) NOT NULL REFERENCES teams(id),
        away_team_id VARCHAR(64) NOT NULL REFERENCES teams(id),
        status VARCHAR(16) NOT NULL DEFAULT 'SCHEDULED'
            CHECK (status IN ('SCHEDULED', 'FINISHED', 'POSTPONED', 'CANCELLED', 'ABANDONED')),
        home_score INT CHECK (home_score >= 0),
        away_score INT CHECK (away_score >= 0),
        result_available_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CHECK (home_team_id <> away_team_id),
        CHECK (
            (status = 'FINISHED' AND home_score IS NOT NULL AND away_score IS NOT NULL
                AND result_available_at IS NOT NULL AND result_available_at >= match_date)
            OR
            (status <> 'FINISHED' AND home_score IS NULL AND away_score IS NULL
                AND result_available_at IS NULL)
        )
    );
    CREATE INDEX idx_matches_date_league ON matches (match_date, league_id);
    CREATE INDEX idx_matches_teams ON matches (home_team_id, away_team_id);

    CREATE TABLE match_sources (
        source_name VARCHAR(32) NOT NULL,
        external_id VARCHAR(128) NOT NULL,
        match_id VARCHAR(64) NOT NULL REFERENCES matches(id),
        PRIMARY KEY (source_name, external_id)
    );

    CREATE TABLE odds_snapshots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        match_id VARCHAR(64) NOT NULL REFERENCES matches(id),
        source_name VARCHAR(32) NOT NULL,
        bookmaker VARCHAR(32) NOT NULL,
        quote_at TIMESTAMPTZ NOT NULL,
        recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        home_odds NUMERIC(12, 6) NOT NULL CHECK (home_odds > 1 AND home_odds < 1000000),
        draw_odds NUMERIC(12, 6) NOT NULL CHECK (draw_odds > 1 AND draw_odds < 1000000),
        away_odds NUMERIC(12, 6) NOT NULL CHECK (away_odds > 1 AND away_odds < 1000000),
        dejuice_method VARCHAR(16) NOT NULL CHECK (dejuice_method IN ('SHIN', 'MULTIPLICATIVE', 'FAIR')),
        implied_prob_home DOUBLE PRECISION NOT NULL CHECK (implied_prob_home BETWEEN 0 AND 1),
        implied_prob_draw DOUBLE PRECISION NOT NULL CHECK (implied_prob_draw BETWEEN 0 AND 1),
        implied_prob_away DOUBLE PRECISION NOT NULL CHECK (implied_prob_away BETWEEN 0 AND 1),
        UNIQUE (source_name, bookmaker, match_id, quote_at),
        CHECK (quote_at <= recorded_at),
        CHECK (ABS(implied_prob_home + implied_prob_draw + implied_prob_away - 1) <= 1e-8)
    );
    CREATE INDEX idx_odds_match_time ON odds_snapshots (match_id, quote_at DESC);

    CREATE TABLE model_parameters (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        league_id VARCHAR(32) NOT NULL REFERENCES leagues(id),
        model_version VARCHAR(64) NOT NULL,
        training_cutoff TIMESTAMPTZ NOT NULL,
        calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        training_data_ref TEXT NOT NULL,
        home_advantage DOUBLE PRECISION NOT NULL,
        rho DOUBLE PRECISION NOT NULL,
        xi_decay DOUBLE PRECISION NOT NULL CHECK (xi_decay >= 0 AND xi_decay < 'Infinity'::float8),
        team_attack JSONB NOT NULL CHECK (jsonb_typeof(team_attack) = 'object'),
        team_defense JSONB NOT NULL CHECK (jsonb_typeof(team_defense) = 'object'),
        CHECK (training_cutoff <= calculated_at)
    );

    CREATE TABLE predictions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        match_id VARCHAR(64) NOT NULL REFERENCES matches(id),
        model_parameters_id UUID NOT NULL REFERENCES model_parameters(id),
        odds_snapshot_id UUID REFERENCES odds_snapshots(id),
        as_of TIMESTAMPTZ NOT NULL,
        kickoff_at_prediction TIMESTAMPTZ NOT NULL,
        generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        lambda_home DOUBLE PRECISION NOT NULL CHECK (lambda_home > 0 AND lambda_home < 'Infinity'::float8),
        mu_away DOUBLE PRECISION NOT NULL CHECK (mu_away > 0 AND mu_away < 'Infinity'::float8),
        prob_home_win DOUBLE PRECISION NOT NULL CHECK (prob_home_win BETWEEN 0 AND 1),
        prob_draw DOUBLE PRECISION NOT NULL CHECK (prob_draw BETWEEN 0 AND 1),
        prob_away_win DOUBLE PRECISION NOT NULL CHECK (prob_away_win BETWEEN 0 AND 1),
        score_matrix JSONB NOT NULL CHECK (jsonb_typeof(score_matrix) = 'array'),
        omitted_mass DOUBLE PRECISION NOT NULL CHECK (omitted_mass BETWEEN 0 AND 1),
        top_scores JSONB NOT NULL CHECK (jsonb_typeof(top_scores) = 'array'),
        UNIQUE (match_id, as_of),
        CHECK (as_of < kickoff_at_prediction),
        CHECK (as_of <= generated_at AND generated_at < kickoff_at_prediction),
        CHECK (ABS(prob_home_win + prob_draw + prob_away_win - 1) <= 1e-8)
    );
    CREATE INDEX idx_predictions_match_time ON predictions (match_id, as_of DESC);

    CREATE TABLE users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) NOT NULL UNIQUE CHECK (email = LOWER(BTRIM(email))),
        password_hash TEXT NOT NULL,
        plan_tier VARCHAR(16) NOT NULL DEFAULT 'FREE' CHECK (plan_tier IN ('FREE', 'ANALYST')),
        plan_expires_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CHECK (plan_tier <> 'ANALYST' OR plan_expires_at IS NOT NULL)
    );

    CREATE TABLE crypto_invoices (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id),
        order_id VARCHAR(64) NOT NULL UNIQUE,
        request_key UUID NOT NULL,
        plan_type VARCHAR(32) NOT NULL CHECK (plan_type IN ('PRO_MONTHLY', 'PRO_SEASON')),
        amount_usd NUMERIC(10, 2) NOT NULL CHECK (amount_usd > 0 AND amount_usd < 1000000),
        duration_days INT NOT NULL CHECK (
            (plan_type = 'PRO_MONTHLY' AND duration_days = 30)
            OR (plan_type = 'PRO_SEASON' AND duration_days = 270)
        ),
        gateway_invoice_id VARCHAR(128) UNIQUE,
        gateway_payment_id VARCHAR(128) UNIQUE,
        checkout_url TEXT,
        valid_until TIMESTAMPTZ,
        gateway_status VARCHAR(32),
        payment_status VARCHAR(16) NOT NULL DEFAULT 'CREATING'
            CHECK (payment_status IN ('CREATING', 'PENDING', 'PAID', 'FAILED', 'EXPIRED', 'REVIEW')),
        credited_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (user_id, request_key),
        CHECK ((payment_status = 'PAID') = (credited_at IS NOT NULL)),
        CHECK (payment_status <> 'PAID' OR
            (gateway_invoice_id IS NOT NULL AND gateway_payment_id IS NOT NULL))
    );
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS crypto_invoices CASCADE;
    DROP TABLE IF EXISTS users CASCADE;
    DROP TABLE IF EXISTS predictions CASCADE;
    DROP TABLE IF EXISTS model_parameters CASCADE;
    DROP TABLE IF EXISTS odds_snapshots CASCADE;
    DROP TABLE IF EXISTS match_sources CASCADE;
    DROP TABLE IF EXISTS matches CASCADE;
    DROP TABLE IF EXISTS team_aliases CASCADE;
    DROP TABLE IF EXISTS teams CASCADE;
    DROP TABLE IF EXISTS leagues CASCADE;
    """)
