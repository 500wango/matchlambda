import pytest
import math
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from app.math.shin import calculate_shin_probabilities
from app.math.dixon_coles import (
    InsufficientTrainingDataError,
    calculate_match_distribution,
    check_all_tau_factors,
    tau,
    fit_dixon_coles,
)
from app.math.ev import calculate_ev, calculate_half_kelly, has_value_signal
from app.math.metrics import brier_score_multiclass, log_loss_multiclass
from app.math.freshness import latest_eligible_quote
from app.math.backtest import calculate_historical_backtest, calculate_dataset_backtest


def test_shin_fair_market():
    # Odds (3, 3, 3) -> S = 1.0, z = 0, probs = (1/3, 1/3, 1/3)
    probs, z, method = calculate_shin_probabilities([3.0, 3.0, 3.0])
    assert method == "FAIR"
    assert z == 0.0
    for p in probs:
        assert pytest.approx(1.0 / 3.0, abs=1e-8) == p


def test_shin_acceptance_example():
    # Odds (2, 3.5, 4): z approx 0.01789131177
    # probs approx (0.48673363476, 0.27432839612, 0.23893796911)
    probs, z, method = calculate_shin_probabilities([2.0, 3.5, 4.0])
    assert method == "SHIN"
    assert pytest.approx(0.01789131177, abs=1e-5) == z
    assert pytest.approx(0.48673363476, abs=1e-5) == probs[0]
    assert pytest.approx(0.27432839612, abs=1e-5) == probs[1]
    assert pytest.approx(0.23893796911, abs=1e-5) == probs[2]
    assert pytest.approx(1.0, abs=1e-10) == sum(probs)


def test_btts_yes_excludes_scoreless_tails():
    from app.math.derivatives import compute_derived_markets

    dist = calculate_match_distribution(0.2, 4.5, 0.0)
    derived = compute_derived_markets(
        dist["score_matrix"],
        0.2,
        4.5,
        dist["omitted_mass"],
        dist["prob_home_win"],
        dist["prob_draw"],
        dist["prob_away_win"],
    )
    expected = (1.0 - math.exp(-0.2)) * (1.0 - math.exp(-4.5))
    assert derived["btts"]["yes"]["prob"] == pytest.approx(expected, abs=0.02)


def test_dixon_coles_acceptance_distribution():
    # Lambda=1.78, mu=0.92, rho=0:
    # 0-5 display mass approx 0.989751770116 and omitted mass approx 0.010248229884
    dist = calculate_match_distribution(1.78, 0.92, 0.0)
    matrix = dist["score_matrix"]
    display_sum = sum(sum(row) for row in matrix)
    omitted = dist["omitted_mass"]

    assert pytest.approx(0.989751770116, abs=1e-5) == display_sum
    assert pytest.approx(0.010248229884, abs=1e-5) == omitted
    assert pytest.approx(1.0, abs=1e-8) == (dist["prob_home_win"] + dist["prob_draw"] + dist["prob_away_win"])

    # Check top scores are sorted descending and valid
    top = dist["top_scores"]
    assert len(top) == 3
    assert top[0]["prob"] >= top[1]["prob"] >= top[2]["prob"]
    assert top[0]["score"] == "1-0"


def test_dixon_coles_invalid_tau():
    # Lambda=mu=3, rho=0.2: invalid because tau(0,0)=-0.8
    assert not check_all_tau_factors(3.0, 3.0, 0.2)
    with pytest.raises(ValueError, match="violates >= 1e-10"):
        calculate_match_distribution(3.0, 3.0, 0.2)


def test_dixon_coles_rejects_unbounded_tail():
    with pytest.raises(ValueError, match="omitted mass"):
        calculate_match_distribution(50.0, 50.0, 0.0)


def test_dixon_coles_requires_convergence_and_available_results():
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    matches = []
    teams = ["a", "b", "c", "d"]
    for i in range(40):
        matches.append((teams[i % 4], teams[(i + 1) % 4], 1 + (i % 2), i % 2, base + timedelta(days=i), base + timedelta(days=100)))
    with pytest.raises(InsufficientTrainingDataError, match="Not enough eligible"):
        fit_dixon_coles(matches, teams, base + timedelta(days=40))


