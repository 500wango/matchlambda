import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.schemas.fixture import OutcomeItem


class TopScoreItem(BaseModel):
    score: str
    prob: float


class PredictionDetail(BaseModel):
    id: uuid.UUID
    model_parameters_id: uuid.UUID
    model_version: str
    training_cutoff: datetime
    as_of: datetime
    generated_at: datetime
    kickoff_at_prediction: datetime
    lambda_home: float
    mu_away: float
    rho: float
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    score_matrix: List[List[float]]
    omitted_mass: float
    top_scores: List[TopScoreItem]


class ComparisonDetail(BaseModel):
    odds_snapshot_id: uuid.UUID
    source_name: str
    bookmaker: str
    quote_at: datetime
    recorded_at: datetime
    dejuice_method: str
    overround: float
    has_value: bool
    outcomes: List[OutcomeItem]


class MatchAnalysisResponse(BaseModel):
    match_id: str
    data_status: str
    reason: Optional[str] = None
    prediction: Optional[PredictionDetail] = None
    comparison: Optional[ComparisonDetail] = None
