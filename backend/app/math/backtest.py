import math
import csv
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.math.freshness import latest_eligible_quote
from app.math.freshness import is_placeholder_quote
from app.math.shin import calculate_shin_probabilities
from app.models import Match, Prediction


class BacktestRequest(BaseModel):
    initial_bankroll: float = 10000.0
    staking_strategy: str = "HALF_KELLY"
    min_ev: float = 0.05
    max_ev: float = 0.40
    min_odds: float = 1.30
    max_odds: float = 7.00
    league_id: Optional[str] = None


def _actual_outcome(match: Match) -> str:
    if match.home_score > match.away_score:
        return "HOME"
    if match.home_score == match.away_score:
        return "DRAW"
    return "AWAY"


def _stake_amount(
    bankroll: float,
    initial_bankroll: float,
    odds: float,
    ev: float,
    strategy: str,
    kelly_fraction: Optional[float] = None,
    max_stake_cap: Optional[float] = None,
) -> float:
    """One staking path. The strategy name picks the Kelly fraction; a missing cap uses 5%."""
    from app.math.staking import capped_kelly_fraction

    full_kelly = max(0.0, ev / (odds - 1.0)) if odds > 1.0 else 0.0
    portion = capped_kelly_fraction(
        full_kelly,
        strategy,
        kelly_fraction,
        0.05 if max_stake_cap is None else max_stake_cap,
    )
    base = initial_bankroll if strategy == "FLAT_UNIT" else bankroll
    return min(bankroll, base * portion)


def _empty_result(initial_bankroll: float) -> Dict[str, Any]:
    return {
        "status": "INSUFFICIENT_DATA",
        "message": "No finished matches have an eligible stored prediction and pre-kickoff quote.",
        "summary": None,
        "equity_curve": [],
        "recent_bets": [],
        "sample": {"fixtures": 0, "bets": 0},
    }


def _dataset_unavailable_result(initial_bankroll: float, years: int) -> Dict[str, Any]:
    """Historical CSV is missing or could not be parsed: report it, do not fake success."""
    return {
        "status": "DATA_UNAVAILABLE",
        "dataset_name": f"England 10-Year Historical Combined ({years}Y)",
        "message": "Historical dataset file is missing or could not be parsed.",
        "summary": None,
        "equity_curve": [],
        "recent_bets": [],
        "sample": {"fixtures": 0, "bets": 0},
        "method": "Walk-forward Poisson team-rate model over the combined historical CSV.",
        "probability_source": "POISSON_TEAM_RATES",
        "price_source": "PINNACLE_OPENING",
    }


