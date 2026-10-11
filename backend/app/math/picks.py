from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.models import Match, Prediction
from app.math.derivatives import compute_derived_markets
from app.math.ev import calculate_ev, has_value_signal
from app.math.freshness import latest_eligible_quote


# docs/04 §4: a published signal needs unrounded EV >= 0.05.
MIN_SIGNAL_EV = 0.05
# Shared ceiling: an EV above this is treated as an uncalibrated tail anomaly
# rather than an edge. Exported so the scanner (app/api/v1/alpha.py) applies the
# same bound instead of re-declaring its own.
MAX_SIGNAL_EV = 0.35


def generate_rationale(
    category: str,
    home_team: str,
    away_team: str,
    selection_type: str,
    selection_name: str,
    odds: float,
    fair_odds: float,
    prob: float,
    ev: float,
    lambda_h: float,
    mu_a: float,
    top_scores: Optional[List[Dict[str, Any]]],
    extra_data: Optional[Dict[str, Any]] = None,
    lang: str = "zh",
) -> str:
    prob_pct = round(prob * 100, 1)
    ev_pct = round(ev * 100, 1)
    total_xg = round(lambda_h + mu_a, 2)
    if category == "GOALS":
        p_over = extra_data.get("p_over_2_5", 0.0) if extra_data else 0.0
        p_under = extra_data.get("p_under_2_5", 1.0 - p_over) if extra_data else 1.0 - p_over
        p_btts = extra_data.get("p_btts", 0.0) if extra_data else 0.0
        p_over_pct = round(p_over * 100, 1)
        p_under_pct = round(p_under * 100, 1)
        if lang == "en":
            return (
                f"Model estimates: expected total goals {total_xg:.2f}. "
                f"Cumulative Over 2.5 probability is {p_over_pct}% vs. {p_under_pct}% Under 2.5 "
                f"(BTTS probability {round(p_btts * 100, 1)}%). "
                "Note: Individual scores (like 1-1) represent statistical single modes, "
                "while Over 2.5 aggregates the probability mass of all scorelines with >= 3 goals."
            )
        return (
            f"模型估计两队总进球期望为 {total_xg:.2f}；"
            f"全场大 2.5 球累计概率为 {p_over_pct}%（对比小 2.5 球 {p_under_pct}%，双方进球概率 {round(p_btts * 100, 1)}%）。"
            "说明：1-1 等单项比分为统计众数(最高单一频次)，而大 2.5 球涵盖了所有≥3球比分的概率总和。"
        )

    if lang == "en":
        label = "Banker Rationale. " if category == "BANKER" else ""
        return (
            f"{label}Model estimate for {selection_name}: {prob_pct}% (fair odds {fair_odds:.2f}); "
            f"stored bookmaker odds: {odds:.2f}; estimated EV: {ev_pct:+.1f}%. "
            "This is a model estimate, not a guaranteed outcome."
        )
    label = "稳胆核心理由" if category == "BANKER" else "模型推荐"
    return (
        f"【{label}】模型对{selection_name}的概率估计为 {prob_pct}%（公允赔率 {fair_odds:.2f}）；"
        f"已记录机构赔率 {odds:.2f}，估算 EV 为 {ev_pct:+.1f}%。模型估计不代表赛果保证。"
    )


def _match_metadata(match: Match, pred: Prediction, odds) -> Dict[str, Any]:
    return {
        "match_id": match.id,
        "league_id": match.league_id,
        "home_team": match.home_team.canonical_name,
        "away_team": match.away_team.canonical_name,
        "match_date": match.match_date.isoformat(),
        "prediction_as_of": pred.as_of.isoformat(),
        "odds_quote_at": odds.quote_at.isoformat() if odds else None,
        "bookmaker": odds.bookmaker if odds else None,
        "expected_goals": {
            "home": round(pred.lambda_home, 2),
            "away": round(pred.mu_away, 2),
            "total": round(pred.lambda_home + pred.mu_away, 2),
        },
        "top_scores": [
            {
                "score": score.get("score"),
                "prob_pct": round(score.get("prob", 0.0) * 100, 1),
                "goals": (
                    int(score.get("score", "").split("-")[0]) + int(score.get("score", "").split("-")[1])
                    if score.get("score") and "-" in score.get("score") and score.get("score").replace("-", "").isdigit()
                    else None
                ),
            }
            for score in (pred.top_scores or [])[:3]
        ],
    }


