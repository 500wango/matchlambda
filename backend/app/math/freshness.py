import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.models import OddsSnapshot

logger = logging.getLogger(__name__)


# Placeholder quotes are synthetic; tolerate sub-second/rounding differences.
_PLACEHOLDER_MAX_GAP = timedelta(seconds=60)


def is_placeholder_quote(quote: OddsSnapshot) -> bool:
    recorded_at = getattr(quote, "recorded_at", None)
    quote_at = getattr(quote, "quote_at", None)
    if recorded_at is None or quote_at is None:
        return False
    return (
        getattr(quote, "source_name", None) == "the_odds_api"
        and getattr(quote, "bookmaker", "").lower() == "pinnacle"
        and abs(float(getattr(quote, "home_odds", 0)) - 1.9) < 1e-9
        and abs(float(getattr(quote, "draw_odds", 0)) - 3.75) < 1e-9
        and abs(float(getattr(quote, "away_odds", 0)) - 4.5) < 1e-9
        and 0 < (recorded_at - quote_at).total_seconds() <= _PLACEHOLDER_MAX_GAP.total_seconds()
    )


def latest_eligible_quote(
    quotes: List[OddsSnapshot],
    decision_at: datetime,
    max_age: timedelta = timedelta(hours=13),
) -> Optional[OddsSnapshot]:
    cutoff = decision_at - max_age
    disordered = 0
    eligible = []
    for quote in quotes:
        if is_placeholder_quote(quote):
            continue
        quote_at = getattr(quote, "quote_at", None)
        recorded_at = getattr(quote, "recorded_at", None)
        if quote_at is None or recorded_at is None:
            continue
        if recorded_at < quote_at:
            disordered += 1
            continue
        if cutoff <= quote_at <= recorded_at <= decision_at:
            eligible.append(quote)
    if disordered:
        logger.warning("Dropped %s odds quotes with recorded_at before quote_at", disordered)
    return max(eligible, key=lambda quote: quote.quote_at, default=None)