def calculate_historical_backtest(
    matches: List[Match],
    initial_bankroll: float = 10000.0,
    staking_strategy: str = "HALF_KELLY",
    min_ev: float = 0.05,
    max_ev: float = 0.40,
    min_odds: float = 1.30,
    max_odds: float = 7.00,
    kelly_fraction: Optional[float] = None,
    max_stake_cap: Optional[float] = None,
) -> Dict[str, Any]:
    """Evaluate one latest eligible stored prediction and market snapshot per fixture."""
    evaluated = []
    for match in matches:
        if (
            match.status != "FINISHED"
            or match.home_score is None
            or match.away_score is None
            or match.result_available_at is None
        ):
            continue

        choices = []
        for prediction in match.predictions:
            parameters = prediction.model_parameters
            cutoff = parameters.training_cutoff if parameters else None
            if (
                prediction.kickoff_at_prediction != match.match_date
                or prediction.as_of >= match.match_date
                or cutoff is None
                or cutoff > prediction.as_of
            ):
                continue

            quote = latest_eligible_quote(match.odds_snapshots, prediction.as_of)
            if quote is not None:
                choices.append((prediction, quote))

        if not choices:
            continue

        prediction, quote = max(choices, key=lambda item: item[0].as_of)
        try:
            market_probs, _, _ = calculate_shin_probabilities([
                float(quote.home_odds),
                float(quote.draw_odds),
                float(quote.away_odds),
            ])
        except ValueError:
            continue

        model_probs = {
            "HOME": prediction.prob_home_win,
            "DRAW": prediction.prob_draw,
            "AWAY": prediction.prob_away_win,
        }
        market_probs = dict(zip(("HOME", "DRAW", "AWAY"), market_probs))
        actual = _actual_outcome(match)
        evaluated.append({
            "match": match,
            "prediction": prediction,
            "quote": quote,
            "model_probs": model_probs,
            "market_probs": market_probs,
            "actual": actual,
        })

    if not evaluated:
        return _empty_result(initial_bankroll)

    evaluated.sort(key=lambda item: (item["match"].match_date, item["match"].id))
    bankroll = initial_bankroll
    peak_bankroll = initial_bankroll
    max_drawdown = 0.0
    net_profit = 0.0
    total_staked = 0.0
    winning_bets = 0
    clv_samples = 0
    clv_beaten = 0
    daily_pnl = defaultdict(float)
    daily_start_bankroll = {}
    bet_log = []
    equity_curve = [{
        "bet_index": 0,
        "date": evaluated[0]["match"].match_date.date().isoformat(),
        "bankroll": round(bankroll, 2),
        "profit": 0.0,
        "roi_pct": 0.0,
        "drawdown_pct": 0.0,
    }]

    for fixture in evaluated:
        match = fixture["match"]
        quote = fixture["quote"]
        probabilities = fixture["model_probs"]
        actual = fixture["actual"]
        odds_by_outcome = {
            "HOME": float(quote.home_odds),
            "DRAW": float(quote.draw_odds),
            "AWAY": float(quote.away_odds),
        }

        candidates = []
        for outcome, odds in odds_by_outcome.items():
            ev = probabilities[outcome] * odds - 1.0
            if min_odds <= odds <= max_odds and min_ev <= ev <= max_ev:
                candidates.append((ev, outcome, odds))

        if not candidates:
            continue

        if bankroll <= 0:
            break
        ev, selection, odds = max(candidates)
        stake = round(_stake_amount(
            bankroll, initial_bankroll, odds, ev, staking_strategy,
            kelly_fraction=kelly_fraction,
            max_stake_cap=max_stake_cap,
        ), 2)
        if stake <= 0:
            continue

        won = selection == actual
        pnl = round(stake * (odds - 1.0), 2) if won else -stake
        bankroll = round(bankroll + pnl, 2)
        net_profit += pnl
        total_staked += stake
        winning_bets += int(won)
        day = match.match_date.date()
        daily_start_bankroll.setdefault(day, bankroll - pnl)
        daily_pnl[day] += pnl

        if bankroll > peak_bankroll:
            peak_bankroll = bankroll
        drawdown = (peak_bankroll - bankroll) / peak_bankroll if peak_bankroll else 0.0
        max_drawdown = max(max_drawdown, drawdown)

        # The closing snapshot must be strictly later than the entry snapshot we
        # bet at, otherwise the entry quote itself is selected as the close and
        # every bet resolves to beat_clv = False (systematically understating CLV).
        closing_quote = max(
            (
                candidate for candidate in match.odds_snapshots
                if candidate.source_name == quote.source_name
                and candidate.bookmaker == quote.bookmaker
                and not is_placeholder_quote(candidate)
                and candidate.quote_at > quote.quote_at
                and candidate.quote_at <= match.match_date
                and candidate.recorded_at <= match.match_date
            ),
            key=lambda candidate: candidate.quote_at,
            default=None,
        )
        closing_odds = float(getattr(closing_quote, f"{selection.lower()}_odds")) if closing_quote else None
        # No strictly-later close exists: leave the bet out of the CLV sample
        # instead of recording a spurious loss.
        beat_clv = odds > closing_odds if closing_odds is not None else None
        if beat_clv is not None:
            clv_samples += 1
            clv_beaten += int(beat_clv)

        bet_log.append({
            "bet_id": f"BT_{len(bet_log) + 1:04d}",
            "date": match.match_date.date().isoformat(),
            "league": match.league_id,
            "bookmaker": quote.bookmaker,
            "selection": selection,
            "odds": round(odds, 3),
            "closing_odds": round(closing_odds, 3) if closing_odds is not None else None,
            "beat_clv": beat_clv,
            "ev_pct": round(ev * 100, 2),
            "stake": stake,
            "won": won,
            "pnl": pnl,
            "bankroll": bankroll,
        })
        equity_curve.append({
            "bet_index": len(bet_log),
            "date": match.match_date.date().isoformat(),
            "bankroll": bankroll,
            "profit": round(net_profit, 2),
            "roi_pct": round(net_profit / total_staked * 100, 2),
            "drawdown_pct": round(drawdown * 100, 2),
        })

    actuals = [fixture["actual"] for fixture in evaluated]
    model_predictions = [fixture["model_probs"] for fixture in evaluated]
    market_predictions = [fixture["market_probs"] for fixture in evaluated]

    def brier(predictions):
        outcomes = ("HOME", "DRAW", "AWAY")
        return sum(
            sum((prediction[outcome] - float(outcome == actual)) ** 2 for outcome in outcomes)
            for prediction, actual in zip(predictions, actuals)
        ) / len(actuals)

    model_brier = brier(model_predictions)
    market_brier = brier(market_predictions)
    brier_gain = ((market_brier - model_brier) / market_brier * 100) if market_brier else None

    if bet_log:
        first_day = min(daily_pnl)
        last_day = max(daily_pnl)
        daily_returns = []
        current_day = first_day
        while current_day <= last_day:
            start = daily_start_bankroll.get(current_day, bankroll)
            daily_returns.append(daily_pnl[current_day] / start if start else 0.0)
            current_day = current_day.fromordinal(current_day.toordinal() + 1)
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((value - mean_return) ** 2 for value in daily_returns) / max(1, len(daily_returns) - 1)
        daily_std = math.sqrt(variance)
        sharpe = round(mean_return / daily_std * math.sqrt(365), 2) if daily_std else None
    else:
        sharpe = None

    status = "AVAILABLE" if bet_log else "NO_BETS"

    return {
        "status": status,
        "message": None if bet_log else "Eligible history exists, but no selections meet the requested EV and odds filters.",
        "summary": {
            "initial_bankroll": initial_bankroll,
            "final_bankroll": bankroll,
            "net_profit": round(net_profit, 2),
            "total_bets": len(bet_log),
            "winning_bets": winning_bets,
            "win_rate_pct": round(winning_bets / len(bet_log) * 100, 2) if bet_log else 0.0,
            "total_staked": round(total_staked, 2),
            "roi_pct": round(net_profit / total_staked * 100, 2) if total_staked else 0.0,
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "sharpe_ratio": sharpe,
            "beat_clv_rate_pct": round(clv_beaten / clv_samples * 100, 2) if clv_samples else None,
            "brier_score_model": round(model_brier, 6),
            "brier_score_market": round(market_brier, 6),
            "brier_improvement_pct": round(brier_gain, 2) if brier_gain is not None else None,
        },
        "equity_curve": equity_curve,
        "recent_bets": bet_log[-20:],
        "sample": {"fixtures": len(evaluated), "bets": len(bet_log)},
        "method": "latest stored prediction per finished fixture; one best-EV 1X2 selection per fixture",
    }


