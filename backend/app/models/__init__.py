import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Boolean, Integer, Numeric, Float, Text, ForeignKey,
    DateTime, CheckConstraint, UniqueConstraint, Index, text, desc,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    matches: Mapped[List["Match"]] = relationship("Match", back_populates="league")
    model_parameters: Mapped[List["ModelParameter"]] = relationship("ModelParameter", back_populates="league")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)

    aliases: Mapped[List["TeamAlias"]] = relationship("TeamAlias", back_populates="team")
    home_matches: Mapped[List["Match"]] = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches: Mapped[List["Match"]] = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")


class TeamAlias(Base):
    __tablename__ = "team_aliases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    external_name: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    team_id: Mapped[str] = mapped_column(String(64), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)

    team: Mapped["Team"] = relationship("Team", back_populates="aliases")

    __table_args__ = (
        Index("uq_alias_source_id", "source_name", "external_id", unique=True, postgresql_where=external_id.isnot(None)),
        Index("uq_alias_confirmed_name", "source_name", "country", "external_name", unique=True, postgresql_where=external_id.is_(None)),
    )


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    league_id: Mapped[str] = mapped_column(String(32), ForeignKey("leagues.id"), nullable=False)
    season: Mapped[str] = mapped_column(String(16), nullable=False)
    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    home_team_id: Mapped[str] = mapped_column(String(64), ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[str] = mapped_column(String(64), ForeignKey("teams.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="SCHEDULED", nullable=False)
    home_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result_available_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    league: Mapped["League"] = relationship("League", back_populates="matches")
    home_team: Mapped["Team"] = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team: Mapped["Team"] = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    sources: Mapped[List["MatchSource"]] = relationship("MatchSource", back_populates="match")
    odds_snapshots: Mapped[List["OddsSnapshot"]] = relationship("OddsSnapshot", back_populates="match")
    predictions: Mapped[List["Prediction"]] = relationship("Prediction", back_populates="match")

    __table_args__ = (
        CheckConstraint("status IN ('SCHEDULED', 'FINISHED', 'POSTPONED', 'CANCELLED', 'ABANDONED')", name="chk_match_status"),
        CheckConstraint("home_score >= 0", name="chk_match_home_score"),
        CheckConstraint("away_score >= 0", name="chk_match_away_score"),
        CheckConstraint("home_team_id <> away_team_id", name="chk_match_different_teams"),
        CheckConstraint(
            "(status = 'FINISHED' AND home_score IS NOT NULL AND away_score IS NOT NULL AND result_available_at IS NOT NULL AND result_available_at >= match_date) OR (status <> 'FINISHED' AND home_score IS NULL AND away_score IS NULL AND result_available_at IS NULL)",
            name="chk_match_result_consistency"
        ),
        Index("idx_matches_date_league", "match_date", "league_id"),
        Index("idx_matches_teams", "home_team_id", "away_team_id"),
        Index("idx_matches_status_date", "status", "match_date"),
    )


class MatchSource(Base):
    __tablename__ = "match_sources"

    source_name: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    match_id: Mapped[str] = mapped_column(String(64), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)

    match: Mapped["Match"] = relationship("Match", back_populates="sources")


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[str] = mapped_column(String(64), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(32), nullable=False)
    bookmaker: Mapped[str] = mapped_column(String(32), nullable=False)
    quote_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    home_odds: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    draw_odds: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    away_odds: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    dejuice_method: Mapped[str] = mapped_column(String(16), nullable=False)
    implied_prob_home: Mapped[float] = mapped_column(Float, nullable=False)
    implied_prob_draw: Mapped[float] = mapped_column(Float, nullable=False)
    implied_prob_away: Mapped[float] = mapped_column(Float, nullable=False)

    match: Mapped["Match"] = relationship("Match", back_populates="odds_snapshots")

    __table_args__ = (
        UniqueConstraint("source_name", "bookmaker", "match_id", "quote_at", name="uq_odds_snapshot"),
        CheckConstraint("home_odds > 1 AND home_odds < 1000000", name="chk_odds_home"),
        CheckConstraint("draw_odds > 1 AND draw_odds < 1000000", name="chk_odds_draw"),
        CheckConstraint("away_odds > 1 AND away_odds < 1000000", name="chk_odds_away"),
        CheckConstraint("dejuice_method IN ('SHIN', 'MULTIPLICATIVE', 'FAIR')", name="chk_odds_dejuice_method"),
        CheckConstraint("implied_prob_home BETWEEN 0 AND 1", name="chk_odds_prob_home"),
        CheckConstraint("implied_prob_draw BETWEEN 0 AND 1", name="chk_odds_prob_draw"),
        CheckConstraint("implied_prob_away BETWEEN 0 AND 1", name="chk_odds_prob_away"),
        CheckConstraint("quote_at <= recorded_at", name="chk_odds_quote_before_recorded"),
        CheckConstraint("ABS(implied_prob_home + implied_prob_draw + implied_prob_away - 1) <= 1e-8", name="chk_odds_prob_sum"),
        Index("idx_odds_match_time", "match_id", quote_at.desc()),
    )


class ModelParameter(Base):
    __tablename__ = "model_parameters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    league_id: Mapped[str] = mapped_column(String(32), ForeignKey("leagues.id"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    training_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    training_data_ref: Mapped[str] = mapped_column(Text, nullable=False)
    home_advantage: Mapped[float] = mapped_column(Float, nullable=False)
    rho: Mapped[float] = mapped_column(Float, nullable=False)
    xi_decay: Mapped[float] = mapped_column(Float, nullable=False)
    team_attack: Mapped[Dict[str, float]] = mapped_column(JSONB, nullable=False)
    team_defense: Mapped[Dict[str, float]] = mapped_column(JSONB, nullable=False)

    league: Mapped["League"] = relationship("League", back_populates="model_parameters")
    predictions: Mapped[List["Prediction"]] = relationship("Prediction", back_populates="model_parameters")

    __table_args__ = (
        # A deterministic training_data_ref means identical training data must
        # resolve to a single parameter row per league: the DB enforces that so
        # re-training can never grow the table without bound.
        UniqueConstraint("league_id", "training_data_ref", name="uq_model_param_league_ref"),
        CheckConstraint("xi_decay >= 0 AND xi_decay < 'Infinity'::float8", name="chk_model_xi_decay"),
        CheckConstraint("training_cutoff <= calculated_at", name="chk_model_training_cutoff"),
        CheckConstraint("jsonb_typeof(team_attack) = 'object'", name="chk_model_team_attack_object"),
        CheckConstraint("jsonb_typeof(team_defense) = 'object'", name="chk_model_team_defense_object"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[str] = mapped_column(String(64), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    model_parameters_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("model_parameters.id"), nullable=False)
    odds_snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("odds_snapshots.id"), nullable=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kickoff_at_prediction: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    lambda_home: Mapped[float] = mapped_column(Float, nullable=False)
    mu_away: Mapped[float] = mapped_column(Float, nullable=False)
    prob_home_win: Mapped[float] = mapped_column(Float, nullable=False)
    prob_draw: Mapped[float] = mapped_column(Float, nullable=False)
    prob_away_win: Mapped[float] = mapped_column(Float, nullable=False)
    score_matrix: Mapped[List[List[float]]] = mapped_column(JSONB, nullable=False)
    omitted_mass: Mapped[float] = mapped_column(Float, nullable=False)
    top_scores: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    match: Mapped["Match"] = relationship("Match", back_populates="predictions")
    model_parameters: Mapped["ModelParameter"] = relationship("ModelParameter", back_populates="predictions")
    odds_snapshot: Mapped[Optional["OddsSnapshot"]] = relationship("OddsSnapshot")

    __table_args__ = (
        UniqueConstraint("match_id", "as_of", name="uq_prediction_match_as_of"),
        CheckConstraint("lambda_home > 0 AND lambda_home < 'Infinity'::float8", name="chk_prediction_lambda_home"),
        CheckConstraint("mu_away > 0 AND mu_away < 'Infinity'::float8", name="chk_prediction_mu_away"),
        CheckConstraint("prob_home_win BETWEEN 0 AND 1", name="chk_prediction_prob_home"),
        CheckConstraint("prob_draw BETWEEN 0 AND 1", name="chk_prediction_prob_draw"),
        CheckConstraint("prob_away_win BETWEEN 0 AND 1", name="chk_prediction_prob_away"),
        CheckConstraint("omitted_mass BETWEEN 0 AND 1", name="chk_prediction_omitted_mass"),
        CheckConstraint("as_of < kickoff_at_prediction", name="chk_prediction_as_of_kickoff"),
        CheckConstraint("as_of <= generated_at AND generated_at < kickoff_at_prediction", name="chk_prediction_generated_at"),
        CheckConstraint("ABS(prob_home_win + prob_draw + prob_away_win - 1) <= 1e-8", name="chk_prediction_prob_sum"),
        CheckConstraint("jsonb_typeof(score_matrix) = 'array'", name="chk_prediction_score_matrix_array"),
        CheckConstraint("jsonb_typeof(top_scores) = 'array'", name="chk_prediction_top_scores_array"),
        Index("idx_predictions_match_time", "match_id", as_of.desc()),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    plan_tier: Mapped[str] = mapped_column(String(16), default="FREE", nullable=False)
    plan_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    invoices: Mapped[List["CryptoInvoice"]] = relationship("CryptoInvoice", back_populates="user")

    __table_args__ = (
        CheckConstraint("email = LOWER(BTRIM(email))", name="users_email_check"),
        CheckConstraint("plan_tier IN ('FREE', 'ANALYST')", name="chk_user_plan_tier"),
        CheckConstraint("plan_tier <> 'ANALYST' OR plan_expires_at IS NOT NULL", name="chk_user_analyst_expires"),
    )


class CryptoInvoice(Base):
    __tablename__ = "crypto_invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    request_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    gateway_invoice_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    checkout_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gateway_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(16), default="CREATING", nullable=False)
    credited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="invoices")

    __table_args__ = (
        UniqueConstraint("user_id", "request_key", name="uq_invoice_user_request"),
        CheckConstraint("plan_type IN ('PRO_DAY', 'PRO_WEEK', 'PRO_MONTHLY', 'PRO_SEASON')", name="chk_invoice_plan_type"),
        CheckConstraint("amount_usd > 0 AND amount_usd < 1000000", name="chk_invoice_amount"),
        CheckConstraint(
            "(plan_type = 'PRO_DAY' AND duration_days = 1) "
            "OR (plan_type = 'PRO_WEEK' AND duration_days = 7) "
            "OR (plan_type = 'PRO_MONTHLY' AND duration_days = 30) "
            "OR (plan_type = 'PRO_SEASON' AND duration_days = 270)",
            name="chk_invoice_plan_duration"
        ),
        CheckConstraint(
            "payment_status IN ('CREATING', 'PENDING', 'PAID', 'FAILED', 'EXPIRED', 'REVIEW')",
            name="chk_invoice_payment_status"
        ),
        CheckConstraint("(payment_status = 'PAID') = (credited_at IS NOT NULL)", name="chk_invoice_paid_credited"),
        CheckConstraint(
            "payment_status <> 'PAID' OR (gateway_invoice_id IS NOT NULL AND gateway_payment_id IS NOT NULL)",
            name="chk_invoice_paid_ids"
        ),
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_audit_logs_created_at", desc("created_at")),
    )