def test_dixon_coles_reports_thin_leagues_as_insufficient_data():
    """Too little history is an expected skip, not a defect.

    hourly_pipeline catches this specific type and logs a one-line warning
    instead of a full traceback on every tick, so it has to stay
    distinguishable from a genuine fit failure.
    """
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    matches = [
        ("a", "b", 1, 0, base + timedelta(days=i), base + timedelta(days=1))
        for i in range(3)
    ]
    with pytest.raises(InsufficientTrainingDataError, match="Insufficient match history"):
        fit_dixon_coles(matches, ["a", "b"], base + timedelta(days=10))
    # Handlers that only know ValueError must keep working.
    assert issubclass(InsufficientTrainingDataError, ValueError)


def test_market_baseline_uses_latest_quote_available_before_decision():
    decision_at = datetime(2025, 1, 2, 12, tzinfo=timezone.utc)
    quotes = [
        SimpleNamespace(quote_at=decision_at - timedelta(hours=14), recorded_at=decision_at - timedelta(hours=14)),
        SimpleNamespace(quote_at=decision_at - timedelta(hours=2), recorded_at=decision_at - timedelta(hours=1)),
        SimpleNamespace(quote_at=decision_at - timedelta(hours=1), recorded_at=decision_at + timedelta(seconds=1)),
        SimpleNamespace(quote_at=decision_at - timedelta(minutes=30), recorded_at=decision_at - timedelta(minutes=20)),
        SimpleNamespace(
            source_name="the_odds_api",
            bookmaker="pinnacle",
            home_odds=1.9,
            draw_odds=3.75,
            away_odds=4.5,
            quote_at=decision_at - timedelta(minutes=10),
            recorded_at=decision_at - timedelta(minutes=9, seconds=30),
        ),
    ]
    assert latest_eligible_quote(quotes, decision_at) is quotes[-2]


def test_historical_backtest_settles_eligible_prediction_and_distinguishes_no_bets():
    kickoff = datetime(2025, 5, 2, 15, tzinfo=timezone.utc)
    decision_at = kickoff - timedelta(hours=2)
    entry_quote = SimpleNamespace(
        source_name="book",
        bookmaker="testbook",
        quote_at=decision_at - timedelta(minutes=5),
        recorded_at=decision_at - timedelta(minutes=4),
        home_odds=1.9,
        draw_odds=3.8,
        away_odds=4.5,
    )
    closing_quote = SimpleNamespace(
        source_name="book",
        bookmaker="testbook",
        quote_at=kickoff - timedelta(minutes=5),
        recorded_at=kickoff - timedelta(minutes=4),
        home_odds=1.8,
        draw_odds=4.2,
        away_odds=5.2,
    )
    prediction = SimpleNamespace(
        as_of=decision_at,
        generated_at=decision_at + timedelta(seconds=1),
        kickoff_at_prediction=kickoff,
        model_parameters=SimpleNamespace(training_cutoff=decision_at - timedelta(days=1)),
        prob_home_win=0.6,
        prob_draw=0.22,
        prob_away_win=0.18,
    )
    match = SimpleNamespace(
        id="match-1",
        league_id="EPL",
        status="FINISHED",
        match_date=kickoff,
        result_available_at=kickoff + timedelta(hours=2),
        home_score=2,
        away_score=1,
        predictions=[prediction],
        odds_snapshots=[entry_quote, closing_quote],
    )

    result = calculate_historical_backtest([match], initial_bankroll=1000)
    assert result["status"] == "AVAILABLE"
    assert result["summary"]["total_bets"] == 1
    assert result["summary"]["final_bankroll"] == 1045
    assert result["recent_bets"][0]["beat_clv"] is True

    no_bets = calculate_historical_backtest([match], initial_bankroll=1000, max_ev=0.1)
    assert no_bets["status"] == "NO_BETS"
    assert no_bets["summary"]["total_bets"] == 0


