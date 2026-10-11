"""Staking fraction helpers.

`staking_strategy` alone fixes how much of full Kelly is staked:

- ``FULL_KELLY``    -> 1.00 x full Kelly
- ``HALF_KELLY``    -> 0.50 x full Kelly
- ``QUARTER_KELLY`` -> 0.25 x full Kelly
- ``FIXED_1_PCT``   -> 1% of bankroll
- ``FLAT_UNIT``     -> 1.5% of bankroll

The admin ``kelly_fraction`` setting is accepted for API stability but does not
redefine these named fractions. Previously ``HALF_KELLY`` read it directly while
``FULL_KELLY`` ignored it, so ``kelly_fraction=0.25`` silently turned
"HALF_KELLY" into quarter Kelly even though the name promises half. The strategy
name is now the single source of truth, so every name means exactly what it says
regardless of the configured value.
"""
from typing import Optional

# Hard ceilings so a missing or loose config cannot stake a third of the bankroll.
STRATEGY_HARD_CAP = {
    "FULL_KELLY": 0.08,
    "HALF_KELLY": 0.05,
    "QUARTER_KELLY": 0.025,
    "FIXED_1_PCT": 0.01,
    "FLAT_UNIT": 0.015,
}


def capped_kelly_fraction(
    full_kelly: float,
    strategy: str,
    kelly_fraction: Optional[float] = None,
    max_stake_cap: Optional[float] = None,
) -> float:
    """Stake as a fraction of bankroll, never above the tighter of the config cap and the strategy ceiling.

    ``kelly_fraction`` is retained for callers/API compatibility and is
    intentionally not used: the named strategy selects the fraction (see the
    module docstring). ``max_stake_cap`` is an absolute config ceiling applied on
    top of the strategy's own ``STRATEGY_HARD_CAP``.
    """
    if strategy not in STRATEGY_HARD_CAP:
        raise ValueError(f"Unsupported staking strategy: {strategy}")
    full_kelly = max(0.0, full_kelly)
    cap = min(max(0.0, max_stake_cap or 0.0), STRATEGY_HARD_CAP[strategy])
    if strategy == "FULL_KELLY":
        portion = full_kelly
    elif strategy == "HALF_KELLY":
        portion = 0.5 * full_kelly
    elif strategy == "QUARTER_KELLY":
        portion = 0.25 * full_kelly
    elif strategy == "FIXED_1_PCT":
        portion = 0.01
    elif strategy == "FLAT_UNIT":
        portion = 0.015
    else:
        raise ValueError(f"Unsupported staking strategy: {strategy}")
    return min(cap, portion)
