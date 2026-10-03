from datetime import datetime, timedelta
from typing import List, Optional

from app.models import OddsSnapshot


def is_placeholder_quote(quote: OddsSnapshot) -> bool:
    return (
        getattr(quote, "source_name", None) == "the_odds_api"
        and getattr(quote, "bookmaker", "").lower() == "pinnacle"
        and abs(float(getattr(quote, "home_odds", 0)) - 1.9) < 1e-9
        and abs(float(getattr(quote, "draw_odds", 0)) - 3.75) < 1e-9
        and abs(float(getattr(quote, "away_odds", 0)) - 4.5) < 1e-9
        and quote.recorded_at - quote.quote_at == timedelta(seconds=30)
    )


def latest_eligible_quote(
    quotes: List[OddsSnapshot],
    decision_at: datetime,
    max_age: timedelta = timedelta(hours=13),
) -> Optional[OddsSnapshot]:
    cutoff = decision_at - max_age
    eligible = [
        quote for quote in quotes
        if not is_placeholder_quote(quote)
        and cutoff <= quote.quote_at <= quote.recorded_at <= decision_at
    ]
    return max(eligible, key=lambda quote: quote.quote_at, default=None)
