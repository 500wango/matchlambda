import math
from typing import Optional


def calculate_ev(prob: float, odds: float) -> float:
    """
    EV = p * O - 1
    """
    if not math.isfinite(prob) or not math.isfinite(odds):
        return 0.0
    return prob * odds - 1.0


def calculate_half_kelly(prob: float, odds: float) -> float:
    """
    f_half = 0.5 * max(0, (p * O - 1) / (O - 1))
    """
    if not math.isfinite(prob) or not math.isfinite(odds) or odds <= 1.0:
        return 0.0
    b = odds - 1.0
    ev = prob * odds - 1.0
    if ev <= 0.0:
        return 0.0
    kelly = ev / b
    return min(0.5, 0.5 * max(0.0, kelly))


def has_value_signal(ev: float, threshold: float = 0.05) -> bool:
    """
    Unrounded EV >= 0.05 signal check.
    """
    return math.isfinite(ev) and ev >= threshold