_CACHED_HISTORICAL_ROWS: Optional[List[Dict[str, str]]] = None
_CACHED_HISTORICAL_KEY: Optional[Tuple[str, int, int]] = None
_CACHE_LOCK = threading.Lock()

# The combined CSV stores `Date` as either dd/mm/yyyy or the football-data
# dd/mm/yy form. Both are accepted; anything else is treated as undated.
_DATASET_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d")


def _parse_dataset_date(raw: Any) -> Optional[datetime]:
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt in _DATASET_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _sort_rows_by_date(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Globally order rows by parsed match date; undated rows go last, stably.

    The combined CSV is concatenated per division (all E0 seasons, then all E1
    seasons), so without this sort the walk-forward loop would train on future
    seasons for the earlier blocks.
    """
    indexed = list(enumerate(rows))
    indexed.sort(key=lambda item: (
        _parse_dataset_date(item[1].get("Date")) is None,
        _parse_dataset_date(item[1].get("Date")) or datetime.min,
        item[0],
    ))
    return [row for _, row in indexed]


def get_historical_dataset_rows() -> List[Dict[str, str]]:
    """Load the combined CSV once per path/mtime/size. The lock avoids a torn cache."""
    global _CACHED_HISTORICAL_ROWS, _CACHED_HISTORICAL_KEY
    candidates = [
        Path("/app/data/historical/england_10y_combined.csv"),
        Path("backend/data/historical/england_10y_combined.csv"),
        Path("data/historical/england_10y_combined.csv"),
        Path("../data/historical/england_10y_combined.csv"),
    ]
    with _CACHE_LOCK:
        for path in candidates:
            if not path.exists():
                continue
            stat = path.stat()
            key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
            if _CACHED_HISTORICAL_ROWS is not None and _CACHED_HISTORICAL_KEY == key:
                return _CACHED_HISTORICAL_ROWS
            with open(path, "r", encoding="utf-8-sig") as handle:
                loaded = list(csv.DictReader(handle))
            _CACHED_HISTORICAL_ROWS = _sort_rows_by_date(loaded)
            _CACHED_HISTORICAL_KEY = key
            return _CACHED_HISTORICAL_ROWS
        return []


def _poisson_1x2(lam: float, mu: float, support: int = 10) -> Tuple[float, float, float]:
    lam = min(max(lam, 0.05), 6.0)
    mu = min(max(mu, 0.05), 6.0)
    home_pmf = [math.exp(-lam)]
    away_pmf = [math.exp(-mu)]
    for goals in range(1, support + 1):
        home_pmf.append(home_pmf[-1] * lam / goals)
        away_pmf.append(away_pmf[-1] * mu / goals)
    home = draw = away = 0.0
    for home_goals, home_p in enumerate(home_pmf):
        for away_goals, away_p in enumerate(away_pmf):
            mass = home_p * away_p
            if home_goals > away_goals:
                home += mass
            elif home_goals == away_goals:
                draw += mass
            else:
                away += mass
    total = home + draw + away
    if total <= 0:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return (home / total, draw / total, away / total)


class _TeamRateModel:
    """Walk-forward goals-per-game model. Updated only after a fixture is scored."""

    PRIOR = 6.0

    def __init__(self) -> None:
        self.scored: Dict[str, float] = defaultdict(float)
        self.conceded: Dict[str, float] = defaultdict(float)
        self.games: Dict[str, int] = defaultdict(int)
        self.home_goals = 0.0
        self.away_goals = 0.0
        self.matches = 0

    def ready(self, home: str, away: str) -> bool:
        return self.matches >= 40 and self.games[home] >= 3 and self.games[away] >= 3

    def predict(self, home: str, away: str) -> Tuple[float, float, float]:
        league = max(0.2, (self.home_goals + self.away_goals) / max(1, self.matches) / 2.0)
        avg_home = self.home_goals / self.matches
        avg_away = self.away_goals / self.matches

        def attack(team: str) -> float:
            return (self.scored[team] + self.PRIOR * league) / (self.games[team] + self.PRIOR)

        def defense(team: str) -> float:
            return (self.conceded[team] + self.PRIOR * league) / (self.games[team] + self.PRIOR)

        base = max(league, 0.2)
        lam = avg_home * (attack(home) / base) * (defense(away) / base)
        mu = avg_away * (attack(away) / base) * (defense(home) / base)
        return _poisson_1x2(lam, mu)

    def update(self, home: str, away: str, home_goals: int, away_goals: int) -> None:
        self.scored[home] += home_goals
        self.conceded[home] += away_goals
        self.scored[away] += away_goals
        self.conceded[away] += home_goals
        self.games[home] += 1
        self.games[away] += 1
        self.home_goals += home_goals
        self.away_goals += away_goals
        self.matches += 1


def calculate_dataset_backtest(
    initial_bankroll: float = 10000.0,
    staking_strategy: str = "HALF_KELLY",
    min_ev: float = 0.05,
    max_ev: float = 0.40,
    min_odds: float = 1.30,
    max_odds: float = 6.00,
    league_filter: Optional[str] = None,
    years: int = 10,
    kelly_fraction: Optional[float] = None,
    max_stake_cap: Optional[float] = None,
) -> Dict[str, Any]:
    raw_rows = get_historical_dataset_rows()
    if not raw_rows:
        # Previously this silently looked like an empty-but-successful run. The
        # file being missing/unparseable is a distinct, actionable condition.
        return _dataset_unavailable_result(initial_bankroll, years)

    rows = _sort_rows_by_date(raw_rows)
    # Filter by league
    if league_filter and league_filter.upper() not in ("ALL", "*"):
        norm_league = league_filter.upper()
        if norm_league in ("EPL", "PREMIER_LEAGUE", "E0"):
            rows = [r for r in rows if r.get("Div") == "E0"]
        elif norm_league in ("CHAMPIONSHIP", "E1"):
            rows = [r for r in rows if r.get("Div") == "E1"]

    # Filter by years relative to the current season, not a hardcoded 2027.
    # `years` is the number of seasons to keep; a value large enough to cover
    # the whole dataset simply keeps everything (previously years >= 12 skipped
    # the filter entirely, so years=12 silently returned all history).
    if years and years > 0:
        today = datetime.now(timezone.utc)
        anchor_year = today.year if today.month >= 7 else today.year - 1
        min_start_year = anchor_year - years + 1
        filtered_rows = []
        for r in rows:
            season = r.get("Season", "")
            try:
                start_yr = int(season.split("-")[0])
                if start_yr >= min_start_year:
                    filtered_rows.append(r)
            except Exception:
                filtered_rows.append(r)
        rows = filtered_rows

    bankroll = float(initial_bankroll)
    peak_bankroll = bankroll
    max_drawdown = 0.0

    bet_log: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []

    clv_samples = 0
    clv_beaten = 0
    clv_edge_sum = 0.0
    winning_bets = 0
    total_staked = 0.0
    evaluated = []
    daily_pnl: Dict[Any, float] = defaultdict(float)
    daily_start: Dict[Any, float] = {}

    equity_curve.append({
        "bet_index": 0,
        "date": "Start",
        "bankroll": round(bankroll, 2),
        "profit": 0.0,
        "roi_pct": 0.0,
        "drawdown_pct": 0.0,
    })

    # Probabilities come from past scores only. Prices and the Brier baseline
    # are the same Pinnacle quote. Best-across-books odds are not used.
    rates = _TeamRateModel()
    # Group by match date so a whole matchday is predicted from one model
    # snapshot: same-day fixtures kick off together and must not leak one
    # match's result into a later same-day forecast. Undated rows are processed
    # one at a time at the end, in their original (deterministic) order.
    matchdays: List[Tuple[Optional[datetime], List[Tuple[Optional[datetime], Dict[str, str]]]]] = []
    for parsed, r in ((_parse_dataset_date(row.get("Date")), row) for row in rows):
        if parsed is not None and matchdays and matchdays[-1][0] == parsed:
            matchdays[-1][1].append((parsed, r))
        else:
            matchdays.append((parsed, [(parsed, r)]))

    for _day, day_rows in matchdays:
        # Predict phase: the model state entering this matchday is frozen.
        prepared = []
        for parsed, r in day_rows:
            actual_ftr = r.get("FTR")
            if actual_ftr not in ("H", "D", "A"):
                continue
            actual_outcome = {"H": "HOME", "D": "DRAW", "A": "AWAY"}[actual_ftr]
            home_team = r.get("HomeTeam") or ""
            away_team = r.get("AwayTeam") or ""
            try:
                home_goals = int(float(r.get("FTHG") or ""))
                away_goals = int(float(r.get("FTAG") or ""))
            except (TypeError, ValueError):
                continue
            if not home_team or not away_team or home_goals < 0 or away_goals < 0:
                continue

            model_probs = None
            market_probs = None
            pinnacle_odds = None
            if rates.ready(home_team, away_team) and bankroll > 0:
                try:
                    ps_h = float(r.get("PSH") or 0)
                    ps_d = float(r.get("PSD") or 0)
                    ps_a = float(r.get("PSA") or 0)
                    if ps_h > 1.0 and ps_d > 1.0 and ps_a > 1.0:
                        dejuiced, _, _ = calculate_shin_probabilities([ps_h, ps_d, ps_a])
                        predicted = rates.predict(home_team, away_team)
                        model_probs = {"HOME": predicted[0], "DRAW": predicted[1], "AWAY": predicted[2]}
                        market_probs = {"HOME": dejuiced[0], "DRAW": dejuiced[1], "AWAY": dejuiced[2]}
                        pinnacle_odds = (ps_h, ps_d, ps_a)
                except (TypeError, ValueError):
                    model_probs = None

            prepared.append({
                "row": r,
                "parsed": parsed,
                "actual": actual_outcome,
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "model_probs": model_probs,
                "market_probs": market_probs,
                "pinnacle_odds": pinnacle_odds,
            })

        # Settle phase: every bet today is decided from the frozen snapshot.
        for item in prepared:
            r = item["row"]
            model_probs = item["model_probs"]
            market_probs = item["market_probs"]
            pinnacle_odds = item["pinnacle_odds"]
            if model_probs is None or market_probs is None or pinnacle_odds is None:
                continue

            actual_outcome = item["actual"]
            evaluated.append({
                "actual": actual_outcome,
                "model_probs": model_probs,
                "market_probs": market_probs,
            })

            odds_list = [
                ("HOME", pinnacle_odds[0], model_probs["HOME"], r.get("PSCH")),
                ("DRAW", pinnacle_odds[1], model_probs["DRAW"], r.get("PSCD")),
                ("AWAY", pinnacle_odds[2], model_probs["AWAY"], r.get("PSCA")),
            ]

            best_ev = -1.0
            best_sel = None
            for sel, odds, prob, cl_odds in odds_list:
                ev = prob * odds - 1.0
                if min_odds <= odds <= max_odds and min_ev <= ev <= max_ev:
                    if ev > best_ev:
                        try:
                            parsed_cl = float(cl_odds) if cl_odds else None
                        except (ValueError, TypeError):
                            parsed_cl = None
                        best_ev = ev
                        best_sel = (sel, odds, prob, parsed_cl)

            if not best_sel or bankroll <= 0:
                continue

            sel, odds, prob, cl_odds = best_sel
            try:
                stake = _stake_amount(
                    bankroll, initial_bankroll, odds, best_ev, staking_strategy,
                    kelly_fraction=kelly_fraction,
                    max_stake_cap=max_stake_cap,
                )
            except Exception:
                continue

            if stake <= 0.0:
                continue

            won = (actual_outcome == sel)
            pnl = stake * (odds - 1.0) if won else -stake
            start_of_day_bankroll = bankroll
            bankroll += pnl
            total_staked += stake
            if won:
                winning_bets += 1

            if bankroll > peak_bankroll:
                peak_bankroll = bankroll
            drawdown = (peak_bankroll - bankroll) / peak_bankroll if peak_bankroll > 0 else 0.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown

            beat_clv = (odds > cl_odds) if cl_odds is not None else None
            clv_edge = ((odds / cl_odds) - 1.0) if cl_odds is not None and cl_odds > 0 else None
            if beat_clv is not None:
                clv_samples += 1
                clv_beaten += int(beat_clv)
                if clv_edge is not None:
                    clv_edge_sum += clv_edge

            date_str = r.get("Date", "")
            home_team = r.get("HomeTeam", "")
            away_team = r.get("AwayTeam", "")
            league_name = r.get("League") or ("Premier League" if r.get("Div") == "E0" else "Championship")

            day_key = item["parsed"].date() if item["parsed"] is not None else date_str
            daily_start.setdefault(day_key, start_of_day_bankroll)
            daily_pnl[day_key] += pnl

            bet_log.append({
                "bet_id": f"HB_{len(bet_log) + 1:04d}",
                "date": date_str,
                "season": r.get("Season", ""),
                "league": league_name,
                "match": f"{home_team} vs {away_team}",
                "selection": sel,
                "odds": round(odds, 3),
                "closing_odds": round(cl_odds, 3) if cl_odds is not None else None,
                "beat_clv": beat_clv,
                "clv_edge_pct": round(clv_edge * 100, 2) if clv_edge is not None else None,
                "ev_pct": round(best_ev * 100, 2),
                "stake": round(stake, 2),
                "won": won,
                "pnl": round(pnl, 2),
                "bankroll": round(bankroll, 2),
            })

            equity_curve.append({
                "bet_index": len(bet_log),
                "date": date_str,
                "bankroll": round(bankroll, 2),
                "profit": round(bankroll - initial_bankroll, 2),
                "roi_pct": round((bankroll - initial_bankroll) / total_staked * 100, 2) if total_staked > 0 else 0.0,
                "drawdown_pct": round(drawdown * 100, 2),
            })

        # Update phase: the model learns all of today's results at once.
        for item in prepared:
            rates.update(item["home_team"], item["away_team"], item["home_goals"], item["away_goals"])

    if len(equity_curve) > 120:
        step = max(1, len(equity_curve) // 120)
        downsampled = [equity_curve[0]] + equity_curve[1:-1:step] + [equity_curve[-1]]
        equity_curve = downsampled

    net_profit = bankroll - initial_bankroll
    roi_pct = round(net_profit / total_staked * 100, 2) if total_staked > 0 else 0.0
    win_rate_pct = round(winning_bets / len(bet_log) * 100, 2) if bet_log else 0.0
    beat_clv_pct = round(clv_beaten / clv_samples * 100, 2) if clv_samples > 0 else None
    avg_clv_edge_pct = round(clv_edge_sum / clv_samples * 100, 2) if clv_samples > 0 else None

    if len(bet_log) > 10:
        # Daily Sharpe on fractional returns, consistent with the database path:
        # each day's return is that day's PnL over the bankroll at its start.
        if daily_pnl and all(isinstance(key, date) for key in daily_pnl):
            first_day = min(daily_pnl)
            last_day = max(daily_pnl)
            daily_returns = []
            current_day = first_day
            while current_day <= last_day:
                start = daily_start.get(current_day, bankroll)
                daily_returns.append(daily_pnl[current_day] / start if start else 0.0)
                current_day = current_day.fromordinal(current_day.toordinal() + 1)
        else:
            daily_returns = [
                pnl / daily_start[key] if daily_start.get(key) else 0.0
                for key, pnl in daily_pnl.items()
            ]
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((value - mean_return) ** 2 for value in daily_returns) / max(1, len(daily_returns) - 1)
        daily_std = math.sqrt(variance)
        sharpe = round(mean_return / daily_std * math.sqrt(365), 2) if daily_std else None
    else:
        sharpe = None

    actuals = [fixture["actual"] for fixture in evaluated]
    model_predictions = [fixture["model_probs"] for fixture in evaluated]
    market_predictions = [fixture["market_probs"] for fixture in evaluated]

    def brier(predictions):
        outcomes = ("HOME", "DRAW", "AWAY")
        return sum(
            sum((prediction[outcome] - float(outcome == actual)) ** 2 for outcome in outcomes)
            for prediction, actual in zip(predictions, actuals)
        ) / len(actuals) if actuals else 0.0

    model_brier = brier(model_predictions) if actuals else 0.0
    market_brier = brier(market_predictions) if actuals else 0.0
    brier_gain = ((market_brier - model_brier) / market_brier * 100) if market_brier > 0 else None

    # Shared status contract: AVAILABLE only when the model both beats the
    # market on Brier and backtests profitable; otherwise MODEL_NO_EDGE with a
    # readable explanation. No usable sample at all is INSUFFICIENT_DATA.
    if not evaluated:
        status = "INSUFFICIENT_DATA"
        message = (
            "Historical dataset exists but yielded no evaluable fixtures for the "
            "requested league/years window."
        )
    elif roi_pct > 0 and brier_gain is not None and brier_gain > 0:
        status = "AVAILABLE"
        message = None
    else:
        status = "MODEL_NO_EDGE"
        message = (
            f"Model shows no edge over the market: backtest ROI {roi_pct}% over "
            f"{len(bet_log)} bets, Brier improvement "
            f"{round(brier_gain, 2) if brier_gain is not None else None}% versus the "
            "Shin-de-juiced Pinnacle baseline."
        )

    return {
        "status": status,
        "dataset_name": f"England 10-Year Historical Combined ({years}Y)",
        "message": message,
        "summary": {
            "initial_bankroll": initial_bankroll,
            "final_bankroll": round(bankroll, 2),
            "net_profit": round(net_profit, 2),
            "total_bets": len(bet_log),
            "winning_bets": winning_bets,
            "win_rate_pct": win_rate_pct,
            "total_staked": round(total_staked, 2),
            "roi_pct": roi_pct,
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "sharpe_ratio": sharpe,
            "beat_clv_rate_pct": beat_clv_pct,
            "avg_clv_edge_pct": avg_clv_edge_pct,
            "brier_score_model": round(model_brier, 6),
            "brier_score_market": round(market_brier, 6),
            "brier_improvement_pct": round(brier_gain, 2) if brier_gain is not None else None,
        },
        "equity_curve": equity_curve,
        "recent_bets": bet_log[-25:],
        "sample": {"fixtures": len(evaluated), "bets": len(bet_log)},
        "method": (
            "Walk-forward Poisson team-rate model trained only on earlier results, "
            "staking the same fixture's Pinnacle opening price. "
            "Market Brier uses Shin de-juicing of that Pinnacle quote. "
            "This path is not Dixon-Coles and does not bet best-across-books prices."
        ),
        "probability_source": "POISSON_TEAM_RATES",
        "price_source": "PINNACLE_OPENING",
    }


async def run_historical_backtest(
    db: AsyncSession,
    initial_bankroll: float = 10000.0,
    staking_strategy: str = "HALF_KELLY",
    min_ev: float = 0.05,
    max_ev: float = 0.40,
    min_odds: float = 1.30,
    max_odds: float = 7.00,
    league_filter: Optional[str] = None,
    dataset: str = "HISTORICAL_10Y",
    years: int = 10,
    kelly_fraction: Optional[float] = None,
    max_stake_cap: Optional[float] = None,
) -> Dict[str, Any]:
    stake_kwargs = {
        "kelly_fraction": kelly_fraction,
        "max_stake_cap": max_stake_cap,
    }
    if dataset == "HISTORICAL_10Y":
        return calculate_dataset_backtest(
            initial_bankroll=initial_bankroll,
            staking_strategy=staking_strategy,
            min_ev=min_ev,
            max_ev=max_ev,
            min_odds=min_odds,
            max_odds=max_odds,
            league_filter=league_filter,
            years=years,
            **stake_kwargs,
        )

    stmt = (
        select(Match)
        .options(
            selectinload(Match.predictions).selectinload(Prediction.model_parameters),
            selectinload(Match.odds_snapshots),
        )
        .where(
            Match.status == "FINISHED",
            Match.home_score.isnot(None),
            Match.away_score.isnot(None),
            Match.result_available_at.isnot(None),
        )
        .order_by(Match.match_date.asc(), Match.id.asc())
    )
    if league_filter and league_filter.upper() not in ("ALL", "*"):
        if league_filter.upper() in ("TOP5", "TOP_5"):
            stmt = stmt.where(Match.league_id.in_(("EPL", "LA_LIGA", "SERIE_A", "BUNDESLIGA", "LIGUE_1")))
        else:
            stmt = stmt.where(Match.league_id == league_filter.upper())

    matches = (await db.execute(stmt)).scalars().unique().all()
    res = calculate_historical_backtest(
        matches,
        initial_bankroll=initial_bankroll,
        staking_strategy=staking_strategy,
        min_ev=min_ev,
        max_ev=max_ev,
        min_odds=min_odds,
        max_odds=max_odds,
        **stake_kwargs,
    )
    if res.get("status") == "INSUFFICIENT_DATA":
        res["message"] = (
            "No finished matches have an eligible stored prediction and pre-kickoff quote. "
            "Pass dataset=HISTORICAL_10Y to run the separate CSV backtest."
        )
        res["dataset_name"] = "DATABASE"
    return res