def test_ev_and_half_kelly():
    prob = 0.5764915150
    odds = 1.90
    ev = calculate_ev(prob, odds)
    assert pytest.approx(0.0953338786, abs=1e-5) == ev
    assert has_value_signal(ev) is True

    hk = calculate_half_kelly(prob, odds)
    assert pytest.approx(0.0529632659, abs=1e-5) == hk

    # Negative EV
    ev_neg = calculate_ev(0.2, 3.0)  # 0.6 - 1 = -0.4
    assert ev_neg < 0
    assert has_value_signal(ev_neg) is False
    assert calculate_half_kelly(0.2, 3.0) == 0.0
    with pytest.raises(ValueError):
        calculate_ev(float("nan"), 2.0)
    with pytest.raises(ValueError):
        calculate_half_kelly(0.5, 1.0)


def test_metrics():
    preds = [(0.6, 0.3, 0.1), (0.2, 0.2, 0.6)]
    actuals = ["HOME", "AWAY"]
    bs = brier_score_multiclass(preds, actuals)
    # Match 1: (0.6-1)^2 + 0.3^2 + 0.1^2 = 0.16 + 0.09 + 0.01 = 0.26
    # Match 2: 0.2^2 + 0.2^2 + (0.6-1)^2 = 0.04 + 0.04 + 0.16 = 0.24
    # Mean: 0.25
    assert pytest.approx(0.25, abs=1e-6) == bs

    ll = log_loss_multiclass(preds, actuals)
    expected_ll = (-math.log(0.6) - math.log(0.6)) / 2
    assert pytest.approx(expected_ll, abs=1e-6) == ll

    with pytest.raises(ValueError, match="Unknown actual"):
        brier_score_multiclass([(0.3, 0.3, 0.4)], ["INVALID"])
    with pytest.raises(ValueError, match="sum to 1"):
        log_loss_multiclass([(0.3, 0.3, 0.3)], ["HOME"])


def test_dataset_historical_backtest_execution():
    res = calculate_dataset_backtest(
        initial_bankroll=10000.0,
        staking_strategy="HALF_KELLY",
        min_ev=0.04,
        max_ev=0.40,
        min_odds=1.30,
        max_odds=6.00,
        league_filter="EPL",
        years=3,
    )
    # Dataset-path status vocabulary (NO_BETS is retired on this path):
    #   AVAILABLE       -> ROI > 0 AND Brier improvement > 0
    #   MODEL_NO_EDGE   -> results computed but ROI <= 0 or Brier improvement <= 0
    #   DATA_UNAVAILABLE-> historical dataset missing/unparseable
    #   INSUFFICIENT_DATA -> no evaluable fixtures in the window
    # With the 10-year dataset present the walk-forward backtest is not
    # profitable, so this path reports MODEL_NO_EDGE.
    assert res["status"] in ("AVAILABLE", "MODEL_NO_EDGE")
    assert "summary" in res
    if res["status"] == "AVAILABLE":
        s = res["summary"]
        assert s["roi_pct"] > 0
        assert s["brier_improvement_pct"] is not None and s["brier_improvement_pct"] > 0
        assert s["total_bets"] > 0
        assert s["total_staked"] > 0
        assert s["win_rate_pct"] > 0
        assert s["beat_clv_rate_pct"] is None or 0.0 <= s["beat_clv_rate_pct"] <= 100.0
        assert "Dixon-Coles" not in res["method"] or "not Dixon-Coles" in res["method"]
        assert res["probability_source"] == "POISSON_TEAM_RATES"
        assert res["price_source"] == "PINNACLE_OPENING"
        assert len(res["equity_curve"]) > 0
        assert len(res["recent_bets"]) > 0
        # Check CLV structure on recent bets
        first_bet = res["recent_bets"][0]
        assert "beat_clv" in first_bet
        assert "odds" in first_bet
        assert "closing_odds" in first_bet
    else:
        s = res["summary"]
        # MODEL_NO_EDGE requires the model to be flat-or-losing and/or no better
        # than the de-juiced market baseline.
        assert s["roi_pct"] <= 0 or (
            s["brier_improvement_pct"] is not None and s["brier_improvement_pct"] <= 0
        )
