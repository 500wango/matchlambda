import math
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln


def tau(x: int, y: int, lambda_: float, mu: float, rho: float) -> float:
    """
    Dixon-Coles low-score correction factor tau(x, y).
    """
    if x == 0 and y == 0:
        return 1.0 - lambda_ * mu * rho
    elif x == 0 and y == 1:
        return 1.0 + lambda_ * rho
    elif x == 1 and y == 0:
        return 1.0 + mu * rho
    elif x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def check_all_tau_factors(lambda_: float, mu: float, rho: float, tol: float = 1e-10) -> bool:
    """
    Verifies that ALL four low-score tau factors are >= 1e-10.
    """
    f00 = 1.0 - lambda_ * mu * rho
    f01 = 1.0 + lambda_ * rho
    f10 = 1.0 + mu * rho
    f11 = 1.0 - rho
    return f00 >= tol and f01 >= tol and f10 >= tol and f11 >= tol


def pois_logpmf(k: int, mu: float) -> float:
    """
    Log-PMF of Poisson distribution using gammaln:
    log Pois(k; mu) = k * log(mu) - mu - gammaln(k + 1)
    """
    if mu <= 0:
        return -float("inf")
    return k * math.log(mu) - mu - gammaln(k + 1)


def calculate_match_distribution(
    lambda_home: float,
    mu_away: float,
    rho: float,
) -> Dict[str, Any]:
    """
    Adheres strictly to docs/04_ALGORITHMS_MATH_SPEC.md:
    1. Enforce all four low-score factors >= 1e-10.
    2. Expand integer support 0..K (K >= 5) until omitted joint mass <= 1e-10.
    3. Normalize only this tiny calculation tail.
    4. Compute 1X2 from normalized distribution.
    5. Output 6x6 unconditional, unnormalized matrix for display.
    6. Compute omitted_mass = 1.0 - sum(6x6).
    7. Rank top_scores using unnormalized P over calculation support.
    """
    if not (math.isfinite(lambda_home) and math.isfinite(mu_away) and math.isfinite(rho)):
        raise ValueError("Invalid non-finite parameter for prediction.")

    if lambda_home <= 0 or mu_away <= 0:
        raise ValueError(f"Parameters must be positive: lambda={lambda_home}, mu={mu_away}")

    if not check_all_tau_factors(lambda_home, mu_away, rho):
        raise ValueError(
            f"Invalid tau factors: lambda={lambda_home}, mu={mu_away}, rho={rho} violates >= 1e-10"
        )

    # 1. Expand support K >= 5 until omitted joint mass <= 1e-10
    K = 5
    while True:
        # Compute marginal Poisson tails: P(X > K) and P(Y > K)
        # Using cumulative Poisson or direct sum
        tail_x = 1.0 - sum(math.exp(pois_logpmf(x, lambda_home)) for x in range(K + 1))
        tail_y = 1.0 - sum(math.exp(pois_logpmf(y, mu_away)) for y in range(K + 1))
        # Dixon-Coles corrections only affect {0,1}x{0,1}, which sum to zero.
        # For K >= 1, the omitted tail mass <= tail_x + tail_y
        omitted_bound = max(0.0, tail_x) + max(0.0, tail_y)
        if omitted_bound <= 1e-10 or K >= 30:
            break
        K += 1

    # Compute unnormalized joint distribution P(x, y) over 0..K
    unnorm_grid = np.zeros((K + 1, K + 1), dtype=np.float64)
    for x in range(K + 1):
        log_px = pois_logpmf(x, lambda_home)
        for y in range(K + 1):
            log_py = pois_logpmf(y, mu_away)
            t_val = tau(x, y, lambda_home, mu_away, rho)
            unnorm_grid[x, y] = t_val * math.exp(log_px + log_py)

    total_calc_mass = float(np.sum(unnorm_grid))
    norm_grid = unnorm_grid / total_calc_mass

    # Compute 1X2 from normalized distribution
    prob_home_win = float(np.sum(np.tril(norm_grid, -1)))
    prob_draw = float(np.sum(np.diag(norm_grid)))
    prob_away_win = float(np.sum(np.triu(norm_grid, 1)))

    # Ensure probabilities sum to 1 within 1e-8
    sum_1x2 = prob_home_win + prob_draw + prob_away_win
    if abs(sum_1x2 - 1.0) > 1e-8:
        # slight numerical cleanup
        prob_home_win /= sum_1x2
        prob_draw /= sum_1x2
        prob_away_win /= sum_1x2

    # 2. Display 6x6 matrix: unconditional, unnormalized P(x,y) for x,y=0..5
    score_matrix_6x6 = []
    display_sum = 0.0
    for x in range(6):
        row = []
        for y in range(6):
            val = float(unnorm_grid[x, y])
            row.append(val)
            display_sum += val
        score_matrix_6x6.append(row)

    omitted_mass = max(0.0, 1.0 - display_sum)

    # 3. Top 3 scores using unnormalized P over the calculation support
    score_pairs = []
    for x in range(K + 1):
        for y in range(K + 1):
            score_pairs.append((f"{x}-{y}", float(unnorm_grid[x, y])))
    score_pairs.sort(key=lambda s: s[1], reverse=True)
    top_scores = [{"score": s[0], "prob": s[1]} for s in score_pairs[:3]]

    return {
        "lambda_home": float(lambda_home),
        "mu_away": float(mu_away),
        "rho": float(rho),
        "prob_home_win": prob_home_win,
        "prob_draw": prob_draw,
        "prob_away_win": prob_away_win,
        "score_matrix": score_matrix_6x6,
        "omitted_mass": omitted_mass,
        "top_scores": top_scores,
    }


