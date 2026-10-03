import asyncio
import math
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.models import Match, OddsSnapshot
from app.math.dixon_coles import fit_dixon_coles, calculate_match_distribution
from app.math.shin import calculate_shin_probabilities
from app.math.metrics import brier_score_multiclass, log_loss_multiclass
from app.math.freshness import latest_eligible_quote


async def run_chronological_evaluation():
    """
    Executes expanding chronological folds evaluation adhering to docs/04_ALGORITHMS_MATH_SPEC.md.
    Reports Brier score and Log Loss for both Dixon-Coles and Market/Baseline on held-out matches.
    """
    async with AsyncSessionLocal() as session:
        # Load all finished matches ordered chronologically
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
        matches = [m for m in matches if m.result_available_at is not None]
        matches.sort(key=lambda m: (m.match_date, m.id))

        if len(matches) < 20:
            print("Not enough finished matches for chronological folds (need >= 20).")
            return

        # Split into expanding folds: e.g. train on first 60%, test on remaining 40% in batches
        n_total = len(matches)
        train_initial_size = int(n_total * 0.6)
        fold_test_size = 5

        print("=" * 70)
        print("MatchLambda — Chronological Expanding Folds Evaluation Report")
        print("=" * 70)
        print(f"Total Completed Matches: {n_total}")
        print(f"Unique Teams: {len({team_id for m in matches for team_id in (m.home_team_id, m.away_team_id)})}")
        print(f"Initial Training Size: {train_initial_size}")
        print(f"Time Decay Parameter: xi = 0.0018 / day")
        print("-" * 70)

        all_model_preds = []
        all_market_preds = []
        all_actuals = []

        fold_idx = 1
        current_train_end = train_initial_size

        while current_train_end < n_total:
            test_end = min(n_total, current_train_end + fold_test_size)
            train_matches = matches[:current_train_end]
            test_matches = matches[current_train_end:test_end]

            train_cutoff = test_matches[0].match_date
            available_train_matches = [
                m for m in train_matches
                if m.match_date <= train_cutoff and m.result_available_at <= train_cutoff
            ]
            team_list = sorted({
                team_id
                for match in available_train_matches
                for team_id in (match.home_team_id, match.away_team_id)
            })

            train_tuples = [
                (
                    m.home_team_id, m.away_team_id, m.home_score, m.away_score,
                    m.match_date, m.result_available_at,
                )
                for m in available_train_matches
            ]

            try:
                fit_res = fit_dixon_coles(
                    matches=train_tuples,
                    team_list=team_list,
                    training_cutoff=train_cutoff,
                    xi=0.0018,
                )
            except Exception as e:
                print(f"Fold {fold_idx} training failed: {e}")
                current_train_end = test_end
                fold_idx += 1
                continue

            # Predict on test matches
            for tm in test_matches:
                if tm.home_team_id not in fit_res["team_attack"] or tm.away_team_id not in fit_res["team_attack"]:
                    continue
                quote = latest_eligible_quote(tm.odds_snapshots, tm.match_date)
                if not quote:
                    continue

                actual = (
                    "HOME"
                    if tm.home_score > tm.away_score
                    else "DRAW"
                    if tm.home_score == tm.away_score
                    else "AWAY"
                )

                home_att = fit_res["team_attack"].get(tm.home_team_id, 0.0)
                home_def = fit_res["team_defense"].get(tm.home_team_id, 0.0)
                away_att = fit_res["team_attack"].get(tm.away_team_id, 0.0)
                away_def = fit_res["team_defense"].get(tm.away_team_id, 0.0)

                lam = math.exp(home_att - away_def + fit_res["home_advantage"])
                mu = math.exp(away_att - home_def)

                try:
                    dist = calculate_match_distribution(lam, mu, fit_res["rho"])
                    m_prob = (dist["prob_home_win"], dist["prob_draw"], dist["prob_away_win"])
                except Exception:
                    continue

                try:
                    baseline_prob, _, _ = calculate_shin_probabilities([
                        float(quote.home_odds),
                        float(quote.draw_odds),
                        float(quote.away_odds),
                    ])
                except ValueError:
                    continue
                baseline_prob = tuple(baseline_prob)

                all_model_preds.append(m_prob)
                all_market_preds.append(baseline_prob)
                all_actuals.append(actual)

            print(
                f"Fold {fold_idx}: Trained on {len(train_matches)} matches -> Tested on {len(test_matches)} matches (Cutoff: {train_cutoff.strftime('%Y-%m-%d')})"
            )
            current_train_end = test_end
            fold_idx += 1

        print("-" * 70)
        if all_model_preds:
            model_brier = brier_score_multiclass(all_model_preds, all_actuals)
            model_ll = log_loss_multiclass(all_model_preds, all_actuals)

            base_brier = brier_score_multiclass(all_market_preds, all_actuals)
            base_ll = log_loss_multiclass(all_market_preds, all_actuals)

            print(f"Evaluated Test Samples: {len(all_model_preds)}")
            print(f"Model Multiclass Brier Score: {model_brier:.5f} (Baseline: {base_brier:.5f})")
            print(f"Model Multiclass Log Loss:    {model_ll:.5f} (Baseline: {base_ll:.5f})")
            print("=" * 70)
            print("Evaluation completed successfully.")
        else:
            print("No test predictions could be evaluated.")


if __name__ == "__main__":
    asyncio.run(run_chronological_evaluation())
