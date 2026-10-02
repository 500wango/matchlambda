import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TeamInfo(BaseModel):
    id: str
    name: str


class OutcomeItem(BaseModel):
    outcome: str
    model_prob: float
    market_prob: float
    odds: float
    ev: float
    half_kelly: float


class PredictionSummary(BaseModel):
    id: uuid.UUID
    as_of: datetime
    lambda_home: float
    mu_away: float
    prob_home_win: float
    prob_draw: float
    prob_away_win: float


class ComparisonSummary(BaseModel):
    odds_snapshot_id: uuid.UUID
    bookmaker: str
    quote_at: datetime
    has_value: bool
    outcomes: List[OutcomeItem]


class FixtureItem(BaseModel):
    match_id: str
    league_id: str
    match_date: datetime
    home_team: TeamInfo
    away_team: TeamInfo
    status: str
    # Present only for active analyst pass
    data_status: Optional[str] = None
    reason: Optional[str] = None
    prediction: Optional[PredictionSummary] = None
    comparison: Optional[ComparisonSummary] = None


class FixturesResponse(BaseModel):
    total: int
    limit: int
    offset: int
    fixtures: List[FixtureItem]
