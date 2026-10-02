import pytest
import math
from app.math.shin import calculate_shin_probabilities
from app.math.dixon_coles import calculate_match_distribution, check_all_tau_factors, tau
from app.math.ev import calculate_ev, calculate_half_kelly, has_value_signal
from app.math.metrics import brier_score_multiclass, log_loss_multiclass


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
