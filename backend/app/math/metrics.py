import math
from typing import List, Tuple, Dict, Any


def brier_score_multiclass(predictions: List[Tuple[float, float, float]], actuals: List[str]) -> float:
    """
    Multiclass Brier score: sum over three outcomes of squared probability error,
    averaged over matches.
    actuals: List of 'HOME', 'DRAW', or 'AWAY'
    """
    if not predictions or len(predictions) != len(actuals):
        raise ValueError("Predictions and actuals must have matching non-zero lengths.")

    total_error = 0.0
    for (ph, pd, pa), act in zip(predictions, actuals):
        yh = 1.0 if act == "HOME" else 0.0
        yd = 1.0 if act == "DRAW" else 0.0
        ya = 1.0 if act == "AWAY" else 0.0

        match_bs = (ph - yh) ** 2 + (pd - yd) ** 2 + (pa - ya) ** 2
        total_error += match_bs

    return total_error / len(predictions)


def log_loss_multiclass(predictions: List[Tuple[float, float, float]], actuals: List[str], eps: float = 1e-15) -> float:
    """
    Multiclass log loss: mean negative log probability of realized outcome.
    """
    if not predictions or len(predictions) != len(actuals):
        raise ValueError("Predictions and actuals must have matching non-zero lengths.")

    total_loss = 0.0
    for (ph, pd, pa), act in zip(predictions, actuals):
        if act == "HOME":
            p = max(eps, min(1.0, ph))
        elif act == "DRAW":
            p = max(eps, min(1.0, pd))
        elif act == "AWAY":
            p = max(eps, min(1.0, pa))
        else:
            raise ValueError(f"Unknown actual outcome: {act}")
        total_loss += -math.log(p)

    return total_loss / len(predictions)