def _build_goals_pick(
    match: Match,
    pred: Prediction,
    markets: Dict[str, Any],
    metadata: Dict[str, Any],
    lang: str,
    market_odds: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    totals = markets.get("totals", {})
    over = totals.get("over_2_5", {})
    probability = over.get("prob", 0.0)
    under_prob = round(max(0.0, 1.0 - probability), 4)
    probability_btts = markets.get("btts", {}).get("yes", {}).get("prob", 0.0)
    total_xg = pred.lambda_home + pred.mu_away
    if total_xg < 2.6 and probability < 0.52:
        return None

    # A goals pick is only a *recommendation* when it has an executable price
    # with strictly positive EV. The stored odds snapshots carry 1X2 prices
    # only, so without an Over 2.5 quote there is no value to publish: skip it
    # rather than emitting a price-less "recommendation" that bypasses the EV
    # gate the banker/value/underdog picks all obey.
    if market_odds is None or market_odds <= 1.0:
        return None
    ev = probability * market_odds - 1.0
    if not has_value_signal(ev, MIN_SIGNAL_EV):
        return None

    is_en = lang == "en"
    fair_odds = over.get("fair_odds", round(1.0 / probability, 2) if probability > 0 else 2.0)
    name = "Over 2.5 Goals" if is_en else "全场大 2.5 球"
    return {
        **metadata,
        "pick_id": f"GOAL_{match.id}_O25",
        "category": "GOALS",
        "category_label": "⚽ Goal Feast" if is_en else "⚽ 进球狂欢",
        "selection": "OVER_2_5",
        "selection_name": name,
        "market_type": "Totals (O/U)" if is_en else "大小球 (Totals)",
        "market_odds": round(market_odds, 3),
        "fair_odds": fair_odds,
        "model_probability": round(probability, 4),
        "under_probability": under_prob,
        "totals_line": 2.5,
        "confidence_stars": 5 if probability >= 0.68 else 4,
        "ev_pct": round(ev * 100, 1),
        "price_status": "AVAILABLE",
        "reasoning": generate_rationale(
            "GOALS",
            match.home_team.canonical_name,
            match.away_team.canonical_name,
            "OVER_2_5",
            name,
            market_odds,
            fair_odds,
            probability,
            ev,
            pred.lambda_home,
            pred.mu_away,
            pred.top_scores,
            extra_data={"p_over_2_5": probability, "p_under_2_5": under_prob, "p_btts": probability_btts},
            lang=lang,
        ),
        "key_stats": [
            f"{'Over 2.5 Prob' if is_en else '大球概率'} {round(probability * 100, 1)}%",
            f"{'Total xG' if is_en else '两队期望进球'} {total_xg:.2f}",
            f"{'BTTS Prob' if is_en else '双进概率'} {round(probability_btts * 100, 1)}%",
        ],
    }


def compile_daily_picks(
    matches: List[Match],
    league_id: Optional[str] = None,
    lang: str = "zh",
) -> Dict[str, Any]:
    """
    Processes scheduled matches into curated picks and smart parlays.
    Supports both 'zh' (Chinese) and 'en' (English).
    """
    is_en = lang == "en"
    now = datetime.now(timezone.utc)
    bankers: List[Dict[str, Any]] = []
    values: List[Dict[str, Any]] = []
    underdogs: List[Dict[str, Any]] = []
    goals_list: List[Dict[str, Any]] = []

    for m in matches:
        if not m.predictions:
            continue
        pred = max(m.predictions, key=lambda p: p.as_of)
        odds = latest_eligible_quote(m.odds_snapshots, pred.as_of)
        deriv = compute_derived_markets(
            pred.score_matrix, pred.lambda_home, pred.mu_away, pred.omitted_mass,
            prob_home_win=pred.prob_home_win,
            prob_draw=pred.prob_draw,
            prob_away_win=pred.prob_away_win,
        )
        match_meta = _match_metadata(m, pred, odds)
        if not odds:
            # No 1X2 quote either; nothing can be priced, so nothing is published.
            continue

        h_odds = float(odds.home_odds)
        d_odds = float(odds.draw_odds)
        a_odds = float(odds.away_odds)

        p_h = pred.prob_home_win
        p_d = pred.prob_draw
        p_a = pred.prob_away_win

        ev_h = calculate_ev(p_h, h_odds)
        ev_d = calculate_ev(p_d, d_odds)
        ev_a = calculate_ev(p_a, a_odds)

        # One (match, selection) is published in a single category.
        claimed: set = set()

        # Banker: EV in [0.05, 0.35], win prob >= 42%, odds in [1.20, 2.50].
        banker_opts = []
        if p_h >= 0.42 and 1.20 <= h_odds <= 2.50 and has_value_signal(ev_h, MIN_SIGNAL_EV) and ev_h <= MAX_SIGNAL_EV:
            banker_opts.append((True, p_h, h_odds, ev_h, "HOME_WIN"))
        if p_a >= 0.42 and 1.20 <= a_odds <= 2.50 and has_value_signal(ev_a, MIN_SIGNAL_EV) and ev_a <= MAX_SIGNAL_EV:
            banker_opts.append((False, p_a, a_odds, ev_a, "AWAY_WIN"))

        for is_home, b_prob, b_odds, b_ev, b_code in banker_opts:
            if is_en:
                b_name = f"{m.home_team.canonical_name} (Home Win)" if is_home else f"{m.away_team.canonical_name} (Away Win)"
                cat_label = "⭐ Daily Banker"
                mkt_label = "1X2 Match Odds"
            else:
                b_name = f"{m.home_team.canonical_name} (主胜)" if is_home else f"{m.away_team.canonical_name} (客胜)"
                cat_label = "⭐ 今日稳胆"
                mkt_label = "1X2 独赢"

            b_fair = round(1.0 / b_prob, 2) if b_prob > 0 else 99.0
            stars = 5 if b_prob >= 0.60 else 4

            claimed.add((m.id, b_code))
            bankers.append({
                **match_meta,
                "prob_raw": b_prob,
                "pick_id": f"BANKER_{m.id}_{b_code}",
                "category": "BANKER",
                "category_label": cat_label,
                "selection": b_code,
                "selection_name": b_name,
                "market_type": mkt_label,
                "market_odds": b_odds,
                "fair_odds": b_fair,
                "model_probability": round(b_prob, 4),
                "confidence_stars": stars,
                "ev_pct": round(b_ev * 100, 1),
                "score": round(b_prob * b_ev, 4),
                "reasoning": generate_rationale(
                    "BANKER",
                    m.home_team.canonical_name,
                    m.away_team.canonical_name,
                    b_code,
                    b_name,
                    b_odds,
                    b_fair,
                    b_prob,
                    b_ev,
                    pred.lambda_home,
                    pred.mu_away,
                    pred.top_scores,
                    lang=lang,
                ),
                "key_stats": [
                    f"{'Model Win Rate' if is_en else '模型胜率'} {round(b_prob * 100, 1)}%",
                    f"{'Positive EV' if is_en else '正期望 EV'} +{round(b_ev * 100, 1)}%",
                    f"{'Initial Odds' if is_en else '机构初赔'} {b_odds:.2f}",
                ],
            })

        # 2. Check Value Candidates (EV in [5%, 35%], Win Prob >= 35%, Odds 1.35 <= odds <= 3.30)
        # Excludes non-positive EV lines and uncalibrated tail anomalies (>35%)
        val_cands = [
            ("HOME_WIN", f"{m.home_team.canonical_name} (Home Win)" if is_en else f"{m.home_team.canonical_name} (主胜)", p_h, h_odds, ev_h),
            ("AWAY_WIN", f"{m.away_team.canonical_name} (Away Win)" if is_en else f"{m.away_team.canonical_name} (客胜)", p_a, a_odds, ev_a),
        ]
        for code, name, prob, o, ev in val_cands:
            if (m.id, code) in claimed:
                continue
            if has_value_signal(ev, MIN_SIGNAL_EV) and ev <= MAX_SIGNAL_EV and prob >= 0.35 and 1.35 <= o <= 3.30:
                claimed.add((m.id, code))
                fair = round(1.0 / prob, 2) if prob > 0 else 99.0
                values.append({
                    **match_meta,
                    "prob_raw": prob,
                    "pick_id": f"VAL_{m.id}_{code}",
                    "category": "VALUE",
                    "category_label": "🔥 Top Value Pick" if is_en else "🔥 每日精选",
                    "selection": code,
                    "selection_name": name,
                    "market_type": "1X2 Value" if is_en else "1X2 价值",
                    "market_odds": o,
                    "fair_odds": fair,
                    "model_probability": round(prob, 4),
                    "confidence_stars": 5 if ev >= 0.15 else 4,
                    "ev_pct": round(ev * 100, 1),
                    "risk_adjusted_score": round(prob * ev, 4),
                    "reasoning": generate_rationale(
                        "VALUE",
                        m.home_team.canonical_name,
                        m.away_team.canonical_name,
                        code,
                        name,
                        o,
                        fair,
                        prob,
                        ev,
                        pred.lambda_home,
                        pred.mu_away,
                        pred.top_scores,
                        lang=lang,
                    ),
                    "key_stats": [
                        f"{'Positive EV' if is_en else '正期望 EV'} +{round(ev * 100, 1)}%",
                        f"{'Fair Odds' if is_en else '合理赔率'} {fair:.2f} ({'Now' if is_en else '现赔'} {o:.2f})",
                        f"{'Model Prob' if is_en else '模型胜率'} {round(prob * 100, 1)}%",
                    ],
                })

        # 3. Check Underdog / Draw Candidates (Sensible High Odds 2.50 <= odds <= 4.00, EV in [5%, 35%], prob >= 25%)
        # Strictly positive edge only; excludes longshots with astronomical uncalibrated variance
        dog_cands = [
            ("DRAW", "Draw (平局)" if is_en else "平局 (Draw)", p_d, d_odds, ev_d),
            ("HOME_WIN", f"{m.home_team.canonical_name} (Home Dog)" if is_en else f"{m.home_team.canonical_name} (主胜高赔)", p_h, h_odds, ev_h),
            ("AWAY_WIN", f"{m.away_team.canonical_name} (Away Dog)" if is_en else f"{m.away_team.canonical_name} (客胜高赔)", p_a, a_odds, ev_a),
        ]
        for code, name, prob, o, ev in dog_cands:
            if (m.id, code) in claimed:
                continue
            if 2.50 <= o <= 4.00 and has_value_signal(ev, MIN_SIGNAL_EV) and ev <= MAX_SIGNAL_EV and prob >= 0.25:
                claimed.add((m.id, code))
                fair = round(1.0 / prob, 2) if prob > 0 else 99.0
                underdogs.append({
                    **match_meta,
                    "prob_raw": prob,
                    "pick_id": f"DOG_{m.id}_{code}",
                    "category": "UNDERDOG",
                    "category_label": "💣 Value Underdog" if is_en else "💣 搏冷高赔",
                    "selection": code,
                    "selection_name": name,
                    "market_type": "Underdog Pick" if is_en else "高赔搏冷",
                    "market_odds": o,
                    "fair_odds": fair,
                    "model_probability": round(prob, 4),
                    "confidence_stars": 4 if ev >= 0.20 else 3,
                    "ev_pct": round(ev * 100, 1),
                    "reasoning": generate_rationale(
                        "UNDERDOG",
                        m.home_team.canonical_name,
                        m.away_team.canonical_name,
                        code,
                        name,
                        o,
                        fair,
                        prob,
                        ev,
                        pred.lambda_home,
                        pred.mu_away,
                        pred.top_scores,
                        lang=lang,
                    ),
                    "key_stats": [
                        f"{'Underdog Odds' if is_en else '搏冷赔率'} {o:.2f}",
                        f"{'Positive EV' if is_en else '正期望 EV'} +{round(ev * 100, 1)}%",
                        f"{'Model Prob' if is_en else '模型胜率'} {round(prob * 100, 1)}%",
                    ],
                })

        # Goals picks require an executable Over 2.5 price with positive EV.
        # Stored odds snapshots carry 1X2 prices only, so no goals-market quote
        # exists and `_build_goals_pick` returns None: goals are deliberately not
        # published as recommendations rather than bypassing the EV gate.
        goal_pick = _build_goals_pick(m, pred, deriv, match_meta, lang)
        if goal_pick:
            goals_list.append(goal_pick)

    def _sort_key(primary: str):
        def key(item: Dict[str, Any]):
            return (-float(item.get(primary) or 0.0), str(item.get("match_id") or ""), str(item.get("selection") or ""))
        return key

    bankers.sort(key=_sort_key("score"))
    values.sort(key=_sort_key("risk_adjusted_score"))
    underdogs.sort(key=_sort_key("ev_pct"))
    goals_list.sort(key=lambda x: (
        -float((x.get("expected_goals") or {}).get("total") or 0.0),
        str(x.get("match_id") or ""),
    ))

    top_bankers = bankers[:6]
    top_values = values[:6]
    top_underdogs = underdogs[:6]
    top_goals = goals_list[:6]

    # Generate Smart Parlays
    parlays = _build_smart_parlays(top_bankers, top_values, top_underdogs, lang=lang)

    def _publish(pick: Dict[str, Any]) -> Dict[str, Any]:
        pick.pop("prob_raw", None)
        return pick

    top_bankers = [_publish(pick) for pick in top_bankers]
    top_values = [_publish(pick) for pick in top_values]
    top_underdogs = [_publish(pick) for pick in top_underdogs]

    return {
        "generated_at": now.isoformat(),
        "lang": lang,
        "summary": {
            "banker_count": len(top_bankers),
            "value_count": len(top_values),
            "underdog_count": len(top_underdogs),
            "goals_count": len(top_goals),
            "parlays_count": len(parlays),
        },
        "bankers": top_bankers,
        "values": top_values,
        "underdogs": top_underdogs,
        "goals": top_goals,
        "parlays": parlays,
    }


def _leg_prob(leg: Dict[str, Any]) -> float:
    raw = leg.get("prob_raw")
    if isinstance(raw, (int, float)):
        return float(raw)
    return float(leg.get("model_probability") or 0.0)


def _joint(legs: List[Dict[str, Any]]) -> tuple:
    """Unrounded joint odds, probability, and EV, plus display rounding."""
    c_odds_raw = 1.0
    j_prob_raw = 1.0
    for leg in legs:
        c_odds_raw *= float(leg["market_odds"])
        j_prob_raw *= _leg_prob(leg)
    j_ev_raw = j_prob_raw * c_odds_raw - 1.0
    return c_odds_raw, j_prob_raw, j_ev_raw, round(c_odds_raw, 2), round(j_prob_raw, 4), round(j_ev_raw * 100, 1)


def _build_smart_parlays(
    bankers: List[Dict[str, Any]],
    values: List[Dict[str, Any]],
    underdogs: List[Dict[str, Any]],
    lang: str = "zh",
) -> List[Dict[str, Any]]:
    """
    Constructs 3 strictly positive-EV parlays with disciplined odds ceilings and joint win probabilities.
    First Law of Quantitative Betting: All parlays MUST have joint EV > 0.
    """
    is_en = lang == "en"
    parlays = []

    # 1. 稳健 2 串 1: Pool consists of positive-EV bankers and low-odds values (odds <= 2.60, EV > 0)
    safe_pool = bankers + [v for v in values if v["market_odds"] <= 2.60 and (v.get("ev_pct") or 0) > 0]
    unique_safe = []
    seen_safe_matches = set()
    for s in safe_pool:
        if s["match_id"] not in seen_safe_matches and (s.get("ev_pct") or 0) > 0:
            unique_safe.append(s)
            seen_safe_matches.add(s["match_id"])

    if len(unique_safe) >= 2:
        leg1, leg2 = unique_safe[:2]
        _c_raw, j_prob_raw, j_ev_raw, c_odds, j_prob, j_ev = _joint([leg1, leg2])

        # Inclusion uses the unrounded joint EV so rounding cannot flip the sign.
        if j_ev_raw > 0:
            ev_str = f"+{j_ev}%"
            if is_en:
                title = "🛡️ Daily 2-Fold Positive Alpha"
                subtitle = "Strictly positive EV accumulator; independent low-risk fixtures"
                badge = "Banker Combo"
                copy_text = (
                    f"【MatchLambda Safe 2-Fold Parlay Ticket】\n"
                    f"1. [{leg1['league_id']}] {leg1['home_team']} vs {leg1['away_team']} -> Pick: {leg1['selection_name']} @{leg1['market_odds']:.2f}\n"
                    f"2. [{leg2['league_id']}] {leg2['home_team']} vs {leg2['away_team']} -> Pick: {leg2['selection_name']} @{leg2['market_odds']:.2f}\n"
                    f"Combined Odds: {c_odds:.2f} | Est. Win Rate: {round(j_prob*100, 1)}% | Expected EV: {ev_str}\n"
                    f"Stake Recommendation: Stake ¥100 -> Est. Payout: ¥{round(100 * c_odds, 1)}"
                )
            else:
                title = "🛡️ 今日两场组合估算"
                subtitle = "双腿均具备正期望 Alpha（EV > 0），假设比赛结果相互独立"
                badge = "稳胆组合"
                copy_text = (
                    f"【MatchLambda 稳健 2 串 1 方案】\n"
                    f"1. [{leg1['league_id']}] {leg1['home_team']} vs {leg1['away_team']} -> 推荐: {leg1['selection_name']} @{leg1['market_odds']:.2f}\n"
                    f"2. [{leg2['league_id']}] {leg2['home_team']} vs {leg2['away_team']} -> 推荐: {leg2['selection_name']} @{leg2['market_odds']:.2f}\n"
                    f"组合赔率: {c_odds:.2f} | 预估命中率: {round(j_prob*100, 1)}% | 期望盈利率: {ev_str}\n"
                    f"投注建议: 投 100 元预计奖金 {round(100 * c_odds, 1)} 元"
                )

            parlays.append({
                "parlay_id": "PARLAY_SAFE_2",
                "type": "SAFE_2X1",
                "title": title,
                "subtitle": subtitle,
                "badge": badge,
                "tag_color": "emerald",
                "combined_odds": c_odds,
                "win_probability_pct": round(j_prob * 100, 1),
                "expected_ev_pct": j_ev,
                "suggested_unit": 100,
                "expected_return": round(100 * c_odds, 1),
                "copy_text": copy_text,
                "legs": [
                    {
                        "match_id": leg1["match_id"],
                        "league_id": leg1["league_id"],
                        "match_date": leg1["match_date"],
                        "home_team": leg1["home_team"],
                        "away_team": leg1["away_team"],
                        "selection": leg1["selection_name"],
                        "odds": leg1["market_odds"],
                        "win_prob": round(leg1["model_probability"] * 100, 1),
                    },
                    {
                        "match_id": leg2["match_id"],
                        "league_id": leg2["league_id"],
                        "match_date": leg2["match_date"],
                        "home_team": leg2["home_team"],
                        "away_team": leg2["away_team"],
                        "selection": leg2["selection_name"],
                        "odds": leg2["market_odds"],
                        "win_prob": round(leg2["model_probability"] * 100, 1),
                    },
                ],
            })

    # 2. 黄金进阶 3 串 1 (Balanced 3-fold, Strictly Positive EV).
    #    Legs are positive-EV bankers/values with odds <= 3.30; combined odds are
    #    whatever those legs produce and are not constrained to a target band.
    b_cands = bankers + values
    selected_matches = set()
    b_legs = []
    for cand in b_cands:
        if cand["match_id"] not in selected_matches and (cand.get("ev_pct") or 0) > 0 and cand["market_odds"] <= 3.30:
            b_legs.append(cand)
            selected_matches.add(cand["match_id"])
        if len(b_legs) >= 3:
            break

    if len(b_legs) >= 3:
        _c_raw, _p_raw, j_ev_raw, c_odds, j_prob, j_ev = _joint(b_legs[:3])

        if j_ev_raw > 0:
            ev_str = f"+{j_ev}%"
            if is_en:
                title = "🔥 Golden 3-Fold (Balanced Risk/Reward)"
                subtitle = "Three strictly positive-EV value lines curated for high Sharpe ratio"
                badge = "Golden Combo"
                copy_text = (
                    f"【MatchLambda Golden 3-Fold Parlay Ticket】\n"
                    f"1. [{b_legs[0]['league_id']}] {b_legs[0]['home_team']} vs {b_legs[0]['away_team']} -> {b_legs[0]['selection_name']} @{b_legs[0]['market_odds']:.2f}\n"
                    f"2. [{b_legs[1]['league_id']}] {b_legs[1]['home_team']} vs {b_legs[1]['away_team']} -> {b_legs[1]['selection_name']} @{b_legs[1]['market_odds']:.2f}\n"
                    f"3. [{b_legs[2]['league_id']}] {b_legs[2]['home_team']} vs {b_legs[2]['away_team']} -> {b_legs[2]['selection_name']} @{b_legs[2]['market_odds']:.2f}\n"
                    f"Combined Odds: {c_odds:.2f} | Est. Win Rate: {round(j_prob*100, 1)}% | Expected EV: {ev_str}\n"
                    f"Stake Recommendation: Stake ¥50 -> Est. Payout: ¥{round(50 * c_odds, 1)}"
                )
            else:
                title = "🔥 黄金进阶 3 串 1 (中倍高盈亏比)"
                subtitle = "三场标的全部具备正期望收益（EV > 0），科学搭配高夏普比率"
                badge = "黄金组合"
                copy_text = (
                    f"【MatchLambda 黄金 3 串 1 方案】\n"
                    f"1. [{b_legs[0]['league_id']}] {b_legs[0]['home_team']} vs {b_legs[0]['away_team']} -> {b_legs[0]['selection_name']} @{b_legs[0]['market_odds']:.2f}\n"
                    f"2. [{b_legs[1]['league_id']}] {b_legs[1]['home_team']} vs {b_legs[1]['away_team']} -> {b_legs[1]['selection_name']} @{b_legs[1]['market_odds']:.2f}\n"
                    f"3. [{b_legs[2]['league_id']}] {b_legs[2]['home_team']} vs {b_legs[2]['away_team']} -> {b_legs[2]['selection_name']} @{b_legs[2]['market_odds']:.2f}\n"
                    f"组合赔率: {c_odds:.2f} | 预估命中率: {round(j_prob*100, 1)}% | 期望盈利率: {ev_str}\n"
                    f"投注建议: 投 50 元预计奖金 {round(50 * c_odds, 1)} 元"
                )

            parlays.append({
                "parlay_id": "PARLAY_BALANCED_3",
                "type": "BALANCED_3X1",
                "title": title,
                "subtitle": subtitle,
                "badge": badge,
                "tag_color": "blue",
                "combined_odds": c_odds,
                "win_probability_pct": round(j_prob * 100, 1),
                "expected_ev_pct": j_ev,
                "suggested_unit": 50,
                "expected_return": round(50 * c_odds, 1),
                "copy_text": copy_text,
                "legs": [
                    {
                        "match_id": l["match_id"],
                        "league_id": l["league_id"],
                        "match_date": l["match_date"],
                        "home_team": l["home_team"],
                        "away_team": l["away_team"],
                        "selection": l["selection_name"],
                        "odds": l["market_odds"],
                        "win_prob": round(l["model_probability"] * 100, 1),
                    }
                    for l in b_legs
                ],
            })

    # 3. 梦想搏冷 3 串 1 (Lottery High Odds, Strictly Positive EV).
    #    Legs are positive-EV underdogs in [2.50, 4.00]; combined odds are the
    #    product of those legs, not enforced into a target band.
    dog_legs = []
    dog_seen = set()
    for d in underdogs:
        if d["match_id"] not in dog_seen and 2.50 <= d["market_odds"] <= 4.00 and (d.get("ev_pct") or 0) > 0:
            dog_legs.append(d)
            dog_seen.add(d["match_id"])
        if len(dog_legs) >= 3:
            break

    if len(dog_legs) >= 3:
        _c_raw, _p_raw, j_ev_raw, c_odds, j_prob, j_ev = _joint(dog_legs[:3])

        if j_ev_raw > 0:
            ev_str = f"+{j_ev}%"
            if is_en:
                title = "💣 Longshot 3-Fold Lottery (Positive Edge)"
                subtitle = "3 mispriced high-odds draws and underdogs with verified positive EV"
                badge = "10x Longshot"
                copy_text = (
                    f"【MatchLambda Longshot 3-Fold Lottery Ticket】\n"
                    f"1. [{dog_legs[0]['league_id']}] {dog_legs[0]['home_team']} vs {dog_legs[0]['away_team']} -> {dog_legs[0]['selection_name']} @{dog_legs[0]['market_odds']:.2f}\n"
                    f"2. [{dog_legs[1]['league_id']}] {dog_legs[1]['home_team']} vs {dog_legs[1]['away_team']} -> {dog_legs[1]['selection_name']} @{dog_legs[1]['market_odds']:.2f}\n"
                    f"3. [{dog_legs[2]['league_id']}] {dog_legs[2]['home_team']} vs {dog_legs[2]['away_team']} -> {dog_legs[2]['selection_name']} @{dog_legs[2]['market_odds']:.2f}\n"
                    f"Combined Odds: {c_odds:.2f} | Est. Win Rate: {round(j_prob*100, 1)}% | Expected EV: {ev_str}\n"
                    f"Stake Recommendation: Stake ¥20 micro-unit -> Est. Payout: ¥{round(20 * c_odds, 1)}"
                )
            else:
                title = "💣 梦想搏冷 3 串 1 (十倍大奖小博大)"
                subtitle = "精选 3 场机构深度低估高赔冷门与平局，单票博取十倍以上正期望暴击"
                badge = "十倍搏冷"
                copy_text = (
                    f"【MatchLambda 梦想搏冷 3 串 1 方案】\n"
                    f"1. [{dog_legs[0]['league_id']}] {dog_legs[0]['home_team']} vs {dog_legs[0]['away_team']} -> {dog_legs[0]['selection_name']} @{dog_legs[0]['market_odds']:.2f}\n"
                    f"2. [{dog_legs[1]['league_id']}] {dog_legs[1]['home_team']} vs {dog_legs[1]['away_team']} -> {dog_legs[1]['selection_name']} @{dog_legs[1]['market_odds']:.2f}\n"
                    f"3. [{dog_legs[2]['league_id']}] {dog_legs[2]['home_team']} vs {dog_legs[2]['away_team']} -> {dog_legs[2]['selection_name']} @{dog_legs[2]['market_odds']:.2f}\n"
                    f"组合赔率: {c_odds:.2f} | 预估命中率: {round(j_prob*100, 1)}% | 期望盈利率: {ev_str}\n"
                    f"投注建议: 投 20 元小注博取 {round(20 * c_odds, 1)} 元大奖"
                )

            parlays.append({
                "parlay_id": "PARLAY_LOTTERY_3",
                "type": "LOTTERY_3X1",
                "title": title,
                "subtitle": subtitle,
                "badge": badge,
                "tag_color": "amber",
                "combined_odds": c_odds,
                "win_probability_pct": round(j_prob * 100, 1),
                "expected_ev_pct": j_ev,
                "suggested_unit": 20,
                "expected_return": round(20 * c_odds, 1),
                "copy_text": copy_text,
                "legs": [
                    {
                        "match_id": l["match_id"],
                        "league_id": l["league_id"],
                        "match_date": l["match_date"],
                        "home_team": l["home_team"],
                        "away_team": l["away_team"],
                        "selection": l["selection_name"],
                        "odds": l["market_odds"],
                        "win_prob": round(l["model_probability"] * 100, 1),
                    }
                    for l in dog_legs
                ],
            })

    return parlays