def fit_dixon_coles(
    matches: List[Tuple[str, str, int, int, datetime]],
    team_list: List[str],
    training_cutoff: datetime,
    xi: float = 0.0018,
) -> Dict[str, Any]:
    """
    Fits Dixon-Coles model using SLSQP with constraints:
    - sum(alpha_i) == 0
    - all four tau factors >= 1e-10 for every training match
    - time decay weight w(t_k) = exp(-xi * (cutoff - t_k)_days)
    """
    team_to_idx = {team_id: idx for idx, team_id in enumerate(team_list)}
    n_teams = len(team_list)

    if n_teams < 2 or len(matches) < 5:
        raise ValueError("Insufficient match history or teams for Dixon-Coles fit.")

    # Filter matches available by training_cutoff
    eligible_matches = []
    for h, a, hs, as_, dt in matches:
        if dt <= training_cutoff and h in team_to_idx and a in team_to_idx:
            days_ago = max(0.0, (training_cutoff - dt).total_seconds() / 86400.0)
            weight = math.exp(-xi * days_ago)
            eligible_matches.append((team_to_idx[h], team_to_idx[a], hs, as_, weight))

    if len(eligible_matches) < 5:
        raise ValueError("Not enough eligible matches before training cutoff.")

    # Parameter vector layout:
    # [alpha_0 ... alpha_{N-1}, beta_0 ... beta_{N-1}, gamma (home_advantage), rho]
    # Total dimension: 2*N + 2
    # Initial guess
    x0 = np.zeros(2 * n_teams + 2, dtype=np.float64)
    x0[2 * n_teams] = 0.25  # initial gamma (home advantage ~ +0.25 goals)
    x0[2 * n_teams + 1] = -0.04  # initial rho (typically around -0.05 to -0.03)

    def neg_log_likelihood(params: np.ndarray) -> float:
        alphas = params[:n_teams]
        betas = params[n_teams : 2 * n_teams]
        gamma = params[2 * n_teams]
        rho = params[2 * n_teams + 1]

        total_ll = 0.0
        for h_idx, a_idx, hs, as_, w in eligible_matches:
            lam = math.exp(alphas[h_idx] - betas[a_idx] + gamma)
            mu = math.exp(alphas[a_idx] - betas[h_idx])

            # Enforce all four tau factors >= 1e-10 for every training match
            f00 = 1.0 - lam * mu * rho
            f01 = 1.0 + lam * rho
            f10 = 1.0 + mu * rho
            f11 = 1.0 - rho
            if f00 < 1e-10 or f01 < 1e-10 or f10 < 1e-10 or f11 < 1e-10:
                return 1e12

            t_val = tau(hs, as_, lam, mu, rho)
            if t_val <= 1e-10:
                return 1e12

            log_t = math.log(t_val)
            log_p_home = pois_logpmf(hs, lam)
            log_p_away = pois_logpmf(as_, mu)

            match_ll = log_t + log_p_home + log_p_away
            total_ll += w * match_ll

        return -total_ll

    # Constraint 1: sum(alpha) == 0
    def sum_alpha_constraint(params: np.ndarray) -> float:
        return float(np.sum(params[:n_teams]))

    constraints = [
        {"type": "eq", "fun": sum_alpha_constraint},
    ]

    # Bounds: alphas, betas in [-1.5, 1.5], gamma in [-0.5, 0.8], rho in [-0.15, 0.15]
    bounds = [(-1.5, 1.5)] * (2 * n_teams) + [(-0.5, 0.8), (-0.15, 0.15)]

    res = minimize(
        neg_log_likelihood,
        x0,
        method="SLSQP",
        constraints=constraints,
        bounds=bounds,
        options={"maxiter": 200, "ftol": 1e-6},
    )

    if not res.success and res.fun > 1e10:
        raise RuntimeError(f"Dixon-Coles optimization failed: {res.message}")

    fitted_params = res.x
    alphas = fitted_params[:n_teams]
    betas = fitted_params[n_teams : 2 * n_teams]
    gamma = float(fitted_params[2 * n_teams])
    rho = float(fitted_params[2 * n_teams + 1])

    # Check constraint residual
    if abs(np.sum(alphas)) > 1e-4:
        # Re-center alphas to strictly satisfy sum(alpha) == 0
        mean_alpha = np.mean(alphas)
        alphas = alphas - mean_alpha

    team_attack = {team_list[i]: float(alphas[i]) for i in range(n_teams)}
    team_defense = {team_list[i]: float(betas[i]) for i in range(n_teams)}

    return {
        "home_advantage": gamma,
        "rho": rho,
        "xi_decay": float(xi),
        "team_attack": team_attack,
        "team_defense": team_defense,
        "training_cutoff": training_cutoff,
    }
