from typing import Tuple, List
import math
from scipy.optimize import brentq


def calculate_shin_probabilities(odds: List[float]) -> Tuple[List[float], float, str]:
    """
    Shin (1992, 1993) de-juicing algorithm adhering strictly to docs/04_ALGORITHMS_MATH_SPEC.md.
    Uses the numerically stable equivalent formulation:
    p_i(z) = (2 * pi_i^2 / S) / (sqrt(z^2 + 4 * (1 - z) * pi_i^2 / S) + z)
    
    Returns:
        (probabilities, z, method)
    """
    if len(odds) != 3:
        raise ValueError("Shin de-juicing requires exactly 3 outcomes (1X2).")

    for o in odds:
        if not math.isfinite(o) or o <= 1.0:
            raise ValueError(f"Odds must be finite and > 1.0, got {o}")

    inv_odds = [1.0 / o for o in odds]
    S = sum(inv_odds)

    # If within tolerance of fair market (|S - 1| <= 1e-12), return fair probabilities
    if abs(S - 1.0) <= 1e-12:
        probs = [p / S for p in inv_odds]
        return probs, 0.0, "FAIR"

    # Reject underround quotes
    if S < 1.0 - 1e-12:
        raise ValueError(f"Underround quote rejected (sum of implied probabilities S={S} < 1.0).")

    # pi_i^2 / S terms
    pi_sq_over_s = [(p ** 2) / S for p in inv_odds]

    def prob_i(z: float, term: float) -> float:
        radicand = z ** 2 + 4.0 * (1.0 - z) * term
        if radicand < 0:
            radicand = 0.0
        return (2.0 * term) / (math.sqrt(radicand) + z)

    def objective(z: float) -> float:
        total = sum(prob_i(z, t) for t in pi_sq_over_s)
        return total - 1.0

    # Solve sum(p_i(z)) - 1 = 0 on [0, 1 - 1e-15]
    # Check boundaries
    f0 = objective(0.0)
    # At z=0, sum(prob_i(0, term)) = sum(2 * term / (2 * sqrt(term))) = sum(sqrt(term)) = sum(pi_i / sqrt(S))
    # Since S > 1, sum(pi_i / sqrt(S)) = S / sqrt(S) = sqrt(S) > 1, so f0 > 0.
    
    # At z -> 1, prob_i(1) = 2 * term / (1 + 1) = term = pi_i^2 / S.
    # sum(pi_i^2) / S < (sum pi_i)^2 / S = S^2 / S = S. In fact sum(pi_i^2)/S < 1.
    f1 = objective(1.0 - 1e-10)

    # Bracket check by comparing signs rather than the product. Near S -> 1+ the
    # objective values are tiny and f0 * f1 can underflow to 0, which would look
    # like "not bracketed"; the sign comparison stays correct there.
    if (f0 > 0.0) == (f1 > 0.0):
        raise ValueError("Shin root is not bracketed for this quote.")

    z_root = brentq(objective, 0.0, 1.0 - 1e-10, xtol=1e-12, rtol=1e-12)

    if z_root >= 1.0 or z_root < 0.0:
        raise ValueError(f"Invalid Shin z parameter {z_root}, must be in [0, 1).")

    probs = [prob_i(z_root, t) for t in pi_sq_over_s]

    if any(not math.isfinite(p) or p < 0.0 or p > 1.0 for p in probs):
        raise ValueError("Shin probabilities are outside [0, 1].")

    # Verify root residual and sum error <= 1e-10
    residual = abs(objective(z_root))
    if residual > 1e-10:
        raise ValueError(f"Shin root residual {residual} > 1e-10")
    sum_p = sum(probs)
    if abs(sum_p - 1.0) > 1e-10:
        raise ValueError(f"Shin probabilities sum error {abs(sum_p - 1.0)} > 1e-10")

    return probs, float(z_root), "SHIN"
