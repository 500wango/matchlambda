import math
from typing import Optional


def calculate_ev(prob: float, odds: float) -> float:
    """
    EV = p * O - 1
    """
    if not math.isfinite(prob) or not 0.0 <= prob <= 1.0:
        raise ValueError("Probability must be finite and within [0, 1].")
    if not math.isfinite(odds) or odds <= 1.0:
        raise ValueError("Decimal odds must be finite and greater than 1.")
    return prob * odds - 1.0


def calculate_half_kelly(prob: float, odds: float) -> float:
    """
    f_half = 0.5 * max(0, (p * O - 1) / (O - 1))
    """
    if not math.isfinite(prob) or not 0.0 <= prob <= 1.0:
        raise ValueError("Probability must be finite and within [0, 1].")
    if not math.isfinite(odds) or odds <= 1.0:
        raise ValueError("Decimal odds must be finite and greater than 1.")
    b = odds - 1.0
    ev = prob * odds - 1.0
    if ev <= 0.0:
        return 0.0
    kelly = ev / b
    # prob <= 1 implies kelly = (prob*odds - 1)/(odds - 1) <= 1, so
    # 0.5 * kelly <= 0.5 and a min(0.5, ...) clamp could never bind; the plain
    # half-Kelly fraction is already bounded.
    return 0.5 * max(0.0, kelly)


def has_value_signal(ev: float, threshold: float = 0.05) -> bool:
    """
    Unrounded EV >= 0.05 signal check.
    """
    return math.isfinite(ev) and ev >= threshold
