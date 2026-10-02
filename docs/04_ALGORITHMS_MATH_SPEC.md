# MatchLambda — Mathematical Contract

All inputs are regulation-time EPL results. This document owns formulas and precision; model fitting and provider access remain to be implemented.

## 1. Dixon–Coles score model

This is a product of Poisson marginals with a low-score dependence correction, not a general shared-component bivariate Poisson model.

For home team i and away team j:

$$\lambda=\exp(\alpha_i-\beta_j+\gamma),\qquad
\mu=\exp(\alpha_j-\beta_i).$$

Attack alpha increases scoring; **defensive strength beta increases resistance** (larger beta reduces the opponent's goal rate). Gamma is log home advantage. Impose exactly $\sum_i\alpha_i=0$ to identify the parameters. Store alpha/beta on this log scale, not as multiplicative strengths.

$$\tau(x,y)=\begin{cases}
1-\lambda\mu\rho &(0,0)\\
1+\lambda\rho &(0,1)\\
1+\mu\rho &(1,0)\\
1-\rho &(1,1)\\
1 &\text{otherwise}.
\end{cases}$$

$$P(x,y)=\tau(x,y)\operatorname{Pois}(x;\lambda)\operatorname{Pois}(y;\mu).$$

Nonnegative mass requires
$$\max(-1/\lambda,-1/\mu)\le\rho\le\min(1/(\lambda\mu),1).$$

For optimization, enforce **all four** low-score factors >= 1e-10 for every training match, not just its observed score. Check all four again for each predicted fixture; new teams, invalid factors or non-finite parameters yield an unavailable prediction. Never repair an invalid distribution by clipping its negative cells.

Let the training cutoff be T and the kickoff time be t, with elapsed time measured in **days**:

$$w(t)=\exp[-\xi(T-t)],\qquad \xi=0.0018\ {\rm day}^{-1}.$$

This is an initial decay rate, with half-life $\ln(2)/\xi\approx385$ days, not a calibrated universal optimum. Include only completed results available by T.

Maximize
$$\sum_k w(t_k)\left[\log\tau(x_k,y_k)+\log\operatorname{Pois}(x_k;\lambda_k)+\log\operatorname{Pois}(y_k;\mu_k)\right].$$

Use log-PMF/log-gamma arithmetic directly, not a product of tiny PMFs followed by log. SLSQP may be used with the equality and per-match positivity constraints. Check convergence, finite objective and constraint residuals before persisting parameters. An unconstrained L-BFGS-B call or a penalty on observed tau alone does not implement this contract. Record fitting configuration with the immutable training artifact; do not publish a failed optimization as a new model.

ClubElo priors, promoted-team priors and residual ML are deferred. If current teams lack sufficient connected training history for the chosen window, publish unavailable rather than inventing strengths.

## 2. Bookmaker de-juicing

For one complete, simultaneous bookmaker 1X2 quote, let $\pi_i=1/O_i$ and $S=\sum_i\pi_i$. Odds must be finite and > 1. Store overround as the fraction $S-1$, not percentage points.

Multiplicative estimate: $p_i=\pi_i/S$.

Shin estimate:
$$p_i(z)=\frac{\sqrt{z^2+4(1-z)\pi_i^2/S}-z}{2(1-z)}.$$

Solve $\sum_i p_i(z)-1=0$ for $0\le z<1$. For three outcomes the equivalent square-root equation has right-hand side $2+z$, but do not use its spurious z=1 endpoint.

For numerical stability use the equivalent form
$$p_i(z)=\frac{2\pi_i^2/S}{\sqrt{z^2+4(1-z)\pi_i^2/S}+z}.$$

This form has a finite limit at z=1 and allows a bracketed solve on [0,1]; the returned root must be < 1. If $|S-1|\le10^{-12}$, return the fair-market estimate $\pi_i/S$ with z=0. If S is below that range, reject Shin as an underround quote for this release. Do not silently switch methods or force an arbitrary z.

Persist the actual method (SHIN, MULTIPLICATIVE or FAIR). Require finite probabilities in [0,1], a root residual <= 1e-10 and sum error <= 1e-10 before serialization. The first release selects SHIN except for the FAIR case. These are market estimates, not objective truth.

Reference implementation used to cross-check the squared-inverse-odds term:
https://raw.githubusercontent.com/mberk/shin/master/python/shin/__init__.py

## 3. Calculation distribution versus display

- Increase integer support 0..K (K >= 5) until omitted joint mass is <= 1e-10. The four DC corrections sum to zero when all four cells are included; Poisson marginal tail bounds therefore apply.
- Validate nonnegative cells and the support sum before normalizing only this tiny calculation tail. Compute home/draw/away from x>y, x=y and x<y respectively, using the same normalized calculation distribution.
- The displayed 6×6 matrix is the **unconditional**, unnormalized P(x,y) for x,y=0..5. Rows are home goals; columns are away goals. Report omitted_mass = 1 minus its sum. Do not normalize this display window or derive 1X2 solely from it.
- Rank top_scores using unnormalized P over the calculation support; displayed cells and corresponding top-score values must agree. A top score may be outside the display window.
- Calculate in float64. Serialize probabilities to 10 decimal places; allow 1e-8 sum error after rounding. Do not round before EV or threshold decisions.

## 4. EV and Half-Kelly

For the selected, fresh bookmaker's decimal odds O and model probability p:

$$EV=pO-1,\qquad f_{\text{half}}=\tfrac12\max(0,(pO-1)/(O-1)).$$

A signal requires unrounded EV >= 0.05 and the ETL eligibility/freshness checks. The compared quote snapshot is fixed at the prediction cutoff. Do not use midpoint or lay prices as executable back odds; exchange EV and commission are outside this release. One bookmaker's quote is not a claim about market-wide best odds.

## 5. Evaluation and numerical acceptance

Use expanding chronological training/validation folds. Select decay settings within earlier folds, then report a held-out period with dates, sample count, training artifact and missing-data exclusions. Multiclass Brier score is the **sum over three outcomes** of squared probability error, averaged over matches; log loss is mean negative log probability of the realized outcome. Compare with an eligible de-juiced market baseline on the same matches/timestamps. No profitability or predictive superiority is assumed.

Historical input availability follows the ETL contract. Results-only evaluation does not validate historical execution prices.

Minimal numeric acceptance examples:
- Odds (3,3,3): z=0 and probabilities (1/3,1/3,1/3).
- Odds (2,3.5,4): z approximately 0.01789131177; probabilities approximately (0.48673363476,0.27432839612,0.23893796911).
- Lambda=1.78, mu=0.92, rho=0: 0–5 display mass approximately 0.989751770116 and omitted mass approximately 0.010248229884.
- Lambda=mu=3, rho=0.2: invalid because tau(0,0)=-0.8, even if the observed training result is 2–2.
