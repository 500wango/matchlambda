"""League eligibility gate (PRD §2.1).

A league only surfaces in the scanner, daily picks and parlay generator once
it passes coverage, quote-availability and held-out evaluation checks. The
snapshot is recomputed on a schedule and stored as a system setting so user
surfaces stay cheap to serve and every decision is auditable.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.math.shin import calculate_shin_probabilities
from app.math.metrics import brier_score_multiclass
from app.models import Match, OddsSnapshot, Prediction
from app.services.settings_service import get_system_setting, upsert_system_setting

logger = logging.getLogger(__name__)

GATE_CONFIG_KEY = "league_gate"
SNAPSHOT_KEY = "league_eligibility"

DEFAULT_LEAGUE_GATE = {
    "min_finished_matches": 300,
    "min_odds_coverage": 0.40,
    "min_eval_samples": 40,
    "max_brier_vs_market_ratio": 1.05,
    # Leagues approved on the 10-year dataset backtest run provisionally until
    # enough live DB predictions accumulate; the Brier ratio test then binds.
    "provisional_leagues": ["EPL", "CHAMPIONSHIP"],
}

# Upper bound on prediction rows loaded per recomputation.
_EVAL_ROW_CAP = 60000


async def load_gate_config(db: AsyncSession) -> Dict[str, Any]:
    cfg = await get_system_setting(db, GATE_CONFIG_KEY, DEFAULT_LEAGUE_GATE)
    merged = dict(DEFAULT_LEAGUE_GATE)
    if isinstance(cfg, dict):
        merged.update(cfg)
    return merged


async def compute_league_eligibility(db: AsyncSession) -> Dict[str, Any]:
    """Derive per-league metrics and pass/fail reasons from stored evidence."""
    thresholds = await load_gate_config(db)
    min_finished = int(thresholds["min_finished_matches"])
    min_coverage = float(thresholds["min_odds_coverage"])
    min_eval = int(thresholds["min_eval_samples"])
    max_ratio = float(thresholds["max_brier_vs_market_ratio"])

    # 1. Coverage and quote availability per league (single aggregate pass).
    pre_kickoff = (
        select(OddsSnapshot.id)
        .where(
            OddsSnapshot.match_id == Match.id,
            OddsSnapshot.quote_at <= Match.match_date,
        )
        .exists()
    )
    cov_stmt = (
        select(
            Match.league_id,
            func.count().label("finished"),
            func.count().filter(pre_kickoff).label("with_odds"),
        )
        .where(
            Match.status == "FINISHED",
            Match.home_score.isnot(None),
            Match.away_score.isnot(None),
        )
        .group_by(Match.league_id)
    )
    coverage_rows = (await db.execute(cov_stmt)).all()
    metrics: Dict[str, Dict[str, Any]] = {
        row.league_id: {
            "finished_matches": int(row.finished),
            "odds_coverage": round(int(row.with_odds) / int(row.finished), 4) if row.finished else 0.0,
        }
        for row in coverage_rows
    }

    # 2. Held-out evaluation evidence: latest stored prediction per finished
    #    match versus the Shin de-juiced baseline on the paired quote.
    eval_stmt = (
        select(
            Match.league_id,
            Match.id,
            Match.home_score,
            Match.away_score,
            Prediction.as_of,
            Prediction.prob_home_win,
            Prediction.prob_draw,
            Prediction.prob_away_win,
            OddsSnapshot.home_odds,
            OddsSnapshot.draw_odds,
            OddsSnapshot.away_odds,
        )
        .join(Prediction, Prediction.match_id == Match.id)
        .join(OddsSnapshot, OddsSnapshot.id == Prediction.odds_snapshot_id)
        .where(
            Match.status == "FINISHED",
            Match.home_score.isnot(None),
            Match.away_score.isnot(None),
        )
        .order_by(Match.match_date.desc(), Prediction.as_of.desc())
        .limit(_EVAL_ROW_CAP)
    )
    seen_match: Set[str] = set()
    model_probs: Dict[str, list] = {}
    market_probs: Dict[str, list] = {}
    actuals: Dict[str, list] = {}
    for row in (await db.execute(eval_stmt)).all():
        if row.id in seen_match:
            continue
        seen_match.add(row.id)
        actual = (
            "HOME" if row.home_score > row.away_score
            else "DRAW" if row.home_score == row.away_score
            else "AWAY"
        )
        try:
            baseline, _, _ = calculate_shin_probabilities([
                float(row.home_odds), float(row.draw_odds), float(row.away_odds),
            ])
        except (TypeError, ValueError):
            # A NULL or non-numeric price must skip only this row, not abort the
            # whole snapshot computation.
            continue
        lid = row.league_id
        model_probs.setdefault(lid, []).append(
            (row.prob_home_win, row.prob_draw, row.prob_away_win)
        )
        market_probs.setdefault(lid, []).append(tuple(baseline))
        actuals.setdefault(lid, []).append(actual)

    # 3. Live coverage: scheduled fixtures that already carry predictions.
    has_prediction = (
        select(Prediction.id)
        .where(Prediction.match_id == Match.id)
        .exists()
    )
    live_stmt = (
        select(
            Match.league_id,
            func.count().label("scheduled"),
            func.count().filter(has_prediction).label("with_preds"),
        )
        .where(Match.status == "SCHEDULED", Match.match_date >= datetime.now(timezone.utc))
        .group_by(Match.league_id)
    )
    live_rows = (await db.execute(live_stmt)).all()

    leagues = {}
    provisional_set = {str(x).strip().upper() for x in thresholds.get("provisional_leagues") or []}
    for lid, base in sorted(metrics.items(), key=lambda item: item[0]):
        reasons = []
        finished = base["finished_matches"]
        coverage = base["odds_coverage"]
        samples = len(actuals.get(lid, []))
        eval_error: Optional[str] = None
        model_brier = None
        market_brier = None
        if samples:
            # Isolate per league: one league's malformed predictions must not
            # abort the whole snapshot, and a failed evaluation must not leave
            # the league silently eligible.
            try:
                model_brier = brier_score_multiclass(model_probs[lid], actuals[lid])
            except Exception as exc:  # noqa: BLE001 - isolate any metric failure
                eval_error = f"model Brier failed: {exc}"
            try:
                market_brier = brier_score_multiclass(market_probs[lid], actuals[lid])
            except Exception as exc:  # noqa: BLE001
                eval_error = eval_error or f"market Brier failed: {exc}"
        if eval_error:
            logger.warning("league_gate: %s evaluation failed: %s", lid, eval_error)
        ratio = (
            round(model_brier / market_brier, 4)
            if model_brier is not None and market_brier not in (None, 0.0)
            else None
        )
        live = next((r for r in live_rows if r.league_id == lid), None)
        live_with_preds = int(live.with_preds) if live else 0

        if finished < min_finished:
            reasons.append(f"INSUFFICIENT_HISTORY: {finished} < {min_finished} finished matches")
        if coverage < min_coverage:
            reasons.append(f"QUOTE_COVERAGE: {coverage:.2%} < {min_coverage:.0%} of finished matches")
        if samples < min_eval:
            reasons.append(f"EVAL_SAMPLES: {samples} < {min_eval} evaluated predictions")
        elif eval_error:
            reasons.append(f"EVAL_ERROR: {eval_error}")
        elif ratio is not None and ratio > max_ratio:
            reasons.append(f"WORSE_THAN_MARKET: model Brier {ratio:.3f}x baseline > {max_ratio:.2f}x")
        if live is None or live_with_preds == 0:
            reasons.append("NO_LIVE_COVERAGE: no scheduled fixture carries a prediction")

        # Provisional basis: dataset-backtest leagues skip history/coverage/
        # sample-count failures only while live evidence is still thin. The
        # worse-than-market and live-coverage checks always bind.
        basis = "LIVE_EVIDENCE"
        if lid in provisional_set and samples < min_eval:
            provisional_prefixes = ("INSUFFICIENT_HISTORY", "QUOTE_COVERAGE", "EVAL_SAMPLES")
            dropped = [r for r in reasons if r.startswith(provisional_prefixes)]
            if dropped:
                reasons = [r for r in reasons if r not in dropped]
                basis = "PROVISIONAL_DATASET_BACKTEST"

        leagues[lid] = {
            "eligible": not reasons,
            "basis": basis,
            "reasons": reasons,
            "metrics": {
                "finished_matches": finished,
                "odds_coverage": coverage,
                "eval_samples": samples,
                "model_brier": round(model_brier, 5) if model_brier is not None else None,
                "market_brier": round(market_brier, 5) if market_brier is not None else None,
                "brier_ratio": ratio,
                "scheduled_with_predictions": live_with_preds,
            },
        }

    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": thresholds,
        "leagues": leagues,
    }


async def refresh_and_store_snapshot(db: AsyncSession) -> Dict[str, Any]:
    snapshot = await compute_league_eligibility(db)
    await upsert_system_setting(
        db,
        SNAPSHOT_KEY,
        snapshot,
        "League eligibility snapshot (PRD §2.1). Governs scanner/picks exposure.",
    )
    await db.commit()
    return snapshot


async def get_eligibility_snapshot(db: AsyncSession) -> Optional[Dict[str, Any]]:
    snapshot = await get_system_setting(db, SNAPSHOT_KEY, None)
    return snapshot if isinstance(snapshot, dict) else None


async def eligible_league_ids(db: AsyncSession) -> Set[str]:
    """The set of league ids that currently pass the gate. Fail-closed.

    If the snapshot is missing or malformed the gate cannot be evaluated, so this
    returns an empty set and logs an error. It deliberately never returns None:
    callers treat None as "gate inactive" and would let every league through,
    which is exactly the silent gate failure this contract forbids.
    """
    snapshot = await get_eligibility_snapshot(db)
    if not snapshot or not isinstance(snapshot.get("leagues"), dict):
        logger.error(
            "League eligibility snapshot (%s) is missing or malformed; failing "
            "closed with no eligible leagues. Recompute the snapshot.",
            SNAPSHOT_KEY,
        )
        return set()
    return {
        lid for lid, info in snapshot["leagues"].items()
        if isinstance(info, dict) and info.get("eligible")
    }
