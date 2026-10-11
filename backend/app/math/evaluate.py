import asyncio
import math
from typing import Any, Dict, List, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.models import Match
from app.math.dixon_coles import fit_dixon_coles, calculate_match_distribution
from app.math.shin import calculate_shin_probabilities
from app.math.metrics import brier_score_multiclass, log_loss_multiclass
from app.math.freshness import latest_eligible_quote
from app.services.settings_service import load_quant_config

# Decay is chosen on an earlier window, then frozen for the held-out report.
XI_CANDIDATES = (0.001, 0.0018, 0.003)


def _score_block(
    train_matches: List[Match],
    test_matches: List[Match],
    xi: float,
    min_matches: int,
) -> Tuple[List[Tuple[Any, Any, str]], int]:
    """Fit once. Training rows must have a result strictly before the first test kickoff."""
    if not test_matches:
        return [], 0
    kickoff = min(match.match_date for match in test_matches)
    available = [
        match for match in train_matches
        if match.result_available_at is not None and match.result_available_at < kickoff
    ]
    excluded = 0
    team_list = sorted({
        team_id
        for match in available
        for team_id in (match.home_team_id, match.away_team_id)
    })
    train_tuples = [
        (
            match.home_team_id, match.away_team_id, match.home_score, match.away_score,
            match.match_date, match.result_available_at,
        )
        for match in available
    ]
    try:
        fit_res = fit_dixon_coles(
            matches=train_tuples,
            team_list=team_list,
            training_cutoff=kickoff,
            xi=xi,
            min_matches=min_matches,
        )
    except Exception as exc:
        print(f"Training failed for xi={xi}: {type(exc).__name__}")
        return [], len(test_matches)

    rows = []
    for tm in test_matches:
        attack = fit_res["team_attack"]
        defense = fit_res["team_defense"]
        if tm.home_team_id not in attack or tm.away_team_id not in attack:
            excluded += 1
            continue
        if tm.home_team_id not in defense or tm.away_team_id not in defense:
            excluded += 1
            continue
        quote = latest_eligible_quote(tm.odds_snapshots, tm.match_date)
        if not quote:
            excluded += 1
            continue

        actual = (
            "HOME"
            if tm.home_score > tm.away_score
            else "DRAW"
            if tm.home_score == tm.away_score
            else "AWAY"
        )
        lam = math.exp(attack[tm.home_team_id] - defense[tm.away_team_id] + fit_res["home_advantage"])
        mu = math.exp(attack[tm.away_team_id] - defense[tm.home_team_id])
        try:
            dist = calculate_match_distribution(lam, mu, fit_res["rho"])
            model_prob = (dist["prob_home_win"], dist["prob_draw"], dist["prob_away_win"])
        except Exception:
            excluded += 1
            continue
        try:
            baseline_prob, _, _ = calculate_shin_probabilities([
                float(quote.home_odds),
                float(quote.draw_odds),
                float(quote.away_odds),
            ])
        except ValueError:
            excluded += 1
            continue
        rows.append((model_prob, tuple(baseline_prob), actual))
    return rows, excluded


def _choose_xi(scored_by_xi: Dict[float, List[Tuple[Any, Any, str]]], fallback: float) -> float:
    best_xi = fallback
    best_brier = None
    for xi in XI_CANDIDATES:
        scored = scored_by_xi.get(xi) or []
        if not scored:
            continue
        brier = brier_score_multiclass([row[0] for row in scored], [row[2] for row in scored])
        if best_brier is None or brier < best_brier - 1e-12:
            best_brier = brier
            best_xi = xi
        elif abs(brier - best_brier) <= 1e-12 and xi == 0.0018:
            best_xi = xi
    return best_xi


async def run_chronological_evaluation():
    """
    Select a decay rate on an earlier window, then report one held-out period.

    The held-out fit is not repeated for every candidate, and a result is
    eligible only when result_available_at is strictly before the test kickoff.
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Match)
            .options(selectinload(Match.odds_snapshots))
            .where(
                Match.league_id == "EPL",
                Match.status == "FINISHED",
                Match.home_score.isnot(None),
                Match.away_score.isnot(None),
            )
            .order_by(Match.match_date.asc())
        )
        matches = (await session.execute(stmt)).scalars().all()
        matches = [match for match in matches if match.result_available_at is not None]
        matches.sort(key=lambda match: (match.match_date, match.id))

        quant = await load_quant_config(session)
        configured_xi = float(quant["dixon_coles_decay_xi"])
        min_matches = int(quant["min_training_matches"])
        n_total = len(matches)
        if n_total < max(20, min_matches + 2):
            print("Not enough finished matches for chronological evaluation.")
            return

        sel_start = max(int(n_total * 0.60), min(min_matches, n_total - 2))
        hold_start = max(int(n_total * 0.80), sel_start + 1)
        if hold_start >= n_total:
            hold_start = n_total - 1
        if sel_start >= hold_start:
            sel_start = max(0, hold_start - 1)

        selection = matches[sel_start:hold_start]
        heldout = matches[hold_start:]
        print("=" * 70)
        print("MatchLambda — Held-out Evaluation Report")
        print("=" * 70)
        print(f"Total Completed Matches: {n_total}")
        print(f"Selection window: {len(selection)} matches, indexes [{sel_start}, {hold_start})")
        print(f"Held-out window: {len(heldout)} matches, from {heldout[0].match_date.date()} to {heldout[-1].match_date.date()}")

        scored_by_xi = {}
        if selection:
            for xi in XI_CANDIDATES:
                scored, _excluded = _score_block(matches[:sel_start], selection, xi, min_matches)
                scored_by_xi[xi] = scored
                if scored:
                    brier = brier_score_multiclass([row[0] for row in scored], [row[2] for row in scored])
                    print(f"Selection xi={xi}: samples={len(scored)} brier={brier:.5f}")
        chosen_xi = _choose_xi(scored_by_xi, configured_xi)
        print(f"Chosen decay: xi = {chosen_xi} / day")
        print("-" * 70)

        scored, excluded = _score_block(matches[:hold_start], heldout, chosen_xi, min_matches)
        print(f"Held-out exclusions (missing team, quote, or distribution): {excluded}")
        if scored:
            model_preds = [row[0] for row in scored]
            market_preds = [row[1] for row in scored]
            actuals = [row[2] for row in scored]
            model_brier = brier_score_multiclass(model_preds, actuals)
            model_ll = log_loss_multiclass(model_preds, actuals)
            base_brier = brier_score_multiclass(market_preds, actuals)
            base_ll = log_loss_multiclass(market_preds, actuals)
            print(f"Evaluated Test Samples: {len(scored)}")
            print(f"Model Multiclass Brier Score: {model_brier:.5f} (Baseline: {base_brier:.5f})")
            print(f"Model Multiclass Log Loss:    {model_ll:.5f} (Baseline: {base_ll:.5f})")
            print("=" * 70)
            print("Evaluation completed successfully.")
        else:
            print("No held-out predictions could be evaluated.")


if __name__ == "__main__":
    asyncio.run(run_chronological_evaluation())
